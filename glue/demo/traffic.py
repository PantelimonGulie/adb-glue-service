import asyncio
import logging
import random
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import httpx

from common.catalog import product_name
from glue.clients import segment

if TYPE_CHECKING:
    from glue.context import Context

log = logging.getLogger(__name__)

INTERVALS = {"slow": 5.0, "normal": 2.6, "fast": 0.45}
SHOP_SHARE = 0.64
SHIP_EVERY = 6
LOW_STOCK = 3
RESTOCK = 20
# A shelf someone counted on purpose, e.g. to set up a demo story, is left as they set it.
HANDS_OFF = timedelta(minutes=10)


@dataclass
class Traffic:
    running: bool = False
    speed: str = "slow"
    ticks: int = 0


def initial(setting: str) -> Traffic:
    if setting == "off":
        return Traffic()
    if setting not in INTERVALS:
        raise ValueError(f"DEMO_TRAFFIC must be off, slow, normal or fast, not {setting!r}")
    return Traffic(running=True, speed=setting)


def problem(exc: httpx.HTTPError) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        return "it refused the request"
    if isinstance(exc, httpx.TimeoutException):
        return "it took too long to answer"
    return "it could not be reached"


async def buy(ctx: "Context") -> None:
    channel = "shop" if random.random() < SHOP_SHARE else "emag"
    # What the channel was last told, not the warehouse: orders keep coming while it is down.
    in_stock = [row["sku"] for row in ctx.db.channel_stock(channel) if row["qty"] > 0]
    if not in_stock:
        return
    path = "/orders" if channel == "shop" else "/buy"
    url = ctx.settings.channel_urls()[channel] + path
    response = await ctx.http.post(url, data={"sku": random.choice(in_stock), "qty": 1})
    if response.is_error:
        log.info("demo traffic could not buy on %s: HTTP %s", channel, response.status_code)


async def ship_oldest(ctx: "Context") -> tuple[bool, str]:
    url = ctx.settings.warehouse_url
    try:
        response = await ctx.http.get(f"{url}/orders")
        response.raise_for_status()
        reserved = [order["id"] for order in response.json() if order["status"] == "reserved"]
        if not reserved:
            return False, "The warehouse has no reserved order to ship."
        order_id = reserved[0]
        response = await ctx.http.post(f"{url}/orders/{segment(order_id)}/ship")
    except httpx.HTTPError as exc:
        return False, f"The warehouse shipped nothing: {problem(exc)}."
    if response.is_error:
        return False, f"The warehouse refused to ship {order_id}."
    return True, f"The warehouse shipped {order_id}."


async def customer_cancel(ctx: "Context") -> tuple[bool, str]:
    url = ctx.settings.shop_url
    try:
        response = await ctx.http.get(f"{url}/V1/orders")
        response.raise_for_status()
        pending = [order["id"] for order in response.json() if order["status"] == "pending"]
        if not pending:
            return False, "Electronic Market has no open order a customer could cancel."
        order_id = pending[-1]
        response = await ctx.http.post(f"{url}/orders/{segment(order_id)}/cancel")
    except httpx.HTTPError as exc:
        return False, f"Electronic Market cancelled nothing: {problem(exc)}."
    if response.is_error:
        return False, f"Electronic Market refused to cancel {order_id}."
    return True, f"A customer cancelled {order_id} on Electronic Market."


async def recount(ctx: "Context", sku: str, on_hand: int, note: str = "") -> tuple[bool, str]:
    url = f"{ctx.settings.warehouse_url}/stock/{segment(sku)}/recount"
    try:
        response = await ctx.http.post(url, data={"on_hand": on_hand, "note": note})
    except httpx.HTTPError as exc:
        return False, f"The warehouse did not take the count: {problem(exc)}."
    if response.status_code == 404:
        return False, f"The warehouse does not stock {sku}."
    if response.is_error:
        return False, "The warehouse refused the count."
    return True, f"The warehouse now counts {on_hand} {product_name(sku)} on the shelf."


async def restock(ctx: "Context") -> None:
    # Through the warehouse's own recount, so the activity log shows it as a demo restock.
    response = await ctx.warehouse.stock()
    response.raise_for_status()
    since = (datetime.now(UTC) - HANDS_OFF).isoformat(timespec="milliseconds")
    counted = ctx.db.counted_by_hand(since)
    for row in response.json():
        if row["available"] < LOW_STOCK and row["sku"] not in counted:
            await recount(ctx, row["sku"], row["on_hand"] + RESTOCK, note="demo restock")


async def tick(ctx: "Context") -> None:
    ctx.traffic.ticks += 1
    await buy(ctx)
    if ctx.traffic.ticks % SHIP_EVERY == 0:
        ok, message = await ship_oldest(ctx)
        if not ok:
            log.info("demo traffic: %s", message)
    try:
        await restock(ctx)
    except httpx.HTTPError as exc:
        # Demo faults make the warehouse fail on purpose; the next tick tries again.
        log.info("demo traffic did not restock: %s", problem(exc))


async def run_forever(ctx: "Context") -> None:
    # Always running, so the demo controls can start and stop traffic without a restart.
    while True:
        await asyncio.sleep(INTERVALS[ctx.traffic.speed])
        if not ctx.traffic.running:
            continue
        try:
            await tick(ctx)
        except Exception:
            log.exception("demo traffic tick failed")
