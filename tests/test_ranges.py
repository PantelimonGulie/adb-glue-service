from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from glue import ranges
from glue.analytics_series import Trip, bucket_starts, labels, series

NOW = datetime(2026, 10, 22, 10, 30, 15, tzinfo=UTC)
BUCHAREST = ZoneInfo("Europe/Bucharest")


def resolve(name: str, from_: str | None = None, to: str | None = None, now: datetime = NOW):
    return ranges.resolve(name, from_, to, now, BUCHAREST)


def test_live_is_15_minutes():
    window = resolve("live")

    assert (window.since, window.until) == (
        "2026-10-22T10:15:15.000+00:00",
        "2026-10-22T10:30:15.000+00:00",
    )
    assert window.unit == "minute"


def test_today_starts_at_midnight_in_bucharest():
    window = resolve("today")

    # 00:00 in Bucharest is 21:00 UTC the evening before while summer time lasts.
    assert (window.since, window.until) == (
        "2026-10-21T21:00:00.000+00:00",
        "2026-10-22T21:00:00.000+00:00",
    )
    assert window.previous.since == "2026-10-20T21:00:00.000+00:00"


def test_an_order_at_half_past_midnight_counts_for_that_day():
    window = resolve("week")
    starts = bucket_starts(window, BUCHAREST)
    # 00:30 on 22 October in Bucharest, still 21 October in UTC.
    found = {"shop-1": Trip("shop", "2026-10-21T21:30:00.000+00:00")}

    orders = series([], found, starts)["orders"]["shop"]

    assert labels(starts, "day", BUCHAREST)[-1] == "2026-10-22"
    assert orders[-1] == 1


def test_the_day_the_clocks_go_back_has_25_hours():
    window = resolve("today", now=datetime(2026, 10, 25, 12, 0, tzinfo=UTC))
    starts = bucket_starts(window, BUCHAREST)

    assert (window.since, window.until) == (
        "2026-10-24T21:00:00.000+00:00",
        "2026-10-25T22:00:00.000+00:00",
    )
    assert len(starts) == 25
    assert labels(starts, "hour", BUCHAREST)[:5] == ["00:00", "01:00", "02:00", "03:00", "03:00"]
    # Yesterday is a whole day of 24 hours, not the 25 hours just before today.
    assert window.previous.since == "2026-10-23T21:00:00.000+00:00"


def test_month_starts_on_first():
    window = resolve("month")

    assert (window.since, window.until) == (
        "2026-09-30T21:00:00.000+00:00",
        "2026-10-22T21:00:00.000+00:00",
    )
    assert window.unit == "day"


def test_custom_days_are_bucharest_days_across_the_clock_change():
    window = resolve("custom", "2026-10-24", "2026-10-26")
    starts = bucket_starts(window, BUCHAREST)

    assert (window.since, window.until) == (
        "2026-10-23T21:00:00.000+00:00",
        "2026-10-26T22:00:00.000+00:00",
    )
    assert starts == [
        "2026-10-23T21:00:00.000+00:00",
        "2026-10-24T21:00:00.000+00:00",
        "2026-10-25T22:00:00.000+00:00",
    ]
    assert labels(starts, "day", BUCHAREST) == ["2026-10-24", "2026-10-25", "2026-10-26"]


async def test_custom_range_validation(systems):
    with pytest.raises(ValueError):
        resolve("custom", "2026-10-10", "2026-10-01")
    with pytest.raises(ValueError):
        resolve("custom", "2026-13-01", "2026-10-01")
    with pytest.raises(ValueError):
        resolve("custom", None, "2026-10-01")

    response = await systems.http.get(
        "http://glue/api/overview",
        params={"range": "custom", "from": "2026-10-10", "to": "2026-10-01"},
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["query", "range"]


def test_custom_range_is_capped_at_a_year():
    leap_year = resolve("custom", "2024-01-01", "2024-12-31")

    with pytest.raises(ValueError, match="at most a year"):
        resolve("custom", "2024-01-01", "2025-01-01")
    assert leap_year.until == "2024-12-31T22:00:00.000+00:00"


@pytest.mark.parametrize("name", ["live", "today", "week", "month", "custom"])
def test_previous_window_same_length(name):
    window = resolve(name, "2026-10-01", "2026-10-07")
    since, until = (datetime.fromisoformat(t) for t in (window.since, window.until))
    before = window.previous
    previous_since, previous_until = (
        datetime.fromisoformat(t) for t in (before.since, before.until)
    )

    assert before.until == window.since
    assert previous_until - previous_since == until - since
    assert before.unit == window.unit


async def test_me_names_the_business_timezone(systems):
    me = await systems.http.get("http://glue/api/me")

    assert me.json()["timezone"] == "Europe/Bucharest"


def test_exact_window_is_stored_as_utc_stamps():
    assert ranges.exact("2026-10-22T13:00:00Z", "2026-10-22T16:00:00.5+02:00") == (
        "2026-10-22T13:00:00.000+00:00",
        "2026-10-22T14:00:00.500+00:00",
    )
    assert ranges.exact("2026-10-22T13:00", "2026-10-22T13:01")[0] == (
        "2026-10-22T13:00:00.000+00:00"
    )


@pytest.mark.parametrize(
    ("since", "until", "message"),
    [
        ("2026-10-22T14:00:00Z", "2026-10-22T13:00:00Z", "before"),
        ("yesterday", "2026-10-22T13:00:00Z", "not an ISO timestamp"),
        ("2025-01-01T00:00:00Z", "2026-01-03T00:00:00Z", "at most a year"),
        ("2026-10-22T13:00:00Z", None, "together"),
    ],
)
def test_exact_window_validation(since, until, message):
    with pytest.raises(ValueError, match=message):
        ranges.exact(since, until)
