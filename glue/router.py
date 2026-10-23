from pydantic import BaseModel, Field

from common.models import Order, OrderLine
from glue import reconciler, review, settle
from glue.audit import record
from glue.context import Context
from glue.retry import RetryExhausted, with_retries


class EmagProduct(BaseModel):
    part_number: str
    quantity: int


class EmagOrder(BaseModel):
    id: int
    status: int
    products: list[EmagProduct] = Field(min_length=1)
    customer: str


def fail(
    ctx: Context, order_id: str, correlation_id: str, kind: str, reason: str, operation: str
) -> None:
    # Only a failed placement changes the status: a failed cancel leaves the reservation in
    # place (still allocated), and a failed ship notice leaves the order shipped.
    if operation == "place":
        ctx.db.set_order(order_id, status="failed", last_error=reason)
    else:
        ctx.db.set_order(order_id, last_error=reason)
    record(ctx.db, correlation_id, "order", order_id, kind, reason=reason)
    payload = {**ctx.db.get_order(order_id), "operation": operation}
    review.queue_item(ctx, kind, order_id, reason, correlation_id, payload=payload)


async def place_order(ctx: Context, order: Order, correlation_id: str) -> None:
    # Business-level dedupe: eMAG re-notifies, Adobe may redeliver under a new event id.
    if not ctx.db.insert_order_if_new(order):
        existing = ctx.db.get_order(order.id)
        if existing["status"] == "received" and order.id not in ctx.sending:
            # Received but nobody sending it: the glue stopped before the warehouse answer was
            # recorded. The warehouse dedupes on Idempotency-Key, so sending it again is safe.
            record(ctx.db, correlation_id, "order", order.id, "allocation_resumed")
            await allocate(ctx, order, correlation_id)
            return
        action = "placed_after_cancel" if existing["status"] == "cancelled" else "order_known"
        record(ctx.db, correlation_id, "order", order.id, action)
        return
    await allocate(ctx, order, correlation_id)


async def allocate(ctx: Context, order: Order, correlation_id: str) -> None:
    def on_retry(attempt: int, delay: float, problem: str) -> None:
        ctx.db.set_order(order.id, attempts=attempt + 1, last_error=problem)
        record(
            ctx.db,
            correlation_id,
            "order",
            order.id,
            "retry_scheduled",
            attempt=attempt,
            delay_seconds=round(delay, 2),
            problem=problem,
        )

    ctx.sending.add(order.id)
    try:
        response = await with_retries(ctx, lambda: ctx.warehouse.create_order(order), on_retry)
    except RetryExhausted as exc:
        return fail(ctx, order.id, correlation_id, "order_failed", str(exc), "place")
    finally:
        ctx.sending.discard(order.id)
    if response.status_code == 201:
        # A cancel handled while the warehouse call was in flight already marked the order
        # cancelled; the reservation it just got must be released again.
        cancelled_meanwhile = ctx.db.get_order(order.id)["status"] == "cancelled"
        ctx.db.set_order(order.id, status="allocated", last_error=None)
        lines = [line.model_dump() for line in order.lines]
        record(ctx.db, correlation_id, "order", order.id, "order_allocated", lines=lines)
        if cancelled_meanwhile:
            return await cancel_order(ctx, order.id, correlation_id)
        skus = [line.sku for line in order.lines]
        return await reconciler.reconcile_skus(ctx, skus, correlation_id)
    if response.status_code == 409:
        reason = "warehouse has no stock: sold on another channel first"
        return fail(ctx, order.id, correlation_id, "unfulfillable", reason, "place")
    reason = f"warehouse rejected: HTTP {response.status_code} {response.text}"
    fail(ctx, order.id, correlation_id, "order_failed", reason, "place")


async def import_emag_order(ctx: Context, event: dict) -> None:
    emag_id = event["payload"]["order_id"]
    correlation_id = event["event_id"]
    response = await with_retries(ctx, lambda: ctx.emag.read_order(emag_id))
    response.raise_for_status()
    raw = EmagOrder.model_validate(response.json())
    order = Order(
        id=f"emag-{raw.id}",
        channel="emag",
        channel_order_id=str(raw.id),
        lines=[OrderLine(sku=p.part_number, qty=p.quantity) for p in raw.products],
        customer=raw.customer,
    )
    if event["payload"]["type"] == "new":
        await place_order(ctx, order, correlation_id)
        await with_retries(ctx, lambda: ctx.emag.acknowledge(emag_id))
        record(ctx.db, correlation_id, "order", order.id, "emag_acknowledged")
    else:
        await cancel_order(ctx, order.id, correlation_id)


async def cancel_order(ctx: Context, order_id: str, correlation_id: str) -> None:
    order = ctx.db.get_order(order_id)
    if order is None:
        # The cancel overtook the placement; remember it so the late placement is not allocated.
        channel, channel_order_id = order_id.split("-", 1)
        stub = Order(
            id=order_id, channel=channel, channel_order_id=channel_order_id, lines=[], customer=""
        )
        ctx.db.insert_order_if_new(stub, status="cancelled")
        record(ctx.db, correlation_id, "order", order_id, "order_cancelled", note="before placed")
        return settle.settle(ctx, order_id, "cancelled", correlation_id)
    if order["status"] == "cancelled":
        record(ctx.db, correlation_id, "order", order_id, "cancel_repeated")
        return
    releases_stock = order["status"] == "allocated"
    if releases_stock:
        try:
            response = await with_retries(ctx, lambda: ctx.warehouse.cancel_order(order_id))
        except RetryExhausted as exc:
            reason = f"warehouse cancel not delivered: {exc}"
            return fail(ctx, order_id, correlation_id, "order_failed", reason, "cancel")
        if response.status_code == 409:
            reason = "already shipped: customer cancelled after dispatch"
            return fail(ctx, order_id, correlation_id, "order_failed", reason, "cancel")
    ctx.db.set_order(order_id, status="cancelled")
    record(ctx.db, correlation_id, "order", order_id, "order_cancelled", was=order["status"])
    settle.settle(ctx, order_id, "cancelled", correlation_id)
    if releases_stock:
        skus = [line["sku"] for line in order["lines"]]
        await reconciler.reconcile_skus(ctx, skus, correlation_id)


async def cancel_on_channel(ctx: Context, order_id: str, correlation_id: str) -> None:
    order = ctx.db.get_order(order_id)
    if order["channel"] == "shop":
        response = await with_retries(ctx, lambda: ctx.shop.cancel(order_id))
    else:
        emag_id = int(order["channel_order_id"])
        response = await with_retries(ctx, lambda: ctx.emag.set_status(emag_id, 0))
    response.raise_for_status()
    await cancel_order(ctx, order_id, correlation_id)


async def mark_shipped(ctx: Context, event: dict) -> None:
    order_id = event["payload"]["order_id"]
    if ctx.db.get_order(order_id) is None:
        raise LookupError(f"warehouse shipped unknown order {order_id}")
    ctx.db.set_order(order_id, status="shipped")
    settle.settle(ctx, order_id, "shipped", event["event_id"])
    await notify_shipped(ctx, order_id, event["event_id"])


async def notify_shipped(ctx: Context, order_id: str, correlation_id: str) -> None:
    order = ctx.db.get_order(order_id)
    try:
        if order["channel"] == "shop":
            response = await with_retries(ctx, lambda: ctx.shop.mark_shipped(order_id))
        else:
            emag_id = int(order["channel_order_id"])
            response = await with_retries(ctx, lambda: ctx.emag.set_status(emag_id, 4))
    except RetryExhausted as exc:
        reason = f"channel not told it shipped: {exc}"
        return fail(ctx, order_id, correlation_id, "order_failed", reason, "ship")
    record(
        ctx.db,
        correlation_id,
        "order",
        order_id,
        "order_shipped",
        channel=order["channel"],
        channel_response=response.status_code,
    )
