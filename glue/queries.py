import asyncio
import time
from collections import Counter
from datetime import UTC, datetime, timedelta

import httpx

from common.catalog import product_name
from glue import review, rules
from glue.context import Context

CHANNELS = ("shop", "emag")
# "received" is not here: it counts order placements only, see db.placements().
COUNTERS = {
    "duplicates": ("duplicate_dropped", "order_known"),
    "reserved": ("order_allocated",),
    "retries": ("retry_scheduled",),
    "failed": ("order_failed", "unfulfillable"),
}
REVIEW_KEYS = (
    "id",
    "kind",
    "order_id",
    "reason",
    "payload",
    "created_at",
    "status",
    "action",
    "decided_by",
    "decided_at",
)


async def check_health(http: httpx.AsyncClient, base_url: str) -> dict:
    started = time.perf_counter()
    try:
        response = await http.get(f"{base_url}/health", timeout=1)
    except httpx.HTTPError:
        return {"ok": False, "state": "Not responding", "latency_ms": None}
    latency_ms = round((time.perf_counter() - started) * 1000)
    if not response.is_success:
        return {
            "ok": False,
            "state": f"Answering HTTP {response.status_code}",
            "latency_ms": latency_ms,
        }
    return {"ok": True, "state": "Healthy", "latency_ms": latency_ms}


async def health_of(ctx: Context) -> dict:
    urls = ctx.settings.channel_urls()
    checks = await asyncio.gather(*(check_health(ctx.http, url) for url in urls.values()))
    return dict(zip(urls, checks, strict=True))


def counters(ctx: Context, since: str, until: str) -> dict[str, int]:
    counts = ctx.db.counters(since, until)
    return {
        "received": ctx.db.placements(since, until),
        **{name: sum(counts.get(a, 0) for a in actions) for name, actions in COUNTERS.items()},
    }


def order_item(row: dict) -> dict:
    line = row["lines"][0] if row["lines"] else {"sku": "", "qty": 0}
    return {
        "order_id": row["order_id"],
        "channel": row["channel"],
        "sku": line["sku"],
        "product": product_name(line["sku"]),
        "qty": line["qty"],
        "status": row["status"],
        "attempts": row["attempts"],
        "last_error": row["last_error"],
        "updated_at": row["updated_at"],
    }


def stock_state(free: int, told: dict, held_back: dict) -> str:
    if any(row and row["dirty"] for row in told.values()):
        return "refused"
    if any(row is None or row["qty"] != max(0, free - held_back[ch]) for ch, row in told.items()):
        return "behind"
    return "held" if any(held_back.values()) else "in_sync"


def stock_rows(ctx: Context) -> list[dict]:
    warehouse = ctx.db.stock()
    skus = [row["sku"] for row in warehouse]
    told = {ch: {row["sku"]: row for row in ctx.db.channel_stock(ch)} for ch in CHANNELS}
    held = {ch: rules.held_back(ctx, ch, skus) for ch in CHANNELS}
    rows = []
    for row in warehouse:
        sku, free = row["sku"], max(0, row["available"])
        channels = {ch: told[ch].get(sku) for ch in CHANNELS}
        held_back = {ch: held[ch][sku] for ch in CHANNELS}
        shown = {
            ch: {"qty": c["qty"], "dirty": bool(c["dirty"])} if c else None
            for ch, c in channels.items()
        }
        rows.append(
            {
                "sku": sku,
                "product": product_name(sku),
                "on_hand": row["on_hand"],
                "reserved": row["reserved"],
                "free": free,
                **shown,
                "held_back": held_back,
                "state": stock_state(free, channels, held_back),
            }
        )
    return rows


def review_item(ctx: Context, item: dict) -> dict:
    order = ctx.db.get_order(item["order_id"]) if item["order_id"] else None
    suggestion = None
    if item["suggested_reason"] is not None:
        suggestion = {"action": item["suggested_action"], "reason": item["suggested_reason"]}
    return {
        **{key: item[key] for key in REVIEW_KEYS},
        "cause": review.cause_of(item),
        "order": order_item(order) if order else None,
        "allowed": sorted(review.allowed_actions(item, order)),
        "suggestion": suggestion,
    }


def review_groups(items: list[dict]) -> list[dict]:
    counts = Counter(review.cause_of(item) for item in items)
    return [{"cause": cause, "count": counts[cause]} for cause in review.CAUSES if counts[cause]]


def metrics(ctx: Context) -> dict:
    hour_ago = (datetime.now(UTC) - timedelta(hours=1)).isoformat(timespec="milliseconds")
    return {
        "last_hour": ctx.db.counters(hour_ago),
        "total": ctx.db.counters(),
        "open_review_items": len(ctx.db.list_review()),
    }
