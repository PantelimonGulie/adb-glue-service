import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from common.events import emit
from common.models import Order, StockLevel

router = APIRouter()


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


def record(app: FastAPI, line: str, problem: bool = False) -> None:
    app.state.outbox.append((datetime.now(UTC), line, problem))


async def send(request: Request, event_type: str, data: dict, subject: str) -> None:
    state = request.app.state
    event_id = str(uuid.uuid4())
    delivered = await emit(
        state.http, state.events_url, event_type, data, event_id, "warehouse", state.secret
    )
    outcome = "delivered" if delivered else "not delivered"
    record(request.app, f"→ {event_type} · {subject} · {outcome}", problem=not delivered)


@router.post("/orders", status_code=201)
async def create_order(request: Request, order: Order, idempotency_key: Annotated[str, Header()]):
    state = request.app.state
    # Only accepted orders are replayed, so a refused one can be retried once stock is back.
    if idempotency_key in state.accepted:
        record(request.app, f"201 already accepted · {order.id}")
        return state.accepted[idempotency_key]
    if any(line.sku not in state.stock or line.qty < 1 for line in order.lines):
        record(request.app, f"422 invalid lines · {order.id}", problem=True)
        return JSONResponse({"reason": "invalid_lines"}, 422)
    if any(
        state.stock[line.sku]["on_hand"] - state.stock[line.sku]["reserved"] < line.qty
        for line in order.lines
    ):
        record(request.app, f"409 insufficient stock · {order.id}", problem=True)
        return JSONResponse({"reason": "insufficient_stock"}, 409)
    for line in order.lines:
        state.stock[line.sku]["reserved"] += line.qty
    state.orders[order.id] = {"id": order.id, "lines": order.lines, "status": "reserved"}
    state.accepted[idempotency_key] = {"id": order.id, "status": "reserved"}
    record(request.app, f"201 order accepted · {order.id}")
    return state.accepted[idempotency_key]


@router.get("/orders")
async def list_orders(request: Request) -> list[dict]:
    return list(request.app.state.orders.values())


@router.post("/orders/{order_id}/cancel")
async def cancel_order(request: Request, order_id: str):
    order = find_order(request, order_id)
    if order["status"] == "shipped":
        record(request.app, f"409 cancel refused, already shipped · {order_id}", problem=True)
        return JSONResponse({"reason": "already_shipped"}, 409)
    if order["status"] == "reserved":
        for line in order["lines"]:
            request.app.state.stock[line.sku]["reserved"] -= line.qty
        order["status"] = "cancelled"
        record(request.app, f"200 order cancelled · {order_id}")
    return {"id": order_id, "status": order["status"]}


@router.get("/stock")
async def get_stock(request: Request) -> list[StockLevel]:
    return stock_levels(request.app.state.stock)
