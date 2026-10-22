from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Annotated, Literal

from fastapi import Query
from fastapi.exceptions import RequestValidationError

DAY = timedelta(days=1)
UNITS = {"live": "minute", "today": "hour", "week": "day", "month": "day", "custom": "day"}


@dataclass(frozen=True)
class Window:
    since: str
    until: str
    unit: Literal["minute", "hour", "day"]
    previous: "Window | None" = None


def stamp(moment: datetime) -> str:
    return moment.isoformat(timespec="milliseconds")


def custom_days(from_: str | None, to: str | None) -> tuple[datetime, datetime]:
    if not from_ or not to:
        raise ValueError("a custom range needs both from and to")
    first, last = date.fromisoformat(from_), date.fromisoformat(to)
    if first > last:
        raise ValueError("from must not be after to")
    return datetime.combine(first, time(), UTC), datetime.combine(last, time(), UTC) + DAY


def resolve(range: str, from_: str | None, to: str | None, now: datetime) -> Window:
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow = today + DAY
    if range == "live":
        since, until = now - timedelta(minutes=15), now
    elif range == "today":
        since, until = today, tomorrow
    elif range == "week":
        since, until = tomorrow - 7 * DAY, tomorrow
    elif range == "month":
        since, until = today.replace(day=1), tomorrow
    elif range == "custom":
        since, until = custom_days(from_, to)
    else:
        raise ValueError(f"unknown range {range!r}")
    unit = UNITS[range]
    previous = Window(stamp(since - (until - since)), stamp(since), unit)
    return Window(stamp(since), stamp(until), unit, previous)


def from_query(
    range: Literal["live", "today", "week", "month", "custom"] | None = None,
    from_: Annotated[str | None, Query(alias="from", max_length=10)] = None,
    to: Annotated[str | None, Query(max_length=10)] = None,
) -> Window | None:
    if range is None:
        return None
    # Dates near year 1 or 9999 overflow when the window or the one before it is computed.
    try:
        return resolve(range, from_, to, datetime.now(UTC))
    except (ValueError, OverflowError) as exc:
        error = {"type": "value_error", "loc": ("query", "range"), "msg": str(exc), "input": range}
        raise RequestValidationError([error]) from None


def bounds(window: Window | None) -> tuple[str, str]:
    return (window.since, window.until) if window else ("", "")
