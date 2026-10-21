import itertools
import os
import random
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

import httpx
from fastapi import APIRouter, FastAPI, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from common.events import emit
from common.models import Order, OrderLine

PRODUCTS = {
    "IPH16-128": ("iPhone 16 128GB", 4299),
    "IPH16-256": ("iPhone 16 256GB", 4899),
    "MBA-M4": ('MacBook Air 13" M4 16GB', 5799),
    "APP-3": ("AirPods Pro 3", 1299),
    "IPAD-A16": ('iPad 11" A16 128GB', 1999),
    "WATCH-S10": ("Apple Watch Series 10 42mm", 2099),
}

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
router = APIRouter()


class StockItem(BaseModel):
    qty: int = Field(ge=0)


class Chaos(BaseModel):
    duplicate_last: bool = False
    flash_sale: int = Field(0, ge=0)


def find_order(request: Request, order_id: str) -> dict:
    order = request.app.state.orders.get(order_id)
    if order is None:
        raise HTTPException(404, "order not found")
    return order


async def send(request: Request, event_type: str, data: dict) -> None:
    state = request.app.state
    state.last_event = (event_type, data, str(uuid.uuid4()))
    await emit(state.http, state.events_url, *state.last_event, source="shop")


async def place(request: Request, sku: str, qty: int) -> Order:
    state = request.app.state
    if sku not in PRODUCTS:
        raise HTTPException(404, "unknown sku")
    if state.stock[sku] < qty:
        raise HTTPException(409, "not enough stock")
    state.stock[sku] -= qty
    number = next(state.order_numbers)
    order = Order(
        id=f"shop-{number}",
        channel="shop",
        channel_order_id=str(number),
        lines=[OrderLine(sku=sku, qty=qty)],
        customer="Guest",
    )
    state.orders[order.id] = {**order.model_dump(), "status": "pending"}
    await send(request, "order.placed", order.model_dump())
    return order


@router.get("/")
async def catalog(request: Request):
    context = {"products": PRODUCTS, "stock": request.app.state.stock}
    return templates.TemplateResponse(request, "catalog.html", context)


@router.get("/orders")
async def my_orders(request: Request):
    orders = request.app.state.orders.values()
    return templates.TemplateResponse(request, "orders.html", {"orders": orders})


@router.post("/orders")
async def buy(request: Request, sku: Annotated[str, Form()], qty: Annotated[int, Form(ge=1)]):
    await place(request, sku, qty)
    return RedirectResponse("/orders", status_code=303)


@router.post("/orders/{order_id}/cancel")
async def cancel_by_customer(request: Request, order_id: str):
    order = find_order(request, order_id)
    if order["status"] != "pending":
        raise HTTPException(409, f"order is {order['status']}")
    order["status"] = "canceled"
    await send(request, "order.cancelled", {"order_id": order_id})
    return RedirectResponse("/orders", status_code=303)


@router.put("/V1/products/{sku}/stockItems")
async def set_stock(request: Request, sku: str, item: StockItem) -> dict:
    if sku not in PRODUCTS:
        raise HTTPException(404, "unknown sku")
    request.app.state.stock[sku] = item.qty
    return {"sku": sku, "qty": item.qty}


@router.post("/V1/order/{order_id}/ship")
async def ship(request: Request, order_id: str) -> dict:
    order = find_order(request, order_id)
    if order["status"] == "canceled":
        raise HTTPException(409, "order is canceled")
    order["status"] = "complete"
    return {"id": order_id, "status": order["status"]}


@router.post("/V1/orders/{order_id}/cancel")
async def cancel_by_glue(request: Request, order_id: str) -> dict:
    order = find_order(request, order_id)
    if order["status"] == "complete":
        raise HTTPException(409, "order is complete")
    order["status"] = "canceled"
    return {"id": order_id, "status": order["status"]}


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@router.post("/chaos")
async def chaos(request: Request, body: Chaos) -> dict:
    state = request.app.state
    if body.duplicate_last and state.last_event:
        await emit(state.http, state.events_url, *state.last_event, source="shop")
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
    app.state.stock = dict.fromkeys(PRODUCTS, 0)
    app.state.orders = {}
    app.state.order_numbers = itertools.count(1001)
    app.state.last_event = None
    app.include_router(router)
    return app


app = create_app()
