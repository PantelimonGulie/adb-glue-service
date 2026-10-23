from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime

import httpx
import pytest

from glue.retry import (
    MAX_RETRY_AFTER_SECONDS,
    RetryExhausted,
    retry_after_seconds,
    send_with_retries,
)


def scripted(*replies: httpx.Response | Exception) -> Callable[[], Awaitable[httpx.Response]]:
    queue = list(replies)

    async def send() -> httpx.Response:
        reply = queue.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply

    return send


async def test_retry_after_is_honoured_and_backoff_doubles(sleeps):
    send = scripted(
        httpx.Response(429, headers={"Retry-After": "1"}),
        httpx.ConnectError("connection refused"),
        httpx.Response(200),
    )

    response = await send_with_retries(send, attempts=5, base_seconds=0.5)

    assert response.status_code == 200
    assert sleeps[0] == 1.0
    assert 1.0 <= sleeps[1] <= 1.2


@pytest.mark.parametrize("status", [400, 409])
async def test_client_errors_are_returned_without_retrying(sleeps, status):
    response = await send_with_retries(scripted(httpx.Response(status)), attempts=5, base_seconds=0)

    assert response.status_code == status
    assert sleeps == []


async def test_exhausted_retries_raise(sleeps):
    send = scripted(*[httpx.Response(503)] * 3)

    with pytest.raises(RetryExhausted) as caught:
        await send_with_retries(send, attempts=3, base_seconds=0)

    assert str(caught.value) == "the Bucharest warehouse is not answering (tried 3 times)"
    assert (caught.value.error, caught.value.attempts) == ("HTTP 503", 3)
    assert len(sleeps) == 2


@pytest.mark.parametrize(
    ("reply", "system", "problem"),
    [
        (
            httpx.ReadTimeout("timed out"),
            "warehouse",
            "the Bucharest warehouse took too long to answer",
        ),
        (httpx.ConnectError("refused"), "shop", "the shop could not be reached"),
        (httpx.Response(429), "emag", "eMAG asked Glue to slow down"),
        (httpx.Response(500), "emag", "eMAG is not answering"),
    ],
)
async def test_each_retry_is_described_in_plain_words(sleeps, reply, system, problem):
    seen = []
    send = scripted(reply, httpx.Response(200))

    await send_with_retries(
        send, system=system, attempts=2, base_seconds=0.5, on_retry=lambda *a: seen.append(a)
    )

    [(attempt, delay, trouble)] = seen
    assert (attempt, trouble.problem) == (1, problem)
    assert delay == sleeps[0]
    assert type(reply).__name__ not in trouble.problem


def http_date(seconds_from_now: int) -> str:
    return format_datetime(datetime.now(UTC) + timedelta(seconds=seconds_from_now), usegmt=True)


async def first_delay(sleeps: list[float], retry_after: str) -> float:
    send = scripted(httpx.Response(503, headers={"Retry-After": retry_after}), httpx.Response(200))
    await send_with_retries(send, attempts=2, base_seconds=0.5)
    return sleeps[-1]


async def test_retry_after_as_an_http_date_waits_until_then(sleeps):
    delay = await first_delay(sleeps, http_date(10))

    assert 8 < delay <= 10


@pytest.mark.parametrize("retry_after", ["86400", http_date(86400)], ids=["seconds", "date"])
async def test_a_long_retry_after_is_capped(sleeps, retry_after):
    assert await first_delay(sleeps, retry_after) == MAX_RETRY_AFTER_SECONDS


@pytest.mark.parametrize("retry_after", ["soon", "-5", "1.5", "nan", "Wed, 99 Foo 2026"])
async def test_an_unreadable_retry_after_falls_back_to_backoff(sleeps, retry_after):
    assert 0.5 <= await first_delay(sleeps, retry_after) <= 0.6


async def test_a_retry_after_date_in_the_past_retries_at_once(sleeps):
    assert await first_delay(sleeps, http_date(-60)) == 0


def test_a_digit_that_is_not_a_plain_number_is_unreadable():
    # str.isdigit() accepts "²", which float() refuses.
    assert retry_after_seconds("²") is None
