import asyncio
import os
from collections import deque
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from common import ui
from warehouse import api, pages
from warehouse.api import record

SEED_ON_HAND = {
    "IPH16-128": 25,
    "IPH16-256": 12,
    "MBA-M4": 1,
    "APP-3": 40,
    "IPAD-A16": 15,
    "WATCH-S10": 8,
}

router = APIRouter()


class Chaos(BaseModel):
    down: bool = False
    slow_seconds: float = Field(0, ge=0)
    fail_next: int = Field(0, ge=0)


def unavailable(retry_after: bool) -> JSONResponse:
    headers = {"Retry-After": "2"} if retry_after else None
    return JSONResponse({"reason": "unavailable"}, 503, headers=headers)


async def apply_chaos(request: Request, call_next):
    if request.url.path in ("/", "/chaos") or request.url.path.startswith("/static/"):
        return await call_next(request)
    chaos = request.app.state.chaos
    if chaos.slow_seconds:
        await asyncio.sleep(chaos.slow_seconds)
    placing = request.method == "POST" and request.url.path == "/orders"
    key = request.headers.get("idempotency-key", "missing")
    if chaos.down:
        if placing:
            record(request.app, f"503 order refused, API offline · key {key}", problem=True)
        return unavailable(retry_after=True)
    if chaos.fail_next and placing:
        chaos.fail_next -= 1
        record(request.app, f"503 order refused, forced failure · key {key}", problem=True)
        return unavailable(retry_after=False)
    return await call_next(request)


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@router.get("/chaos")
async def current_chaos(request: Request) -> Chaos:
    return request.app.state.chaos


@router.post("/chaos")
async def chaos(request: Request, body: Chaos) -> Chaos:
    state = request.app.state
    state.chaos = state.chaos.model_copy(update=body.model_dump(exclude_unset=True))
    return state.chaos


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with httpx.AsyncClient() as http:
        app.state.http = http
        yield


def create_app() -> FastAPI:
    app = FastAPI(title="Warehouse", lifespan=lifespan)
    app.state.events_url = os.environ.get("GLUE_URL", "http://glue:8000") + "/events"
    app.state.secret = os.environ.get("WAREHOUSE_WEBHOOK_SECRET", "")
    app.state.stock = {sku: {"on_hand": n, "reserved": 0} for sku, n in SEED_ON_HAND.items()}
    app.state.orders = {}
    app.state.accepted = {}
    app.state.chaos = Chaos()
    app.state.outbox = deque(maxlen=20)
    app.middleware("http")(apply_chaos)
    ui.mount_static(app, Path(__file__).parent)
    app.include_router(pages.router)
    app.include_router(api.router)
    app.include_router(router)
    return app


app = create_app()
