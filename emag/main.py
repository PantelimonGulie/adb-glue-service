import asyncio
import itertools
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Literal

import httpx
from fastapi import APIRouter, FastAPI, Form, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from common import signing, ui
from common.catalog import product_name

PRICES = {
    "IPH16-128": 4349,
    "IPH16-256": 4949,
    "MBA-M4": 5849,
    "APP-3": 1319,
    "IPAD-A16": 2049,
    "WATCH-S10": 2149,
}
OFFERS = {sku: (product_name(sku), price) for sku, price in PRICES.items()}
STATUSES = {0: "cancelled", 1: "new", 2: "in progress", 3: "prepared", 4: "finalized"}

log = logging.getLogger(__name__)
EPOCH = datetime(2026, 1, 1, tzinfo=UTC).timestamp()
templates = Jinja2Templates(directory=[Path(__file__).parent / "templates", ui.mock_templates_dir])
router = APIRouter()


class OrderRef(BaseModel):
    id: int


class OrderStatus(BaseModel):
    id: int
    status: Literal[0, 3, 4]


class OfferStock(BaseModel):
    part_number: str
    stock: int = Field(ge=0)


class Chaos(BaseModel):
    rate_limit: bool = False
    reject_sku: str | None = None
    freeze_stock: bool = False
    down: bool = False
    renotify_now: bool = False


def find_order(request: Request, order_id: int) -> dict:
    order = request.app.state.orders.get(order_id)
    if order is None:
        raise HTTPException(404, "order not found")
    return order


async def notify(app: FastAPI, order_id: int, kind: str) -> None:
    body = json.dumps({"order_id": order_id, "type": kind}).encode()
    headers = signing.headers(app.state.secret, body)
    try:
        response = await app.state.http.post(
            app.state.notify_url, content=body, headers=headers, timeout=2
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        log.warning("%s notification for order %s not delivered: %s", kind, order_id, exc)


async def renotify(app: FastAPI) -> None:
    unacknowledged = [o["id"] for o in app.state.orders.values() if o["status"] == 1]
    for order_id in unacknowledged:
        await notify(app, order_id, "new")


async def renotify_forever(app: FastAPI) -> None:
    while True:
        await asyncio.sleep(app.state.renotify_seconds)
        await renotify(app)


async def apply_chaos(request: Request, call_next):
    chaos = request.app.state.chaos
    path = request.url.path
    if chaos.down and (path.startswith("/api-3/") or path == "/health"):
        return JSONResponse({"isError": True, "messages": ["service unavailable"]}, 503)
    if chaos.rate_limit and path.startswith("/api-3/"):
        body = {"isError": True, "messages": ["rate limit exceeded"]}
        return JSONResponse(body, 429, headers={"Retry-After": "1"})
    return await call_next(request)


@router.get("/")
async def listing(request: Request):
    state = request.app.state
    context = {
        "offers": OFFERS,
        "stock": state.stock,
        "orders": state.orders.values(),
        "statuses": STATUSES,
        "chaos": state.chaos,
    }
    return templates.TemplateResponse(request, "listing.html", context)


@router.post("/buy")
async def buy(request: Request, sku: Annotated[str, Form()], qty: Annotated[int, Form(ge=1)]):
    state = request.app.state
    if sku not in OFFERS:
        raise HTTPException(404, "unknown offer")
    if state.stock[sku] < qty:
        raise HTTPException(409, "not enough stock")
    state.stock[sku] -= qty
    order_id = next(state.order_ids)
    state.orders[order_id] = {
        "id": order_id,
        "status": 1,
        "products": [{"part_number": sku, "quantity": qty}],
        "customer": "eMAG customer",
    }
    await notify(request.app, order_id, "new")
    return RedirectResponse("/", status_code=303)


@router.post("/orders/{order_id}/cancel")
async def cancel_by_customer(request: Request, order_id: int):
    order = find_order(request, order_id)
    if order["status"] not in (1, 2):
        raise HTTPException(409, f"order is {STATUSES[order['status']]}")
    order["status"] = 0
    await notify(request.app, order_id, "cancelled")
    return RedirectResponse("/", status_code=303)


@router.post("/api-3/order/read")
async def read_order(request: Request, ref: OrderRef) -> dict:
    return find_order(request, ref.id)


@router.post("/api-3/order/acknowledge")
async def acknowledge(request: Request, ref: OrderRef) -> dict:
    order = find_order(request, ref.id)
    if order["status"] == 1:
        order["status"] = 2
    return {"isError": False}


@router.post("/api-3/order/save")
async def save_order(request: Request, update: OrderStatus) -> dict:
    find_order(request, update.id)["status"] = update.status
    return {"isError": False}


@router.post("/api-3/product_offer/save")
async def save_offers(request: Request, offers: list[OfferStock]) -> dict:
    state = request.app.state
    results = []
    for offer in offers:
        if offer.part_number not in state.stock:
            ok, message = False, "unknown part_number"
        elif offer.part_number == state.chaos.reject_sku:
            ok, message = False, "offer rejected by marketplace validation"
        else:
            if not state.chaos.freeze_stock:
                state.stock[offer.part_number] = offer.stock
            ok, message = True, ""
        results.append({"part_number": offer.part_number, "ok": ok, "message": message})
    return {"isError": not all(r["ok"] for r in results), "results": results}


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
    app.middleware("http")(apply_chaos)
    app.mount("/static", ui.static, name="static")
    app.include_router(router)
    return app


app = create_app()
