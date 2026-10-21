import asyncio
import logging

from common.models import Order
from glue import reconciler, review, router
from glue.audit import record
from glue.context import Context

log = logging.getLogger(__name__)


async def place_shop_order(ctx: Context, event: dict) -> None:
    order = Order.model_validate(event["payload"])
    await router.place_order(ctx, order, event["event_id"])


async def cancel_shop_order(ctx: Context, event: dict) -> None:
    await router.cancel_order(ctx, event["payload"]["order_id"], event["event_id"])


HANDLERS = {
    "order.placed": place_shop_order,
    "order.cancelled": cancel_shop_order,
    "emag.notification": router.import_emag_order,
    "order.shipped": router.mark_shipped,
    "stock.adjusted": reconciler.reconcile_sku,
}


def order_id_in(event: dict) -> str | None:
    payload = event["payload"]
    if event["type"] == "emag.notification":
        return f"emag-{payload.get('order_id')}"
    return payload.get("id") or payload.get("order_id")


async def handle(ctx: Context, event: dict) -> None:
    event_id = event["event_id"]
    async with ctx.worker_slots:
        try:
            await HANDLERS[event["type"]](ctx, event)
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            ctx.db.finish_event(event_id, "failed", error)
            record(
                ctx.db, event_id, "event", event_id, "event_failed", type=event["type"], error=error
            )
            reason = f"unexpected while handling {event['type']}: {error}"
            review.open(ctx, "order_failed", order_id_in(event), reason, event_id, payload=event)
            return
        ctx.db.finish_event(event_id, "done")


async def process_pending(ctx: Context) -> int:
    events = ctx.db.claim_pending_events(ctx.settings.worker_concurrency)
    await asyncio.gather(*(handle(ctx, event) for event in events))
    return len(events)


async def run_forever(ctx: Context) -> None:
    # One task per event; only as many are claimed as there are free slots, so a slow retry
    # occupies one slot while new events keep flowing through the rest.
    tasks: set[asyncio.Task] = set()
    while True:
        free = ctx.settings.worker_concurrency - len(tasks)
        try:
            events = ctx.db.claim_pending_events(free) if free > 0 else []
        except Exception:
            log.exception("claiming events failed")
            events = []
        for event in events:
            task = asyncio.create_task(handle(ctx, event))
            tasks.add(task)
            task.add_done_callback(tasks.discard)
        if not events:
            await asyncio.sleep(0.5)
