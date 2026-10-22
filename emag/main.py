import asyncio
import itertools
import os
import time
from collections import Counter, deque
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

import httpx
from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from common import ui
from emag import api, pages
from emag.api import OFFERS, record, renotify, renotify_forever

EPOCH = datetime(2026, 1, 1, tzinfo=UTC).timestamp()
router = APIRouter()


class Chaos(BaseModel):
    rate_limit: bool = False
    reject_sku: str | None = None
    freeze_stock: bool = False
    down: bool = False
    renotify_now: bool = False


async def apply_chaos(request: Request, call_next):
    chaos = request.app.state.chaos
    path = request.url.path
    call = path.removeprefix("/api-3/")
    if chaos.down and (path.startswith("/api-3/") or path == "/health"):
        if path.startswith("/api-3/"):
            record(request.app, f"← {call} · 503 · seller API down", problem=True)
        return JSONResponse({"isError": True, "messages": ["service unavailable"]}, 503)
    if chaos.rate_limit and path.startswith("/api-3/"):
        record(request.app, f"← {call} · 429 · Retry-After 1", problem=True)
        body = {"isError": True, "messages": ["rate limit exceeded"]}
        return JSONResponse(body, 429, headers={"Retry-After": "1"})
    return await call_next(request)


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@router.get("/chaos")
async def current_chaos(request: Request) -> dict:
    return request.app.state.chaos.model_dump(exclude={"renotify_now"})


@router.post("/chaos")
async def chaos(request: Request, body: Chaos) -> Chaos:
    state = request.app.state
    changes = body.model_dump(exclude_unset=True, exclude={"renotify_now"})
    state.chaos = state.chaos.model_copy(update=changes)
    if body.renotify_now:
        await renotify(request.app)
    return state.chaos


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with httpx.AsyncClient() as http:
        app.state.http = http
        task = asyncio.create_task(renotify_forever(app))
        yield
        task.cancel()


def create_app() -> FastAPI:
    app = FastAPI(title="eMAG Marketplace", lifespan=lifespan)
    app.state.notify_url = os.environ.get("GLUE_URL", "http://glue:8000") + "/emag/notifications"
    app.state.renotify_seconds = float(os.environ.get("RENOTIFY_SECONDS", "20"))
    app.state.secret = os.environ.get("EMAG_WEBHOOK_SECRET", "")
    app.state.stock = dict.fromkeys(OFFERS, 0)
    app.state.orders = {}
    # Glue keeps its orders across restarts and drops a number it has seen as a duplicate.
    # Tenths of a second keep the clock ahead of even fast demo traffic.
    app.state.order_ids = itertools.count(int((time.time() - EPOCH) * 10))
    app.state.chaos = Chaos()
    app.state.callbacks = Counter()
    app.state.acknowledged = {}
    app.state.cancelled_by = {}
    app.state.offer_updates = {}
    app.state.activity = deque(maxlen=20)
    app.middleware("http")(apply_chaos)
    ui.mount_static(app, Path(__file__).parent)
    app.include_router(pages.router)
    app.include_router(api.router)
    app.include_router(router)
    return app


app = create_app()
