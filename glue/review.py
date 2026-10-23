import logging

from common.models import Order
from glue import router
from glue.audit import record
from glue.context import Context

log = logging.getLogger(__name__)

ACTIONS = ("retry", "cancel", "dismiss")
CAUSES = ("outage", "soldout", "recount", "other")
OUTAGE_SIGNS = (
    "http 5",
    "timeout",
    "unreachable",
    "not answering",
    "connecterror",
    "readerror",
    "remoteprotocolerror",
)
# A retry repeats the operation that failed, which only makes sense from the state it left.
RETRY_FROM = {"place": "failed", "cancel": "allocated", "ship": "shipped"}


class Conflict(Exception):
    pass


def queue_item(
    ctx: Context,
    kind: str,
    order_id: str | None,
    reason: str,
    correlation_id: str,
    payload: dict | None = None,
) -> int | None:
    item_id = ctx.db.open_review(kind, order_id, payload or {}, reason)
    if item_id is not None:
        record(
            ctx.db,
            correlation_id,
            "order",
            order_id or "-",
            "review_opened",
            review_id=item_id,
            kind=kind,
            reason=reason,
        )
    return item_id


def cause_of(item: dict) -> str:
    reason = item["reason"].lower()
    if item["kind"] == "unfulfillable":
        return "recount" if reason.startswith("recount") else "soldout"
    if item["kind"] == "order_failed" and any(sign in reason for sign in OUTAGE_SIGNS):
        return "outage"
    return "other"


def allowed_actions(item: dict, order: dict | None) -> set[str]:
    if item["status"] != "open":
        return set()
    actions = {"dismiss"}
    if order is None:
        return actions
    if order["status"] == RETRY_FROM.get(item["payload"].get("operation", "place")):
        actions.add("retry")
    if order["status"] not in ("shipped", "cancelled"):
        actions.add("cancel")
    return actions


async def decide(ctx: Context, item_id: int, action: str, decided_by: str = "operator") -> None:
    if action not in ACTIONS:
        raise ValueError(f"unknown review action {action!r}")
    item = ctx.db.get_review(item_id)
    if item is None:
        raise LookupError(f"review item {item_id} not found")
    if item["status"] != "open":
        raise Conflict(f"already decided: {item['action']} by {item['decided_by']}")
    order_id = item["order_id"]
    order = ctx.db.get_order(order_id) if order_id else None
    if action not in allowed_actions(item, order):
        state = f"order is {order['status']}" if order else "no order attached"
        raise Conflict(f"cannot {action}: {state}")
    correlation_id = f"review-{item_id}"
    # No longer open while acting, so a retry that fails again can open a fresh item; a crash
    # mid-action leaves it acting, and the next start puts it back in the queue.
    ctx.db.start_review(item_id, action, decided_by)
    record(
        ctx.db,
        correlation_id,
        "order",
        order_id or "-",
        "review_decided",
        review_id=item_id,
        kind=item["kind"],
        decision=action,
        decided_by=decided_by,
    )
    operation = item["payload"].get("operation")
    try:
        if action == "retry" and operation == "cancel":
            await router.cancel_order(ctx, order_id, correlation_id)
        elif action == "retry" and operation == "ship":
            await router.notify_shipped(ctx, order_id, correlation_id)
        elif action == "retry":
            placed = Order(
                id=order_id,
                channel=order["channel"],
                channel_order_id=order["channel_order_id"],
                lines=order["lines"],
                customer=order["customer"],
            )
            await router.allocate(ctx, placed, correlation_id)
        elif action == "cancel":
            await router.cancel_on_channel(ctx, order_id, correlation_id)
    except Exception as exc:
        ctx.db.decide_review(item_id, action, decided_by)
        reason = f"{action} failed: {exc}"
        queue_item(ctx, item["kind"], order_id, reason, correlation_id, payload=item["payload"])
        raise
    ctx.db.decide_review(item_id, action, decided_by)


async def retry_all(ctx: Context, cause: str, by: str) -> int:
    retried = 0
    for item in ctx.db.list_review():
        order = ctx.db.get_order(item["order_id"]) if item["order_id"] else None
        if cause_of(item) != cause or "retry" not in allowed_actions(item, order):
            continue
        try:
            await decide(ctx, item["id"], "retry", by)
            retried += 1
        except Exception as exc:
            # decide has already re-queued the order with the new reason.
            log.warning("retry of %s failed: %s", item["order_id"], exc)
    return retried
