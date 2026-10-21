from common.models import Order
from glue import router
from glue.audit import record
from glue.context import Context

ACTIONS = ("retry", "cancel", "dismiss")


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


async def decide(ctx: Context, item_id: int, action: str, decided_by: str = "operator") -> dict:
    item = ctx.db.get_review(item_id)
    if item is None or item["status"] != "open":
        raise LookupError(f"review item {item_id} is not open")
    if action not in ACTIONS:
        raise ValueError(f"unknown review action {action!r}")
    order_id = item["order_id"]
    order = ctx.db.get_order(order_id) if order_id else None
    if order is None and action != "dismiss":
        raise LookupError(f"review item {item_id} has no order to {action}")
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
        if action == "retry":
            await router.allocate(ctx, Order(id=order_id, **order), correlation_id)
        elif action == "cancel":
            await router.cancel_on_channel(ctx, order_id, correlation_id)
    except Exception as exc:
        open(ctx, item["kind"], order_id, f"{action} failed: {exc}", correlation_id, payload=order)
        raise
    return ctx.db.get_review(item_id)
