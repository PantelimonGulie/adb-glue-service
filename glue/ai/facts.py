import re
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from common.catalog import PRODUCTS, product_name
from glue import queries, ranges, review
from glue.context import Context

# The words the dashboard uses, so answers read like the rest of it.
STATES = {
    "ok": "working",
    "slow": "slow",
    "rate_limited": "limiting requests",
    "down": "not answering",
}
SYSTEMS = {
    "shop": "the shop (Electronic Market)",
    "emag": "eMAG",
    "warehouse": "the Bucharest warehouse",
}
CHANNELS = {"shop": "the shop", "emag": "eMAG"}
CAUSES = {
    "outage": "warehouse outage",
    "soldout": "sold on the other channel",
    "recount": "shelf count too low",
    "other": "other problem",
}
STATUSES = {
    "received": "received, not reserved yet",
    "allocated": "reserved at the warehouse",
    "shipped": "shipped",
    "failed": "failed, waiting for a person",
    "cancelled": "cancelled",
}
STOCK_STATES = {
    "in_sync": "both channels show what Glue last sent them",
    "behind": "a channel has not been told the latest figure yet",
    "refused": "eMAG refused the last stock update",
    "held": "a rule holds some units back on a channel",
}
# A long outage can fail many orders in an hour; the newest are enough to answer from.
FAILED_SHOWN = 10
STAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?\+00:00")


def local(moment: datetime, zone: ZoneInfo) -> str:
    return moment.astimezone(zone).strftime("%d %b %H:%M:%S").lstrip("0")


def plural(count: int, word: str) -> str:
    return f"{count} {word}{'' if count == 1 else 's'}"


def told(ctx: Context, row: dict, channel: str) -> str:
    sent, held = row[channel], row["held_back"][channel]
    if sent is None:
        return "not told yet"
    if sent["dirty"]:
        shown = ctx.db.last_taken(channel, row["sku"])
        still = "an older figure" if shown is None else shown
        return f"refused the update to {sent['qty']}, so it still shows {still}"
    return f"shows {sent['qty']}" + (f" ({held} held back by a rule)" if held else "")


def stock_lines(ctx: Context) -> list[str]:
    # Every product, in step or not: with no line for a product, a small model makes one up.
    return ["- Stock (free to sell at the warehouse; what Glue last sent each channel):"] + [
        f"  - {row['product']}: {row['free']} free; the shop {told(ctx, row, 'shop')};"
        f" eMAG {told(ctx, row, 'emag')};"
        f" {'in step' if row['state'] in ('in_sync', 'held') else 'out of step'}."
        for row in queries.stock_rows(ctx)
    ]


def failed_lines(ctx: Context, since: str) -> list[str]:
    failed = ctx.db.failed_since(since)
    if not failed:
        return ["- No order failed in the last hour."]
    newest = f"; the newest {FAILED_SHOWN}" if len(failed) > FAILED_SHOWN else ""
    return [
        f"- {plural(len(failed), 'order')} that came in during the last hour failed{newest}:"
    ] + [
        f"  - {row['order_id']} from {CHANNELS[row['channel']]}, {products(row['lines'])}."
        f" Cause: {CAUSES[review.cause_of(row)]}. Now: {STATUSES[row['status']]}."
        for row in failed[:FAILED_SHOWN]
    ]


async def live(ctx: Context) -> str:
    # A small model answers "is X working?" or "what failed?" from these lines more reliably
    # than by choosing and reading tools. Each count says what it counts: a bare "120 retried"
    # next to "1 failed" was read as one order tried 120 times. Failed orders come after the
    # stock: placed before it, a failed MacBook order was taken as the MacBook's stock answer.
    now = datetime.now(UTC)
    since = ranges.stamp(now - timedelta(hours=1))
    health = await queries.health_of(ctx)
    counts = queries.counters(ctx, since, "")
    groups = queries.review_groups(ctx.db.list_review())
    waiting = ", ".join(f"{g['count']} {CAUSES[g['cause']]}" for g in groups) or "nothing"
    systems = "; ".join(f"{SYSTEMS[name]}: {STATES[h['state']]}" for name, h in health.items())
    return "\n".join(
        [
            f"Live facts at {local(now, ctx.settings.zone)}, Bucharest time:",
            f"- Systems: {systems}.",
            f"- Waiting for a person: {waiting}.",
            f"- In the last hour {plural(counts['received'], 'order')} came in;"
            f" {counts['reserved']} of them were reserved at the warehouse.",
            f"- Glue retried {plural(counts['retries'], 'call')} in the last hour,"
            " across all orders and systems.",
            f"- Glue ignored {plural(counts['duplicates'], 'duplicate message')} in the last hour.",
            *stock_lines(ctx),
            *failed_lines(ctx, since),
        ]
    )


def readable(text: str, zone: ZoneInfo) -> str:
    # Whatever a tool returns reaches the model with product names and Bucharest times only.
    for code, name in PRODUCTS.items():
        text = text.replace(code, name)
    text = text.replace('"skus"', '"products"').replace('"sku"', '"product"')
    return STAMP.sub(lambda found: local(datetime.fromisoformat(found.group()), zone), text)


def products(lines: list[dict]) -> str:
    return ", ".join(f"{line['qty']} × {product_name(line['sku'])}" for line in lines)


def order(row: dict) -> dict:
    return {
        "order": row["order_id"],
        "channel": CHANNELS[row["channel"]],
        "products": products(row["lines"]),
        "status": STATUSES[row["status"]],
        "problem": row["last_error"],
        "came in": row["received_at"],
    }
