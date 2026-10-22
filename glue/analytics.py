from collections import Counter, defaultdict
from datetime import UTC, datetime

from common.catalog import product_name
from glue import queries, ranges
from glue.analytics_series import (
    Trip,
    bucket_keys,
    duplicate,
    labels,
    percentile,
    placement,
    seconds_between,
    series,
    trips,
)
from glue.context import Context

WAREHOUSE_ANSWERED = ("order_allocated", "order_shipped", "stock_pushed", "stock_push_failed")


def channel_of(row: dict) -> str:
    detail = row["detail"]
    return detail.get("source") or detail.get("channel") or row["entity_id"].split("-")[0]


def funnel(rows: list[dict], found: dict[str, Trip]) -> dict:
    outcomes = Counter(trip.outcome for trip in found.values())
    messages = ("event_received", "duplicate_dropped")
    return {
        "received": sum(1 for row in rows if row["action"] in messages and placement(row)),
        "duplicates": sum(1 for row in rows if duplicate(row)),
        "sent": len(found),
        "first_try": outcomes["first_try"],
        "after_retry": outcomes["after_retry"],
        "failed": outcomes["failed"],
    }


def longest_outage_minutes(rows: list[dict], until: str) -> int:
    # Nothing is logged when the warehouse comes back; the next thing it answers ends the outage.
    longest, started = 0.0, None
    for row in rows:
        retried = row["action"] == "retry_scheduled" and row["entity_type"] == "order"
        if started is None and (retried or row["action"] == "warehouse_unreachable"):
            started = row["ts"]
        elif started and row["action"] in WAREHOUSE_ANSWERED:
            longest = max(longest, seconds_between(started, row["ts"]))
            started = None
    if started:
        end = min(until, ranges.stamp(datetime.now(UTC)))
        longest = max(longest, seconds_between(started, end))
    return round(longest / 60)


def parts(rows: list[dict], found: dict[str, Trip], steps: dict, until: str) -> dict:
    tally = Counter((channel_of(row), row["action"]) for row in rows)
    duplicates = Counter(channel_of(row) for row in rows if duplicate(row))
    orders = Counter(trip.channel for trip in found.values())
    seconds = [trip.seconds for trip in found.values() if trip.reserved]
    retries = [row for row in rows if row["action"] == "retry_scheduled"]
    slowdowns = [row for row in retries if row["entity_id"] == "emag"]
    sent = steps["sent"]
    return {
        "shop": {
            "orders": orders["shop"],
            "duplicates": duplicates["shop"],
            "refused": tally["shop", "signature_rejected"] + tally["shop", "event_rejected"],
        },
        "emag": {
            "orders": orders["emag"],
            "renotified": duplicates["emag"],
            "slowdowns": sum(1 for row in slowdowns if row["detail"].get("problem") == "HTTP 429"),
            "refused_updates": tally["emag", "stock_push_failed"],
            "sold_out": tally["emag", "unfulfillable"],
        },
        "glue": {
            "handled": steps["received"],
            "duplicates": steps["duplicates"],
            "p50_seconds": percentile(seconds, 0.5),
            "p95_seconds": percentile(seconds, 0.95),
            "lost": 0,
        },
        "warehouse": {
            "received": sent,
            "first_try_pct": round(steps["first_try"] / sent * 100, 1) if sent else 0.0,
            "retries": sum(1 for row in retries if row["entity_type"] == "order"),
            "failed": steps["failed"],
            "longest_outage_minutes": longest_outage_minutes(rows, until),
        },
    }


def by_product(found: dict[str, Trip]) -> list[dict]:
    groups: dict[str, list[Trip]] = defaultdict(list)
    for trip in found.values():
        groups[trip.sku].append(trip)
    rows = [
        {
            "sku": sku,
            "product": product_name(sku),
            "orders": len(group),
            "reserved": sum(1 for trip in group if trip.reserved),
            "failed": sum(1 for trip in group if trip.outcome == "failed"),
            "p50_seconds": percentile([trip.seconds for trip in group if trip.reserved], 0.5),
        }
        for sku, group in groups.items()
    ]
    return sorted(rows, key=lambda row: (-row["orders"], row["sku"]))


def report(ctx: Context, window: ranges.Window, compare: bool) -> dict:
    rows = ctx.db.audit_between(window.since, window.until)
    found = trips(rows)
    for order in ctx.db.orders_in(list(found)):
        if order["lines"]:
            found[order["order_id"]].sku = order["lines"][0]["sku"]
    keys = bucket_keys(window)
    steps = funnel(rows, found)
    previous = queries.counters(ctx, *ranges.bounds(window.previous)) if compare else None
    opened = [row["detail"] for row in rows if row["action"] == "review_opened"]
    return {
        "range": {
            "since": window.since,
            "until": window.until,
            "unit": window.unit,
            "labels": labels(keys, window.unit),
        },
        "totals": queries.counters(ctx, window.since, window.until),
        "previous": previous,
        "funnel": steps,
        "series": series(rows, found, keys, window.unit),
        "parts": parts(rows, found, steps, window.until),
        "by_product": by_product(found),
        "failure_causes": queries.review_groups(opened),
        "sample": any(row["detail"].get("sample") is True for row in rows),
    }


def csv_rows(ctx: Context, window: ranges.Window) -> list[list]:
    rows = ctx.db.audit_between(window.since, window.until)
    keys = bucket_keys(window)
    charts = series(rows, trips(rows), keys, window.unit)
    shop, emag = charts["orders"]["shop"], charts["orders"]["emag"]
    retried, failed = charts["problems"]["retried"], charts["problems"]["failed"]
    lines = [["bucket", "orders", "retried", "failed"]]
    for i, label in enumerate(labels(keys, window.unit)):
        lines.append([label, shop[i] + emag[i], retried[i], failed[i]])
    lines.append(["total", sum(shop) + sum(emag), sum(retried), sum(failed)])
    return lines
