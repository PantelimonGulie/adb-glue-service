from functools import partial

from pydantic import BaseModel, Field

from common.models import Order, OrderLine
from glue import reconciler, review, settle
from glue.audit import record
from glue.context import Context
from glue.retry import SYSTEMS, Problem, RetryExhausted, Trouble, retry_logger, with_retries

EMAG_STATUSES = {1: "new", 2: "in progress", 3: "prepared", 4: "finalized"}


class EmagProduct(BaseModel):
    part_number: str
    quantity: int


class EmagOrder(BaseModel):
    id: int
    status: int
    products: list[EmagProduct] = Field(min_length=1)
    customer: str


def fail(
    ctx: Context,
    order_id: str,
    correlation_id: str,
    kind: str,
    reason: str,
    operation: str,
    error: str = "",
) -> None:
    # Only a failed placement changes the status: a failed cancel leaves the reservation in
    # place (still allocated), and a failed ship notice leaves the order shipped.
    if operation == "place":
        ctx.db.set_order(order_id, status="failed", last_error=reason)
    else:
        ctx.db.set_order(order_id, last_error=reason)
    technical = {"error": error} if error else {}
    record(ctx.db, correlation_id, "order", order_id, kind, reason=reason, **technical)
    payload = {**ctx.db.get_order(order_id), "operation": operation}
    review.queue_item(ctx, kind, order_id, reason, correlation_id, payload=payload, error=error)


async def place_order(ctx: Context, order: Order, correlation_id: str) -> None:
    # Business-level dedupe: eMAG re-notifies, Adobe may redeliver under a new event id.
    if not ctx.db.insert_order_if_new(order):
        existing = ctx.db.get_order(order.id)
        # Every send holds this order's lock, so a received order here is one nobody is sending:
        # the glue stopped before the warehouse answer was recorded. The warehouse dedupes on
        # Idempotency-Key, so sending it again is safe.
        if existing["status"] == "received":
            record(ctx.db, correlation_id, "order", order.id, "allocation_resumed")
            await allocate(ctx, order, correlation_id)
            return
        action = "placed_after_cancel" if existing["status"] == "cancelled" else "order_known"
        record(ctx.db, correlation_id, "order", order.id, action)
        return
    await allocate(ctx, order, correlation_id)


async def allocate(ctx: Context, order: Order, correlation_id: str) -> None:
    log = retry_logger(ctx, correlation_id, "order", order.id)

    def on_retry(attempt: int, delay: float, trouble: Trouble) -> None:
        ctx.db.set_order(order.id, attempts=attempt + 1, last_error=trouble.problem)
        log(attempt, delay, trouble)

    send = partial(ctx.warehouse.create_order, order)
    # Tries counts this send only; the audit log keeps every earlier one.
    ctx.db.set_order(order.id, attempts=1)
    try:
        response = await with_retries(ctx, "warehouse", send, on_retry)
    except RetryExhausted as exc:
        return fail(ctx, order.id, correlation_id, "order_failed", str(exc), "place", exc.error)
    if response.status_code == 201:
        ctx.db.set_order(order.id, status="allocated", last_error=None)
        lines = [line.model_dump() for line in order.lines]
        record(ctx.db, correlation_id, "order", order.id, "order_allocated", lines=lines)
        skus = [line.sku for line in order.lines]
        return await reconciler.reconcile_skus(ctx, skus, correlation_id)
    if response.status_code == 409:
        reason = "warehouse has no stock: sold on another channel first"
        return fail(ctx, order.id, correlation_id, "unfulfillable", reason, "place")
    error = f"HTTP {response.status_code} {response.text}"[:300]
    reason = "the Bucharest warehouse refused the order"
    fail(ctx, order.id, correlation_id, "order_failed", reason, "place", error)


async def import_emag_order(ctx: Context, event: dict) -> None:
    emag_id = event["payload"]["order_id"]
    correlation_id = event["event_id"]
    log = retry_logger(ctx, correlation_id, "order", f"emag-{emag_id}")
    response = await with_retries(ctx, "emag", lambda: ctx.emag.read_order(emag_id), log)
    if response.status_code == 404:
        raise Problem("eMAG no longer knows this order (it answered not found)", "HTTP 404")
    if not response.is_success:
        raise Problem("eMAG refused to show this order", f"HTTP {response.status_code}")
    try:
        raw = EmagOrder.model_validate(response.json())
    except ValueError as exc:
        raise Problem("eMAG sent this order in a form Glue cannot read", str(exc)) from None
    order = Order(
        id=f"emag-{raw.id}",
        channel="emag",
        channel_order_id=str(raw.id),
        lines=[OrderLine(sku=p.part_number, qty=p.quantity) for p in raw.products],
        customer=raw.customer,
    )
    # The notice only says which order to read; what eMAG shows now decides, so a forged or
    # stale cancel notice cannot cancel an order the customer still wants.
    if raw.status == 0:
        await cancel_order(ctx, order.id, correlation_id)
    elif event["payload"]["type"] == "new":
        await place_order(ctx, order, correlation_id)
        await with_retries(ctx, "emag", lambda: ctx.emag.acknowledge(emag_id), log)
        record(ctx.db, correlation_id, "order", order.id, "emag_acknowledged")
    else:
        shown = EMAG_STATUSES.get(raw.status, f"status {raw.status}")
        reason = f"eMAG still shows this order as {shown}, so Glue did not cancel it"
        record(ctx.db, correlation_id, "order", order.id, "cancel_ignored", reason=reason)


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
        send = partial(ctx.warehouse.cancel_order, order_id)
        log = retry_logger(ctx, correlation_id, "order", order_id)
        try:
            response = await with_retries(ctx, "warehouse", send, log)
        except RetryExhausted as exc:
            reason = f"cancellation not delivered: {exc}"
            return fail(ctx, order_id, correlation_id, "order_failed", reason, "cancel", exc.error)
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
    channel = order["channel"]
    if channel == "shop":
        send = partial(ctx.shop.cancel, order_id)
    else:
        send = partial(ctx.emag.set_status, int(order["channel_order_id"]), 0)
    log = retry_logger(ctx, correlation_id, "order", order_id)
    response = await with_retries(ctx, channel, send, log)
    if not response.is_success:
        error = f"HTTP {response.status_code}"
        raise Problem(f"{SYSTEMS[channel]} refused to cancel the order", error)
    await cancel_order(ctx, order_id, correlation_id)


async def mark_shipped(ctx: Context, event: dict) -> None:
    order_id = event["payload"]["order_id"]
    if ctx.db.get_order(order_id) is None:
        raise Problem(f"the warehouse shipped {order_id}, an order Glue does not know")
    ctx.db.set_order(order_id, status="shipped")
    settle.settle(ctx, order_id, "shipped", event["event_id"])
    await notify_shipped(ctx, order_id, event["event_id"])


async def notify_shipped(ctx: Context, order_id: str, correlation_id: str) -> None:
    order = ctx.db.get_order(order_id)
    channel = order["channel"]
    log = retry_logger(ctx, correlation_id, "order", order_id)
    if channel == "shop":
        send = partial(ctx.shop.mark_shipped, order_id)
    else:
        emag_id = int(order["channel_order_id"])
        send = partial(ctx.emag.set_status, emag_id, 4)
    try:
        response = await with_retries(ctx, channel, send, log)
    except RetryExhausted as exc:
        reason = f"channel not told it shipped: {exc}"
        return fail(ctx, order_id, correlation_id, "order_failed", reason, "ship", exc.error)
    record(
        ctx.db,
        correlation_id,
        "order",
        order_id,
        "order_shipped",
        channel=order["channel"],
        channel_response=response.status_code,
    )
