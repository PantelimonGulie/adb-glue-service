import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from glue.ranges import stamp

SKUS = {"APP-3": 6, "IPH16-128": 5, "IPH16-256": 3, "IPAD-A16": 3, "WATCH-S10": 2, "MBA-M4": 1}
SCARCE = ("MBA-M4", "IPH16-256")
EVENTS = {
    "shop": {"source": "shop", "type": "order.placed"},
    "emag": {"source": "emag", "type": "emag.notification"},
}
CUSTOMERS = {"shop": "Guest", "emag": "eMAG customer"}
ATTEMPTS = 5
REASONS = {
    "order_failed": f"the Bucharest warehouse is not answering (tried {ATTEMPTS} times)",
    "unfulfillable": "warehouse has no stock: sold on another channel first",
}


@dataclass
class History:
    rng: random.Random
    now: datetime
    outages: list[tuple[datetime, datetime]] = field(default_factory=list)
    audit: list[dict] = field(default_factory=list)
    orders: list[dict] = field(default_factory=list)

    def log(
        self,
        at: datetime,
        correlation_id: str,
        entity_type: str,
        entity_id: str,
        action: str,
        **detail,
    ) -> None:
        row = {"ts": stamp(at), "correlation_id": correlation_id, "entity_type": entity_type}
        row |= {"entity_id": entity_id, "action": action, "detail": detail | {"sample": True}}
        self.audit.append(row)

    def event(self, at: datetime, event_id: str, action: str, **detail) -> None:
        self.log(at, event_id, "event", event_id, action, **detail)

    def order(
        self, at: datetime, correlation_id: str, order_id: str, action: str, **detail
    ) -> None:
        self.log(at, correlation_id, "order", order_id, action, **detail)

    def later(self, at: datetime, low: float, high: float) -> datetime:
        return at + timedelta(seconds=self.rng.uniform(low, high))

    def down_until(self, at: datetime) -> datetime | None:
        return next((end for start, end in self.outages if start <= at < end), None)

    def event_id(self) -> str:
        return f"sample-{self.rng.getrandbits(48):012x}"


def send(
    h: History, event_id: str, order_id: str, at: datetime
) -> tuple[datetime, int, datetime | None]:
    at, attempt = h.later(at, 0.2, 1.2), 1
    down = h.down_until(at)
    blips = h.rng.choice((1, 2)) if not down and h.rng.random() < 0.02 else 0
    while attempt < ATTEMPTS and ((down and at < down) or attempt <= blips):
        # A down warehouse sends Retry-After: 2; a single failed call gets the doubling backoff.
        delay = 2.0 if down else 0.5 * 2 ** (attempt - 1) * (1 + 0.2 * h.rng.random())
        retry = {"system": "warehouse", "attempt": attempt, "delay_seconds": round(delay, 1)}
        retry |= {"problem": "the Bucharest warehouse is not answering", "error": "HTTP 503"}
        h.order(at, event_id, order_id, "retry_scheduled", **retry)
        at += timedelta(seconds=delay)
        attempt += 1
    # The outage end when the order gave up during one.
    return at, attempt, down if down and at < down else None


def review(
    h: History, order_id: str, lines: list, kind: str, after: datetime
) -> tuple[str, datetime]:
    decided = h.later(after, 120, 2400)
    if decided >= h.now:
        return "failed", after
    decision = "retry" if kind == "order_failed" and h.rng.random() < 0.7 else "cancel"
    review_id = f"sample-review-{order_id}"
    verdict = {"kind": kind, "decision": decision, "decided_by": "operator"}
    h.order(decided, review_id, order_id, "review_decided", **verdict)
    done = h.later(decided, 0.2, 1.5)
    if decision == "retry":
        h.order(done, review_id, order_id, "order_allocated", lines=lines)
        return "allocated", done
    h.order(done, review_id, order_id, "order_cancelled", was="failed")
    return "cancelled", done


def ship(h: History, channel: str, order_id: str, reserved: datetime) -> datetime:
    at = reserved + min(timedelta(hours=h.rng.uniform(0.5, 20)), (h.now - reserved) * 0.9)
    at = h.down_until(at) or at
    event_id = h.event_id()
    h.event(at, event_id, "event_received", source="warehouse", type="order.shipped")
    at = h.later(at, 0.1, 0.6)
    h.order(at, event_id, order_id, "order_shipped", channel=channel, channel_response=200)
    return at


def place(h: History, channel: str, at: datetime) -> None:
    number = 1001 + len(h.orders)
    order_id = f"{channel}-sample-{number}"
    lines = [{"sku": h.rng.choices(list(SKUS), list(SKUS.values()))[0], "qty": 1}]
    event_id = h.event_id() if channel == "shop" else f"sample-emag-notify-{number}-new"
    h.event(at, event_id, "event_received", **EVENTS[channel])
    received = stamp(at)
    if h.rng.random() < 0.03:
        h.event(h.later(at, 2, 40), event_id, "duplicate_dropped", **EVENTS[channel])
    at, attempts, outage_end = send(h, event_id, order_id, at)
    kind = None
    if outage_end:
        kind = "order_failed"
    elif lines[0]["sku"] in SCARCE and h.rng.random() < 0.04:
        kind = "unfulfillable"
    else:
        h.order(at, event_id, order_id, "order_allocated", lines=lines)
    if channel == "emag":
        h.order(h.later(at, 0.05, 0.3), event_id, order_id, "emag_acknowledged")
    status, last = "allocated", at
    if kind:
        h.order(at, event_id, order_id, kind, reason=REASONS[kind])
        h.order(at, event_id, order_id, "review_opened", kind=kind, reason=REASONS[kind])
        status, last = review(h, order_id, lines, kind, outage_end or at)
    if status == "allocated":
        status, last = "shipped", ship(h, channel, order_id, last)
    order = {"order_id": order_id, "channel": channel, "channel_order_id": f"sample-{number}"}
    order |= {"lines": lines, "customer": CUSTOMERS[channel], "status": status}
    error = REASONS[kind] if kind and status != "shipped" else None
    order |= {"attempts": attempts, "last_error": error, "received_at": received}
    h.orders.append(order | {"updated_at": stamp(last)})
