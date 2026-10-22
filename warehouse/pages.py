from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from starlette.datastructures import State

from common import ui
from common.catalog import product_name
from warehouse.api import find_order, send

BINS = {
    "IPH16-128": "B-07-1",
    "IPH16-256": "B-07-2",
    "MBA-M4": "A-03-2",
    "APP-3": "C-11-4",
    "IPAD-A16": "A-05-1",
    "WATCH-S10": "C-02-3",
}
CHANNELS = {"shop": "Shop", "emag": "eMAG"}

templates = ui.templates(Path(__file__).parent)
router = APIRouter()


def faults(state: State) -> list[tuple[str, str]]:
    chaos = state.chaos
    active = []
    if chaos.down:
        text = "Every call gets 503 with Retry-After 2. Ship and Save are off until it is back."
        active.append(("Warehouse API offline", text))
    if chaos.slow_seconds:
        text = f"Every call, Ship and Save here included, waits {chaos.slow_seconds:g} s."
        active.append(("Warehouse API slow", text))
    if chaos.fail_next:
        text = "The next order placement gets 503."
        if chaos.fail_next > 1:
            text = f"The next {chaos.fail_next} order placements get 503."
        active.append(("Order intake failing", text))
    return active


def pick_list(state: State) -> list[dict]:
    picks = []
    for order in state.orders.values():
        if order["status"] != "reserved":
            continue
        lines = [
            {
                "text": f"{line.qty} × {line.sku}",
                "name": product_name(line.sku),
                "bin": BINS[line.sku],
            }
            for line in order["lines"]
        ]
        channel = CHANNELS[order["id"].split("-", 1)[0]]
        picks.append({"id": order["id"], "channel": channel, "lines": lines})
    return picks


def stock_rows(state: State) -> list[dict]:
    rows = []
    for sku, level in state.stock.items():
        free = level["on_hand"] - level["reserved"]
        tone = ""
        if free < 0:
            tone = "is-short"
        elif free == 0:
            tone = "is-empty"
        row = {"sku": sku, "name": product_name(sku), "bin": BINS[sku], **level}
        rows.append({**row, "free": free, "tone": tone})
    return rows


@router.get("/")
async def terminal(request: Request):
    state = request.app.state
    picks = pick_list(state)
    outbox = [
        {"time": ui.clock(at), "text": text, "problem": problem}
        for at, text, problem in reversed(state.outbox)
    ]
    context = {
        "faults": faults(state),
        "down": state.chaos.down,
        "picks": picks,
        "pick_note": f"{len(picks)} {'order' if len(picks) == 1 else 'orders'} reserved",
        "stock": stock_rows(state),
        "outbox": outbox,
    }
    return templates.TemplateResponse(request, "warehouse.html", context)


@router.post("/orders/{order_id}/ship")
async def ship(request: Request, order_id: str):
    order = find_order(request, order_id)
    if order["status"] != "reserved":
        raise HTTPException(409, f"order is {order['status']}")
    for line in order["lines"]:
        request.app.state.stock[line.sku]["on_hand"] -= line.qty
        request.app.state.stock[line.sku]["reserved"] -= line.qty
    order["status"] = "shipped"
    await send(request, "order.shipped", {"order_id": order_id}, order_id)
    return RedirectResponse("/", status_code=303)


@router.post("/stock/{sku}/recount")
async def recount(request: Request, sku: str, on_hand: Annotated[int, Form(ge=0)]):
    stock = request.app.state.stock
    if sku not in stock:
        raise HTTPException(404, "unknown sku")
    stock[sku]["on_hand"] = on_hand
    await send(request, "stock.adjusted", {"sku": sku, **stock[sku]}, f"{sku} on hand {on_hand}")
    return RedirectResponse("/", status_code=303)
