import logging
from dataclasses import asdict
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from openai import APIError
from pydantic import BaseModel, ConfigDict, Field

from glue import auth, ranges, tuning
from glue.ai import assistant, llm
from glue.context import Context

log = logging.getLogger(__name__)
router = APIRouter()
MODELS = [
    {"id": "local", "label": llm.LABEL, "available": True},
    {"id": "claude", "label": "Claude", "available": False},
    {"id": "gpt", "label": "GPT", "available": False},
    {"id": "gemini", "label": "Gemini", "available": False},
]


class LimitsChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    effort: Literal["low", "medium", "high"] | None = None
    max_tokens_per_question: int | None = Field(None, ge=200, le=8000)
    daily_token_budget: int | None = Field(None, ge=1000, le=2000000)


class Turn(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class Question(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    history: list[Turn] = []


async def can_answer(request: Request) -> None:
    ctx = request.app.state.ctx
    model = await llm.status(ctx)
    if model["status"] != "ready":
        raise HTTPException(503, llm.not_ready(model))
    used = ctx.db.usage_on(ranges.today(ctx.settings.zone))["tokens"]
    if used >= tuning.ai_limits(ctx.db)["daily_token_budget"]:
        raise HTTPException(
            429, "Today's token budget is spent. It resets at midnight, or an admin can raise it."
        )


async def assistant_view(ctx: Context) -> dict:
    usage = ctx.db.usage_on(ranges.today(ctx.settings.zone))
    return {
        "model": await llm.status(ctx),
        "models": MODELS,
        **tuning.ai_limits(ctx.db),
        "used_today": usage["tokens"],
        "questions_today": usage["questions"],
    }


@router.get("/assistant", dependencies=[Depends(auth.require("view"))])
async def get_assistant(request: Request) -> dict:
    return await assistant_view(request.app.state.ctx)


@router.put("/assistant/settings")
async def save_assistant_settings(
    request: Request,
    change: LimitsChange,
    user: Annotated[auth.User, Depends(auth.require("settings"))],
) -> dict:
    ctx = request.app.state.ctx
    tuning.save_ai_limits(ctx, change.model_dump(exclude_none=True), user.name)
    return await assistant_view(ctx)


@router.post("/assistant/ask", dependencies=[Depends(auth.require("ask")), Depends(can_answer)])
async def ask(request: Request, body: Question) -> dict:
    # Only the latest turns, trimmed, go back: a long history crowds the small model's context.
    turns = [{"role": turn.role, "content": turn.content[:4000]} for turn in body.history[-12:]]
    try:
        result = await assistant.ask(
            request.app.state.ctx, [*turns, {"role": "user", "content": body.question}]
        )
    except APIError as exc:
        log.warning("assistant failed: %s: %s", type(exc).__name__, exc)
        raise HTTPException(503, llm.failure(exc)) from None
    return asdict(result)
