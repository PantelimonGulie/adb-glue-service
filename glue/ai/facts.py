import re
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from common.catalog import PRODUCTS, product_name
from glue import queries, ranges
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


def stock_line(ctx: Context) -> str:
    rows = [row for row in queries.stock_rows(ctx) if row["state"] != "in_sync"]
    if not rows:
        return f"- Stock: {STOCK_STATES['in_sync']}."
    differ = "; ".join(
        f"{row['product']}, {row['free']} free: the shop {told(ctx, row, 'shop')};"
        f" eMAG {told(ctx, row, 'emag')}"
        for row in rows
    )
    return f"- Stock not in step: {differ}."


async def live(ctx: Context) -> str:
    # A small model answers "is X working?" or "what failed?" from these lines more reliably
    # than by choosing and reading tools.
    now = datetime.now(UTC)
    health = await queries.health_of(ctx)
    counts = queries.counters(ctx, ranges.stamp(now - timedelta(hours=1)), "")
    groups = queries.review_groups(ctx.db.list_review())
    waiting = ", ".join(f"{g['count']} {CAUSES[g['cause']]}" for g in groups) or "nothing"
    systems = "; ".join(f"{SYSTEMS[name]}: {STATES[h['state']]}" for name, h in health.items())
    hour = (
        f"{plural(counts['received'], 'order')} in, {counts['reserved']} reserved,"
        f" {counts['failed']} failed, {plural(counts['retries'], 'call')} retried,"
        f" {plural(counts['duplicates'], 'duplicate')} ignored"
    )
    return "\n".join(
        [
            f"Live facts at {local(now, ctx.settings.zone)}, Bucharest time:",
            f"- Systems: {systems}.",
            f"- Waiting for a person: {waiting}.",
            f"- Last hour: {hour}.",
            stock_line(ctx),
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
