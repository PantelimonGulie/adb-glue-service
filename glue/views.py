import asyncio
import time
from datetime import UTC, datetime, timedelta

import httpx
from fastapi import Request

from glue import review as review_queue
from glue import rules
from glue.context import Context

COUNTERS = (
    ("Events received", ("event_received",)),
    ("Duplicates dropped", ("duplicate_dropped", "order_known")),
    ("Orders allocated", ("order_allocated",)),
    ("Retries", ("retry_scheduled",)),
    ("Failed", ("order_failed", "unfulfillable")),
)


def hour_ago() -> str:
    return (datetime.now(UTC) - timedelta(hours=1)).isoformat(timespec="milliseconds")


async def check_health(http: httpx.AsyncClient, base_url: str) -> dict:
    started = time.perf_counter()
    try:
        response = await http.get(f"{base_url}/health", timeout=1)
    except httpx.HTTPError:
        return {"ok": False, "state": "Not responding"}
    if not response.is_success:
        return {"ok": False, "state": f"Answering HTTP {response.status_code}"}
    return {"ok": True, "state": f"Healthy, {round((time.perf_counter() - started) * 1000)} ms"}


async def overview(ctx: Context, request: Request) -> dict:
    urls = {
        "shop": ctx.settings.shop_url,
        "emag": ctx.settings.emag_url,
        "warehouse": ctx.settings.warehouse_url,
    }
    checks = await asyncio.gather(*(check_health(ctx.http, url) for url in urls.values()))
    # Links are for the browser, so they keep the host it used and swap in each mock's port.
    health = {
        name: {**check, "link": request.url.replace(port=httpx.URL(url).port, path="/", query="")}
        for (name, url), check in zip(urls.items(), checks, strict=True)
    }
    total, recent = ctx.db.counters(), ctx.db.counters(hour_ago())
    counters = [
        (label, sum(total.get(a, 0) for a in actions), sum(recent.get(a, 0) for a in actions))
        for label, actions in COUNTERS
    ]
    return {
        "health": health,
        "counters": counters,
        "reviews": ctx.db.list_review(),
        "activity": ctx.db.audit_tail(12),
        "reconcile_seconds": ctx.settings.reconcile_interval_seconds,
    }


def stock(ctx: Context) -> dict:
    warehouse = ctx.db.stock()
    skus = [row["sku"] for row in warehouse]
    channels = ("shop", "emag")
    told = {ch: {row["sku"]: row for row in ctx.db.channel_stock(ch)} for ch in channels}
    held = {ch: rules.held_back(ctx, ch, skus) for ch in channels}
    rows = [
        {
            **row,
            "sellable": max(0, row["available"]),
            "shop": told["shop"].get(row["sku"]),
            "emag": told["emag"].get(row["sku"]),
            "held": {ch: held[ch][row["sku"]] for ch in channels},
        }
        for row in warehouse
    ]
    return {"rows": rows}


def review_card(ctx: Context, item_id: int, error: str | None = None) -> dict:
    item = ctx.db.get_review(item_id)
    order = ctx.db.get_order(item["order_id"]) if item["order_id"] else None
    allowed = review_queue.allowed_actions(item, order)
    offline = ctx.assistant is None
    return {"item": item, "order": order, "allowed": allowed, "error": error, "offline": offline}


def review(ctx: Context) -> dict:
    decided = ctx.db.list_review("decided")[-8:][::-1]
    return {
        "items": [review_card(ctx, item["id"]) for item in ctx.db.list_review()],
        "decided": [review_card(ctx, item["id"]) for item in decided],
    }


def audit(ctx: Context, entity: str) -> dict:
    rows = ctx.db.audit_for(entity)[::-1][:200] if entity else ctx.db.audit_tail(100)
    return {"entity": entity, "rows": rows}


def metrics(ctx: Context) -> dict:
    return {
        "last_hour": ctx.db.counters(hour_ago()),
        "total": ctx.db.counters(),
        "open_review_items": len(ctx.db.list_review()),
    }
