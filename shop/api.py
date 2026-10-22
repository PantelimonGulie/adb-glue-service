import uuid

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from common.catalog import product_name
from common.events import emit
from common.models import Order, OrderLine

PRICES = {
    "IPH16-128": 4299,
    "IPH16-256": 4899,
    "MBA-M4": 5799,
    "APP-3": 1299,
    "IPAD-A16": 1999,
    "WATCH-S10": 2099,
}
PRODUCTS = {sku: (product_name(sku), price) for sku, price in PRICES.items()}

router = APIRouter()


class StockItem(BaseModel):
    qty: int = Field(ge=0)


def find_order(request: Request, order_id: str) -> dict:
    order = request.app.state.orders.get(order_id)
    if order is None:
        raise HTTPException(404, "order not found")
    return order


async def send(request: Request, event_type: str, data: dict) -> None:
    state = request.app.state
    state.last_event = (event_type, data, str(uuid.uuid4()))
    await emit(state.http, state.events_url, *state.last_event, "shop", state.secret)


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


@router.get("/V1/orders")
async def list_orders(request: Request) -> list[dict]:
    return list(request.app.state.orders.values())


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
