from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from starlette.datastructures import State

from common import ui
from emag.api import OFFERS, STATUSES, find_order, notify

OFFER_STATES = {
    "applied": ("applied", "ok"),
    "frozen": ("accepted, not applied (stock frozen)", "warn"),
    "rejected": ("rejected: validation error", "bad"),
}

templates = ui.templates(Path(__file__).parent)
router = APIRouter()


def faults(state: State) -> list[str]:
    chaos = state.chaos
    active = []
    if chaos.freeze_stock:
        active.append("Stock updates from the seller are accepted but not applied.")
    if chaos.rate_limit:
        active.append("The seller API answers 429, retry after 1 second.")
    if chaos.reject_sku:
        active.append(f"Stock updates for {chaos.reject_sku} are rejected.")
    if chaos.down:
        active.append("The seller API is down: every call gets 503.")
    return active


def stats(state: State) -> dict:
    orders = state.orders.values()
    total = len(orders)
    by_seller = sum(who == "seller" for who in state.cancelled_by.values())
    of_total = f"{by_seller} of {total} {'order' if total == 1 else 'orders'}"
    return {
        "orders": total,
        "awaiting": sum(order["status"] == 1 for order in orders),
        "seller_rate": f"{by_seller / total:.1%}" if total else "0.0%",
        "seller_note": of_total if total else "no orders yet",
        "not_applied": sum(outcome != "applied" for _, outcome in state.offer_updates.values()),
    }


def status_chip(state: State, order: dict) -> tuple[str, str]:
    status = order["status"]
    if status == 0:
        who = state.cancelled_by[order["id"]]
        return f"0 · Cancelled by {who}", f"s0 by-{who}"
    return f"{status} · {STATUSES[status].capitalize()}", f"s{status}"


def acknowledged(state: State, order: dict) -> tuple[str, str]:
    at = state.acknowledged.get(order["id"])
    if at:
        return ui.clock(at), ""
    if order["status"] == 1:
        return "not yet", "late"
    return "never", "muted"


def order_rows(state: State) -> list[dict]:
    rows = []
    for order in reversed(state.orders.values()):
        label, tone = status_chip(state, order)
        ack, ack_tone = acknowledged(state, order)
        callbacks = f"sent {state.callbacks[order['id']]}×"
        if order["status"] == 1:
            callbacks += f" · every {state.renotify_seconds:g} s"
        lines = [
            {"code": f"{p['part_number']} × {p['quantity']}", "name": OFFERS[p["part_number"]][0]}
            for p in order["products"]
        ]
        rows.append(
            {
                "id": order["id"],
                "lines": lines,
                "label": label,
                "tone": tone,
                "callbacks": callbacks,
                "ack": ack,
                "ack_tone": ack_tone,
                "is_new": order["status"] == 1,
                "cancellable": order["status"] in (1, 2),
            }
        )
    return rows


def offer_rows(state: State) -> list[dict]:
    rows = []
    for sku, (name, amount) in OFFERS.items():
        update = state.offer_updates.get(sku)
        label, tone = OFFER_STATES[update[1]] if update else ("no update yet", "none")
        row = {"sku": sku, "name": name, "price": ui.price(amount), "stock": state.stock[sku]}
        saved = ui.clock(update[0]) if update else "not yet"
        rows.append({**row, "saved": saved, "state": label, "tone": tone})
    return rows


@router.get("/")
async def seller_center(request: Request):
    state = request.app.state
    activity = [
        {"time": ui.clock(at), "text": text, "problem": problem}
        for at, text, problem in reversed(state.activity)
    ]
    context = {
        "faults": faults(state),
        "stats": stats(state),
        "orders": order_rows(state),
        "offers": offer_rows(state),
        "activity": activity,
    }
    return templates.TemplateResponse(request, "marketplace.html", context)


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
    request.app.state.cancelled_by[order_id] = "customer"
    await notify(request.app, order_id, "cancelled")
    return RedirectResponse("/", status_code=303)
