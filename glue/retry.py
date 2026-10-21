import asyncio
import random
from collections.abc import Awaitable, Callable

import httpx

from glue.context import Context

RETRYABLE_STATUSES = {408, 429}


class RetryExhausted(Exception):
    def __init__(self, problem: str, attempts: int):
        super().__init__(f"{problem} after {attempts} attempts")
        self.problem = problem
        self.attempts = attempts


def retryable(response: httpx.Response) -> bool:
    return response.status_code in RETRYABLE_STATUSES or response.status_code >= 500


async def send_with_retries(
    send: Callable[[], Awaitable[httpx.Response]],
    *,
    attempts: int,
    base_seconds: float,
    on_retry: Callable[[int, float, str], None] | None = None,
) -> httpx.Response:
    for attempt in range(1, attempts + 1):
        retry_after = None
        try:
            response = await send()
        except httpx.TransportError as exc:
            problem = f"{type(exc).__name__}: {exc}"
        else:
            if not retryable(response):
                return response
            problem = f"HTTP {response.status_code}"
            retry_after = response.headers.get("Retry-After")
        if attempt == attempts:
            raise RetryExhausted(problem, attempts)
        if retry_after:
            delay = float(retry_after)
        else:
            delay = base_seconds * 2 ** (attempt - 1) * (1 + 0.2 * random.random())
        if on_retry:
            on_retry(attempt, delay, problem)
        await asyncio.sleep(delay)


async def with_retries(
    ctx: Context,
    send: Callable[[], Awaitable[httpx.Response]],
    on_retry: Callable[[int, float, str], None] | None = None,
) -> httpx.Response:
    return await send_with_retries(
        send,
        attempts=ctx.settings.retry_attempts,
        base_seconds=ctx.settings.retry_base_seconds,
        on_retry=on_retry,
    )
