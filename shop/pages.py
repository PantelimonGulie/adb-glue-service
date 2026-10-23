from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Query, Request
from fastapi.responses import RedirectResponse

from common import ui
from shop.api import PRODUCTS, find_order, place, send

CATEGORIES = {
    "IPH16-128": "Phones",
    "IPH16-256": "Phones",
    "MBA-M4": "Laptops",
    "IPAD-A16": "Tablets",
    "APP-3": "Audio",
    "WATCH-S10": "Watches",
}
# The shop only hears back when an order ships or is cancelled, so until then it is processing.
STATUSES = {
    "pending": ("Processing", "open"),
    "complete": ("Shipped", "shipped"),
    "canceled": ("Cancelled", "cancelled"),
}

templates = ui.templates(Path(__file__).parent)
router = APIRouter()


def chips(category: str) -> list[dict]:
    links = [{"label": "All", "href": "/", "current": not category}]
    for name in dict.fromkeys(CATEGORIES.values()):
        slug = name.lower()
        links.append({"label": name, "href": f"/?category={slug}", "current": category == slug})
    return links


def availability(left: int) -> tuple[str, str]:
    if left > 1:
        return f"In stock · {left} left", "in"
    if left == 1:
        return "Only 1 left", "last"
    return "Out of stock", "out"


def product_cards(stock: dict[str, int], category: str, query: str) -> list[dict]:
    cards = []
    for sku, (name, amount) in PRODUCTS.items():
        if category and CATEGORIES[sku].lower() != category:
            continue
        if query.lower() not in f"{name} {sku}".lower():
            continue
        note, tone = availability(stock[sku])
        cards.append(
            {
                "sku": sku,
                "name": name,
                "price": ui.price(amount),
                "left": stock[sku],
                "last_one": stock[sku] == 1,
                "note": note,
                "tone": tone,
            }
        )
    return cards


def order_rows(orders: list[dict]) -> list[dict]:
    rows = []
    for order in reversed(orders):
        label, tone = STATUSES[order["status"]]
        items = []
        for line in order["lines"]:
            name = PRODUCTS[line["sku"]][0]
            items.append(name if line["qty"] == 1 else f"{line['qty']} × {name}")
        rows.append(
            {
                "id": order["id"],
                "number": order["channel_order_id"],
                "item": ", ".join(items),
                "label": label,
                "tone": tone,
                "cancellable": order["status"] == "pending",
            }
        )
    return rows


@router.get("/")
async def storefront(
    request: Request,
    category: Annotated[str, Query(max_length=20)] = "",
    q: Annotated[str, Query(max_length=100)] = "",
):
    state = request.app.state
    orders = list(state.orders.values())
    context = {
        "chips": chips(category),
        "query": q,
        "cards": product_cards(state.stock, category, q.strip()),
        "no_match": f"Nothing matches “{q}”." if q.strip() else "There is no such category.",
        "orders": order_rows(orders),
        "open_orders": sum(order["status"] == "pending" for order in orders),
    }
    return templates.TemplateResponse(request, "shop.html", context)


@router.post("/orders")
async def buy(request: Request, sku: Annotated[str, Form()], qty: Annotated[int, Form(ge=1)]):
    await place(request, sku, qty)
    return RedirectResponse("/#orders", status_code=303)


@router.post("/orders/{order_id}/cancel")
async def cancel_by_customer(request: Request, order_id: str):
    order = find_order(request, order_id)
    if order["status"] != "pending":
        raise HTTPException(409, f"order is {order['status']}")
    order["status"] = "canceled"
    await send(request, "order.cancelled", {"order_id": order_id})
    return RedirectResponse("/#orders", status_code=303)
