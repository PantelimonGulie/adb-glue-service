from datetime import UTC, datetime

import pytest

from glue import ranges

NOW = datetime(2026, 10, 22, 10, 30, 15, tzinfo=UTC)


def test_live_is_15_minutes():
    window = ranges.resolve("live", None, None, NOW)

    assert (window.since, window.until) == (
        "2026-10-22T10:15:15.000+00:00",
        "2026-10-22T10:30:15.000+00:00",
    )
    assert window.unit == "minute"


def test_month_starts_on_first():
    window = ranges.resolve("month", None, None, NOW)

    assert (window.since, window.until) == (
        "2026-10-01T00:00:00.000+00:00",
        "2026-10-23T00:00:00.000+00:00",
    )
    assert window.unit == "day"


async def test_custom_range_validation(systems):
    with pytest.raises(ValueError):
        ranges.resolve("custom", "2026-10-10", "2026-10-01", NOW)
    with pytest.raises(ValueError):
        ranges.resolve("custom", "2026-13-01", "2026-10-01", NOW)
    with pytest.raises(ValueError):
        ranges.resolve("custom", None, "2026-10-01", NOW)

    response = await systems.http.get(
        "http://glue/api/overview",
        params={"range": "custom", "from": "2026-10-10", "to": "2026-10-01"},
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["query", "range"]


@pytest.mark.parametrize("name", ["live", "today", "week", "month", "custom"])
def test_previous_window_same_length(name):
    window = ranges.resolve(name, "2026-10-01", "2026-10-07", NOW)
    since, until = (datetime.fromisoformat(t) for t in (window.since, window.until))
    before = window.previous
    previous_since, previous_until = (
        datetime.fromisoformat(t) for t in (before.since, before.until)
    )

    assert before.until == window.since
    assert previous_until - previous_since == until - since
    assert before.unit == window.unit
