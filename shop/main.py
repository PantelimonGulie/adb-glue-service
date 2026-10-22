import itertools
import os
import random
import time
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

import httpx
from fastapi import APIRouter, FastAPI, Request
from pydantic import BaseModel, Field

from common import ui
from common.events import emit
from shop import api, pages
from shop.api import PRODUCTS, place

EPOCH = datetime(2026, 1, 1, tzinfo=UTC).timestamp()
router = APIRouter()


class Chaos(BaseModel):
    duplicate_last: bool = False
    flash_sale: int = Field(0, ge=0)


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@router.post("/chaos")
async def chaos(request: Request, body: Chaos) -> dict:
    state = request.app.state
    if body.duplicate_last and state.last_event:
        await emit(state.http, state.events_url, *state.last_event, "shop", state.secret)
    created = []
    for _ in range(body.flash_sale):
        in_stock = [sku for sku, qty in state.stock.items() if qty > 0]
        if not in_stock:
            break
        created.append((await place(request, random.choice(in_stock), 1)).id)
    return {"duplicated": body.duplicate_last and state.last_event is not None, "created": created}


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with httpx.AsyncClient() as http:
        app.state.http = http
        yield


def create_app() -> FastAPI:
    app = FastAPI(title="Electronic Market", lifespan=lifespan)
    app.state.events_url = os.environ.get("GLUE_URL", "http://glue:8000") + "/events"
    app.state.secret = os.environ.get("SHOP_WEBHOOK_SECRET", "")
    app.state.stock = dict.fromkeys(PRODUCTS, 0)
    app.state.orders = {}
    # Glue keeps its orders across restarts and drops a number it has seen as a duplicate.
    # Tenths of a second keep the clock ahead of even fast demo traffic.
    app.state.order_numbers = itertools.count(int((time.time() - EPOCH) * 10))
    app.state.last_event = None
    ui.mount_static(app, Path(__file__).parent)
    app.include_router(pages.router)
    app.include_router(api.router)
    app.include_router(router)
    return app


app = create_app()
