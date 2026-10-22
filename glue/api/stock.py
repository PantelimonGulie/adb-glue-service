from fastapi import APIRouter, BackgroundTasks, Depends, Request

from glue import auth, queries, reconciler
from glue.db import now

router = APIRouter(dependencies=[Depends(auth.require("view"))])


@router.get("/stock")
async def stock(request: Request) -> dict:
    ctx = request.app.state.ctx
    return {
        "rows": queries.stock_rows(ctx),
        "reconcile_seconds": ctx.tuning.reconcile_interval_seconds,
    }


@router.post("/stock/push", status_code=202, dependencies=[Depends(auth.require("decide"))])
async def push(request: Request, background: BackgroundTasks) -> None:
    background.add_task(reconciler.reconcile_skus, request.app.state.ctx, None, f"push-{now()}")
