from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from fastapi import Query, Request
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
    return moment.astimezone(UTC).isoformat(timespec="milliseconds")


def today(zone: ZoneInfo) -> str:
    return datetime.now(zone).date().isoformat()


def midnight(day: date, zone: ZoneInfo) -> datetime:
    return datetime.combine(day, time(), zone)


def custom_days(from_: str | None, to: str | None, zone: ZoneInfo) -> tuple[datetime, datetime]:
    if not from_ or not to:
        raise ValueError("a custom range needs both from and to")
    first, last = date.fromisoformat(from_), date.fromisoformat(to)
    if first > last:
        raise ValueError("from must not be after to")
    if last - first >= timedelta(days=366):
        raise ValueError("a custom range can cover at most a year")
    return midnight(first, zone), midnight(last + DAY, zone)


def resolve(range: str, from_: str | None, to: str | None, now: datetime, zone: ZoneInfo) -> Window:
    # Days are the business's own: they start at midnight where it trades, not in UTC.
    today = now.astimezone(zone).date()
    tomorrow = midnight(today + DAY, zone)
    if range == "live":
        since, until = now - timedelta(minutes=15), now
    elif range == "today":
        since, until = midnight(today, zone), tomorrow
    elif range == "week":
        since, until = midnight(today - 6 * DAY, zone), tomorrow
    elif range == "month":
        since, until = midnight(today.replace(day=1), zone), tomorrow
    elif range == "custom":
        since, until = custom_days(from_, to, zone)
    else:
        raise ValueError(f"unknown range {range!r}")
    unit = UNITS[range]
    # Both ends share one zone, so this steps back by calendar days: the day before a 25-hour
    # day is still a whole day.
    previous = Window(stamp(since - (until - since)), stamp(since), unit)
    return Window(stamp(since), stamp(until), unit, previous)


def from_query(
    request: Request,
    range: Literal["live", "today", "week", "month", "custom"] | None = None,
    from_: Annotated[str | None, Query(alias="from", max_length=10)] = None,
    to: Annotated[str | None, Query(max_length=10)] = None,
) -> Window | None:
    if range is None:
        return None
    # Dates near year 1 or 9999 overflow when the window or the one before it is computed.
    try:
        return resolve(range, from_, to, datetime.now(UTC), request.app.state.settings.zone)
    except (ValueError, OverflowError) as exc:
        error = {"type": "value_error", "loc": ("query", "range"), "msg": str(exc), "input": range}
        raise RequestValidationError([error]) from None


def instant(text: str) -> datetime:
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        raise ValueError(f"{text!r} is not an ISO timestamp") from None
    # Without an offset the time is taken as UTC, like every time the API returns.
    return moment.replace(tzinfo=UTC) if moment.tzinfo is None else moment.astimezone(UTC)


def exact(since: str | None, until: str | None) -> tuple[str, str]:
    if not since or not until:
        raise ValueError("since and until go together")
    start, end = instant(since), instant(until)
    if start >= end:
        raise ValueError("since must be before until")
    if end - start > timedelta(days=366):
        raise ValueError("a window can cover at most a year")
    # The same format as the stored timestamps, so the database can compare them as text.
    return stamp(start), stamp(end)


def exact_query(
    since: Annotated[str | None, Query(max_length=40)] = None,
    until: Annotated[str | None, Query(max_length=40)] = None,
) -> tuple[str, str] | None:
    if since is None and until is None:
        return None
    try:
        return exact(since, until)
    except (ValueError, OverflowError) as exc:
        error = {"type": "value_error", "loc": ("query", "since"), "msg": str(exc), "input": since}
        raise RequestValidationError([error]) from None


def bounds(window: Window | None) -> tuple[str, str]:
    return (window.since, window.until) if window else ("", "")
