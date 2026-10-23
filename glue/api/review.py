import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from openai import APIError
from pydantic import BaseModel

from glue import auth, queries, review
from glue.ai import llm, triage
from glue.api.assistant import can_answer

log = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(auth.require("view"))])
can_decide = Depends(auth.require("decide"))


class RetryAll(BaseModel):
    cause: Literal["outage"]


@router.get("/review")
async def list_review(
    request: Request,
    status: Literal["open", "decided"] = "open",
    cause: Literal["outage", "soldout", "recount", "other", ""] = "",
) -> dict:
    ctx = request.app.state.ctx
    # Newest first for people; retries and rules work through the queue oldest first.
    items = ctx.db.list_review(status)[::-1]
    return {
        "items": [
            queries.review_item(ctx, item) for item in items if cause in ("", review.cause_of(item))
        ],
        "groups": queries.review_groups(items),
    }


@router.post("/review/retry-all")
async def retry_all(
    request: Request, body: RetryAll, user: Annotated[auth.User, can_decide]
) -> dict:
    ctx = request.app.state.ctx
    if not (await queries.health_of(ctx))["warehouse"]["ok"]:
        raise HTTPException(409, "The warehouse is still not answering")
    return {"retried": await review.retry_all(ctx, body.cause, user.name)}


def open_item(request: Request, item_id: int) -> None:
    # Checked before the model, so a wrong id is not answered with "the model is offline".
    item = request.app.state.ctx.db.get_review(item_id)
    if item is None:
        raise HTTPException(404, f"review item {item_id} not found")
    if item["status"] != "open":
        raise HTTPException(409, "This item is already decided.")


@router.post(
    "/review/{item_id}/triage",
    dependencies=[Depends(auth.require("ask")), Depends(open_item), Depends(can_answer)],
)
async def triage_item(request: Request, item_id: int) -> dict:
    ctx = request.app.state.ctx
    try:
        await triage.suggest(ctx, item_id)
    except APIError as exc:
        log.warning("triage %s failed: %s: %s", item_id, type(exc).__name__, exc)
        raise HTTPException(503, llm.failure(exc)) from None
    return queries.review_item(ctx, ctx.db.get_review(item_id))


@router.post("/review/{item_id}/{action}")
async def decide(
    request: Request, item_id: int, action: str, user: Annotated[auth.User, can_decide]
) -> dict:
    ctx = request.app.state.ctx
    try:
        await review.decide(ctx, item_id, action, user.name)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from None
    except review.Conflict as exc:
        raise HTTPException(409, str(exc)) from None
    except Exception as exc:
        # The operator needs to see why; review.decide has already re-queued the order.
        log.warning("review %s %s failed: %s", item_id, action, exc)
        raise HTTPException(502, str(exc)) from None
    return queries.review_item(ctx, ctx.db.get_review(item_id))
