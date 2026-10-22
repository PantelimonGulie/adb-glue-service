from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from glue import auth

router = APIRouter(dependencies=[Depends(auth.require("view"))])


@router.get("/events")
async def events(
    request: Request,
    after: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 200,
) -> dict:
    # One extra row tells whether the caller has to ask again to catch up.
    rows = request.app.state.ctx.db.audit_after(after, limit + 1)
    page = rows[:limit]
    return {"rows": page, "last_id": page[-1]["id"] if page else after, "more": len(rows) > limit}
