from common.models import Order
from glue import router
from glue.audit import record
from glue.context import Context

ACTIONS = ("retry", "cancel", "dismiss")
# A retry repeats the operation that failed, which only makes sense from the state it left.
RETRY_FROM = {"place": "failed", "cancel": "allocated"}


class Conflict(Exception):
    pass


def open(
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


def allowed_actions(item: dict, order: dict | None) -> set[str]:
    if item["status"] != "open":
        return set()
    actions = {"dismiss"}
    if order is None:
        return actions
    if order["status"] == RETRY_FROM[item["payload"].get("operation", "place")]:
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
    # Closed before acting: a retry that fails again must be able to open a fresh item.
    ctx.db.decide_review(item_id, action, decided_by)
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
    try:
        if action == "retry" and item["payload"].get("operation") == "cancel":
            await router.cancel_order(ctx, order_id, correlation_id)
        elif action == "retry":
            await router.allocate(ctx, Order(id=order_id, **order), correlation_id)
        elif action == "cancel":
            await router.cancel_on_channel(ctx, order_id, correlation_id)
    except Exception as exc:
        reason = f"{action} failed: {exc}"
        open(ctx, item["kind"], order_id, reason, correlation_id, payload=item["payload"])
        raise
