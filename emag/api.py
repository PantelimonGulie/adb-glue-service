import asyncio
import json
import logging
from datetime import UTC, datetime
from typing import Literal

import httpx
from fastapi import APIRouter, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from common import signing
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
router = APIRouter()


class OrderRef(BaseModel):
    id: int


class OrderStatus(BaseModel):
    id: int
    status: Literal[0, 3, 4]


class OfferStock(BaseModel):
    part_number: str
    stock: int = Field(ge=0)


def find_order(request: Request, order_id: int) -> dict:
    order = request.app.state.orders.get(order_id)
    if order is None:
        raise HTTPException(404, "order not found")
    return order


def record(app: FastAPI, line: str, problem: bool = False) -> None:
    app.state.activity.append((datetime.now(UTC), line, problem))


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
        record(app, f"callback → Glue · order {order_id} · {kind} · not delivered", problem=True)
        return
    app.state.callbacks[order_id] += 1
    record(app, f"callback → Glue · order {order_id} · {kind} · {response.status_code}")


async def renotify(app: FastAPI) -> None:
    unacknowledged = [o["id"] for o in app.state.orders.values() if o["status"] == 1]
    for order_id in unacknowledged:
        await notify(app, order_id, "new")


async def renotify_forever(app: FastAPI) -> None:
    while True:
        await asyncio.sleep(app.state.renotify_seconds)
        await renotify(app)


@router.post("/api-3/order/read")
async def read_order(request: Request, ref: OrderRef) -> dict:
    order = find_order(request, ref.id)
    record(request.app, f"← order/read {ref.id} · 200")
    return order


@router.post("/api-3/order/acknowledge")
async def acknowledge(request: Request, ref: OrderRef) -> dict:
    order = find_order(request, ref.id)
    if order["status"] == 1:
        order["status"] = 2
        request.app.state.acknowledged[ref.id] = datetime.now(UTC)
    record(request.app, f"← order/acknowledge {ref.id} · 200")
    return {"isError": False}


@router.post("/api-3/order/save")
async def save_order(request: Request, update: OrderStatus) -> dict:
    find_order(request, update.id)["status"] = update.status
    if update.status == 0:
        request.app.state.cancelled_by.setdefault(update.id, "seller")
    record(request.app, f"← order/save {update.id} · status {update.status} · 200")
    return {"isError": False}


@router.post("/api-3/product_offer/save")
async def save_offers(request: Request, offers: list[OfferStock]) -> dict:
    state = request.app.state
    now = datetime.now(UTC)
    results = []
    for offer in offers:
        if offer.part_number not in state.stock:
            ok, message = False, "unknown part_number"
        elif offer.part_number == state.chaos.reject_sku:
            ok, message = False, "offer rejected by marketplace validation"
            state.offer_updates[offer.part_number] = (now, "rejected")
        else:
            if not state.chaos.freeze_stock:
                state.stock[offer.part_number] = offer.stock
            ok, message = True, ""
            outcome = "frozen" if state.chaos.freeze_stock else "applied"
            state.offer_updates[offer.part_number] = (now, outcome)
        results.append({"part_number": offer.part_number, "ok": ok, "message": message})
    rejected = sum(not r["ok"] for r in results)
    notes = [f"{rejected} rejected"] if rejected else []
    if state.chaos.freeze_stock:
        notes.append("stock frozen")
    items = "1 item" if len(offers) == 1 else f"{len(offers)} items"
    line = f"← product_offer/save · {items} · {', '.join(notes) or 'ok'}"
    record(request.app, line, problem=bool(notes))
    return {"isError": not all(r["ok"] for r in results), "results": results}
