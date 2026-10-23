from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from glue.queries import CHANNELS, COUNTERS
from glue.ranges import Window

KEY_SIZE = {"minute": 16, "hour": 13, "day": 10}
STEP = {"minute": timedelta(minutes=1), "hour": timedelta(hours=1), "day": timedelta(days=1)}


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
        elif row["action"] == "retry_scheduled":
            trip.retried = True
        elif row["action"] in COUNTERS["failed"]:
            trip.failed = True
    return found


def bucket_keys(window: Window) -> list[str]:
    size = KEY_SIZE[window.unit]
    moment = datetime.fromisoformat(window.since[:size]).replace(tzinfo=UTC)
    until = datetime.fromisoformat(window.until)
    keys = []
    while moment < until:
        keys.append(moment.isoformat()[:size])
        moment += STEP[window.unit]
    return keys


def labels(keys: list[str], unit: str) -> list[str]:
    if unit == "minute":
        return [key[11:16] for key in keys]
    if unit == "hour":
        return [f"{key[11:13]}:00" for key in keys]
    return keys


def percentile(values: list[float], share: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * share
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    return round(ordered[low] + (ordered[high] - ordered[low]) * (position - low), 2)


def series(rows: list[dict], found: dict[str, Trip], keys: list[str], unit: str) -> dict:
    size = KEY_SIZE[unit]
    index = {key: i for i, key in enumerate(keys)}
    orders = {channel: [0] * len(keys) for channel in CHANNELS}
    seconds: list[list[float]] = [[] for _ in keys]
    for trip in found.values():
        i = index[trip.received[:size]]
        orders[trip.channel][i] += 1
        if trip.reserved:
            seconds[i].append(trip.seconds)
    retried, failed = [0] * len(keys), [0] * len(keys)
    unsynced: dict[str, list[set]] = {channel: [set() for _ in keys] for channel in CHANNELS}
    for row in rows:
        i = index[row["ts"][:size]]
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
