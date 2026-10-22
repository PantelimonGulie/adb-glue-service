from typing import Annotated

from fastapi import APIRouter, Depends, Request

from glue import auth, queries, ranges

router = APIRouter(dependencies=[Depends(auth.require("view"))])


@router.get("/overview")
async def overview(
    request: Request, window: Annotated[ranges.Window | None, Depends(ranges.from_query)]
) -> dict:
    ctx = request.app.state.ctx
    open_items = ctx.db.list_review()
    previous = queries.counters(ctx, *ranges.bounds(window.previous)) if window else None
    return {
        "counters": queries.counters(ctx, *ranges.bounds(window)),
        "previous": previous,
        "systems": await queries.health_of(ctx),
        "open_reviews": len(open_items),
        "review_groups": queries.review_groups(open_items),
        "latest": ctx.db.audit_tail(10),
    }
