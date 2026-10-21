from collections.abc import Awaitable, Callable

import httpx
import pytest

from glue.retry import RetryExhausted, send_with_retries


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

    assert (caught.value.problem, caught.value.attempts) == ("HTTP 503", 3)
    assert len(sleeps) == 2
