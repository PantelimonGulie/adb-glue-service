from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from glue import auth, queries, ranges

router = APIRouter(dependencies=[Depends(auth.require("view"))])


@router.get("/orders")
async def list_orders(
    request: Request,
    window: Annotated[ranges.Window | None, Depends(ranges.from_query)],
    q: Annotated[str, Query(max_length=64)] = "",
    channel: Literal["shop", "emag", ""] = "",
    status: Literal["received", "allocated", "shipped", "failed", "cancelled", ""] = "",
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=200)] = 25,
) -> dict:
    since, until = ranges.bounds(window)
    rows, total = request.app.state.ctx.db.list_orders(
        q=q.strip(),
        channel=channel,
        status=status,
        since=since,
        until=until,
        limit=per_page,
        offset=(page - 1) * per_page,
    )
    return {
        "rows": [queries.order_item(row) for row in rows],
        "total": total,
        "page": page,
        "per_page": per_page,
    }


@router.get("/orders/{order_id}")
async def order_detail(request: Request, order_id: str) -> dict:
    ctx = request.app.state.ctx
    order = ctx.db.get_order(order_id)
    if order is None:
        raise HTTPException(404, f"order {order_id} not found")
    return {"order": queries.order_item(order), "timeline": ctx.db.timeline(order_id)}
