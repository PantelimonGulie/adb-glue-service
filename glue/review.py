from glue.audit import record
from glue.context import Context


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
