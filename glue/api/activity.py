from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request

from glue import auth, ranges

router = APIRouter(dependencies=[Depends(auth.require("view"))])

KINDS = {
    "orders": [
        "event_received",
        "order_allocated",
        "order_shipped",
        "order_cancelled",
        "emag_acknowledged",
    ],
    "retries": ["retry_scheduled"],
    "problems": [
        "order_failed",
        "unfulfillable",
        "stock_push_failed",
        "signature_rejected",
        "event_rejected",
        "warehouse_unreachable",
    ],
    "duplicates": ["duplicate_dropped", "order_known"],
    "stock": ["stock_pushed", "stock_push_failed"],
    "decisions": [
        "review_decided",
        "review_resolved",
        "rule_changed",
        "rule_applied",
        "settings_changed",
    ],
}


@router.get("/activity")
async def activity(
    request: Request,
    window: Annotated[ranges.Window | None, Depends(ranges.from_query)],
    exact: Annotated[tuple[str, str] | None, Depends(ranges.exact_query)],
    kind: Literal[
        "all", "orders", "retries", "problems", "duplicates", "stock", "decisions"
    ] = "all",
    entity: Annotated[str, Query(max_length=64)] = "",
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=200)] = 25,
) -> dict:
    since, until = exact or ranges.bounds(window)
    rows, total = request.app.state.ctx.db.audit_page(
        kinds=KINDS.get(kind),
        entity=entity.strip(),
        since=since,
        until=until,
        limit=per_page,
        offset=(page - 1) * per_page,
    )
    return {"rows": rows, "total": total, "page": page, "per_page": per_page}
