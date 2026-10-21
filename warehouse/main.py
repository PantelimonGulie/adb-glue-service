import asyncio
import os
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

import httpx
from fastapi import APIRouter, FastAPI, Form, Header, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from common import ui
from common.events import emit
from common.models import Order, StockLevel

SEED_ON_HAND = {
    "IPH16-128": 25,
    "IPH16-256": 12,
    "MBA-M4": 1,
    "APP-3": 40,
    "IPAD-A16": 15,
    "WATCH-S10": 8,
}

templates = Jinja2Templates(directory=[Path(__file__).parent / "templates", ui.mock_templates_dir])
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
    if chaos.down:
        return unavailable(retry_after=True)
    if chaos.fail_next and request.url.path != "/health":
        chaos.fail_next -= 1
        return unavailable(retry_after=False)
    return await call_next(request)


def find_order(request: Request, order_id: str) -> dict:
    order = request.app.state.orders.get(order_id)
    if order is None:
        raise HTTPException(404, "order not found")
    return order


def stock_levels(stock: dict) -> list[StockLevel]:
    return [
        StockLevel(
            sku=sku,
            on_hand=s["on_hand"],
            reserved=s["reserved"],
            available=s["on_hand"] - s["reserved"],
        )
        for sku, s in stock.items()
    ]


async def send(request: Request, event_type: str, data: dict) -> None:
    state = request.app.state
    await emit(state.http, state.events_url, event_type, data, str(uuid.uuid4()), "warehouse")


@router.get("/")
async def index(request: Request):
    state = request.app.state
    context = {
        "stock": stock_levels(state.stock),
        "orders": state.orders.values(),
        "chaos": state.chaos,
    }
    return templates.TemplateResponse(request, "index.html", context)


@router.post("/orders", status_code=201)
async def create_order(request: Request, order: Order, idempotency_key: Annotated[str, Header()]):
    state = request.app.state
    # Only accepted orders are replayed, so a refused one can be retried once stock is back.
    if idempotency_key in state.accepted:
        return state.accepted[idempotency_key]
    if any(line.sku not in state.stock or line.qty < 1 for line in order.lines):
        return JSONResponse({"reason": "invalid_lines"}, 422)
    if any(
        state.stock[line.sku]["on_hand"] - state.stock[line.sku]["reserved"] < line.qty
        for line in order.lines
    ):
        return JSONResponse({"reason": "insufficient_stock"}, 409)
    for line in order.lines:
        state.stock[line.sku]["reserved"] += line.qty
    state.orders[order.id] = {"id": order.id, "lines": order.lines, "status": "reserved"}
    state.accepted[idempotency_key] = {"id": order.id, "status": "reserved"}
    return state.accepted[idempotency_key]


@router.post("/orders/{order_id}/cancel")
async def cancel_order(request: Request, order_id: str):
    order = find_order(request, order_id)
    if order["status"] == "shipped":
        return JSONResponse({"reason": "already_shipped"}, 409)
    if order["status"] == "reserved":
        for line in order["lines"]:
            request.app.state.stock[line.sku]["reserved"] -= line.qty
        order["status"] = "cancelled"
    return {"id": order_id, "status": order["status"]}


@router.post("/orders/{order_id}/ship")
async def ship(request: Request, order_id: str):
    order = find_order(request, order_id)
    if order["status"] != "reserved":
        raise HTTPException(409, f"order is {order['status']}")
    for line in order["lines"]:
        request.app.state.stock[line.sku]["on_hand"] -= line.qty
        request.app.state.stock[line.sku]["reserved"] -= line.qty
    order["status"] = "shipped"
    await send(request, "order.shipped", {"order_id": order_id})
    return RedirectResponse("/", status_code=303)


@router.post("/stock/{sku}/recount")
async def recount(request: Request, sku: str, on_hand: Annotated[int, Form(ge=0)]):
    stock = request.app.state.stock
    if sku not in stock:
        raise HTTPException(404, "unknown sku")
    stock[sku]["on_hand"] = on_hand
    await send(request, "stock.adjusted", {"sku": sku, **stock[sku]})
    return RedirectResponse("/", status_code=303)


@router.get("/stock")
async def get_stock(request: Request) -> list[StockLevel]:
    return stock_levels(request.app.state.stock)


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


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
    app.state.stock = {sku: {"on_hand": n, "reserved": 0} for sku, n in SEED_ON_HAND.items()}
    app.state.orders = {}
    app.state.accepted = {}
    app.state.chaos = Chaos()
    app.middleware("http")(apply_chaos)
    app.mount("/static", ui.static, name="static")
    app.include_router(router)
    return app


app = create_app()
