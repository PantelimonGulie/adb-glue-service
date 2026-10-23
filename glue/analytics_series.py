from bisect import bisect_right
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from glue.queries import CHANNELS, COUNTERS
from glue.ranges import DAY, Window, midnight, stamp

STEP = {"minute": timedelta(minutes=1), "hour": timedelta(hours=1)}
LABEL = {"minute": "%H:%M", "hour": "%H:00", "day": "%Y-%m-%d"}


def seconds_between(start: str, end: str) -> float:
    return (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds()


@dataclass
class Trip:
    channel: str
    received: str
    reserved: str | None = None
    retried: bool = False
    failed: bool = False
    sku: str = ""

    @property
    def outcome(self) -> str | None:
        if self.reserved:
            return "after_retry" if self.retried or self.failed else "first_try"
        return "failed" if self.failed else None

    @property
    def seconds(self) -> float:
        return seconds_between(self.received, self.reserved)


def placement(row: dict) -> bool:
    # Same rule as db.PLACEMENT.
    return row["detail"].get("type") == "order.placed" or row["entity_id"].endswith("-new")


def system_of(row: dict) -> str:
    # Retries saved before they named their system: on an order they were warehouse placements.
    detail = row["detail"]
    return detail.get("system") or (
        "warehouse" if row["entity_type"] == "order" else row["entity_id"]
    )


def warehouse_retry(row: dict) -> bool:
    return row["action"] == "retry_scheduled" and system_of(row) == "warehouse"


def duplicate(row: dict) -> bool:
    # Order placements only, like the funnel's "received"; a repeated cancel is not one.
    return row["action"] == "order_known" or (
        row["action"] == "duplicate_dropped" and placement(row)
    )


def trips(rows: list[dict]) -> dict[str, Trip]:
    # An inbound event row names the event, not the order; the order rows it caused share
    # its correlation id.
    order_of: dict[str, str] = {}
    for row in rows:
        if row["entity_type"] == "order" and row["entity_id"].startswith(("shop-", "emag-")):
            order_of.setdefault(row["correlation_id"], row["entity_id"])
    found: dict[str, Trip] = {}
    for row in rows:
        order_id = order_of.get(row["correlation_id"])
        if row["action"] == "event_received" and order_id and placement(row):
            found.setdefault(order_id, Trip(order_id.split("-")[0], row["ts"]))
        trip = found.get(row["entity_id"])
        if trip is None or trip.reserved or row["entity_type"] != "order":
            continue
        if row["action"] == "order_allocated":
            trip.reserved = row["ts"]
        elif warehouse_retry(row):
            trip.retried = True
        elif row["action"] in COUNTERS["failed"]:
            trip.failed = True
    return found


def bucket_starts(window: Window, zone: ZoneInfo) -> list[str]:
    # UTC stamps like the stored times, so a time finds its bucket by comparing text. Days are
    # local days, 23 or 25 hours long when the clocks change.
    since = datetime.fromisoformat(window.since).astimezone(zone)
    until = datetime.fromisoformat(window.until)
    starts = []
    if window.unit == "day":
        day = since.date()
        while (moment := midnight(day, zone)) < until:
            starts.append(stamp(moment))
            day += DAY
        return starts
    whole = {"minute": 0} if window.unit == "hour" else {}
    moment = since.replace(second=0, microsecond=0, **whole).astimezone(UTC)
    while moment < until:
        starts.append(stamp(moment))
        moment += STEP[window.unit]
    return starts


def labels(starts: list[str], unit: str, zone: ZoneInfo) -> list[str]:
    return [
        datetime.fromisoformat(start).astimezone(zone).strftime(LABEL[unit]) for start in starts
    ]


def percentile(values: list[float], share: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * share
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    return round(ordered[low] + (ordered[high] - ordered[low]) * (position - low), 2)


def series(rows: list[dict], found: dict[str, Trip], keys: list[str]) -> dict:
    def index(ts: str) -> int:
        return bisect_right(keys, ts) - 1

    orders = {channel: [0] * len(keys) for channel in CHANNELS}
    seconds: list[list[float]] = [[] for _ in keys]
    for trip in found.values():
        i = index(trip.received)
        orders[trip.channel][i] += 1
        if trip.reserved:
            seconds[i].append(trip.seconds)
    retried, failed = [0] * len(keys), [0] * len(keys)
    unsynced: dict[str, list[set]] = {channel: [set() for _ in keys] for channel in CHANNELS}
    for row in rows:
        i = index(row["ts"])
        if row["action"] in COUNTERS["retries"]:
            retried[i] += 1
        elif row["action"] in COUNTERS["failed"]:
            failed[i] += 1
        elif row["action"] == "stock_push_failed":
            unsynced[row["detail"]["channel"]][i].add(row["entity_id"])
    return {
        "orders": orders,
        "problems": {"retried": retried, "failed": failed},
        "latency": {
            "p50": [percentile(values, 0.5) for values in seconds],
            "p95": [percentile(values, 0.95) for values in seconds],
        },
        "out_of_sync": {ch: [len(skus) for skus in unsynced[ch]] for ch in CHANNELS},
    }
