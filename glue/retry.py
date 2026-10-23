import asyncio
import random
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

import httpx

from glue.audit import record
from glue.context import Context

RETRYABLE_STATUSES = {408, 429}
# Waiting holds a worker slot; a longer outage is better left to the review queue.
MAX_RETRY_AFTER_SECONDS = 30
SYSTEMS = {"warehouse": "the Bucharest warehouse", "shop": "the shop", "emag": "eMAG"}
# What a failed call says about the system; the overview reports the same states.
STATES = {
    "slow": "took too long to answer",
    "rate_limited": "asked Glue to slow down",
    "unreachable": "could not be reached",
    "down": "is not answering",
}


class Problem(Exception):
    # A reason an operator can read; `error` keeps the technical detail for the audit log.
    def __init__(self, reason: str, error: str = ""):
        super().__init__(reason)
        self.error = error


def explained(exc: Exception) -> tuple[str, str]:
    # The reason an operator reads, and the technical detail the audit log keeps.
    if isinstance(exc, Problem):
        return str(exc), exc.error or str(exc)
    unexpected = "Glue hit an unexpected error; the details are in the activity log"
    return unexpected, f"{type(exc).__name__}: {exc}"


@dataclass(frozen=True)
class Trouble:
    system: str
    state: str
    error: str

    @property
    def problem(self) -> str:
        return f"{SYSTEMS[self.system]} {STATES[self.state]}"


class RetryExhausted(Problem):
    def __init__(self, trouble: Trouble, attempts: int):
        super().__init__(f"{trouble.problem} (tried {attempts} times)", trouble.error)
        self.trouble = trouble
        self.attempts = attempts


def retryable(response: httpx.Response) -> bool:
    return response.status_code in RETRYABLE_STATUSES or response.status_code >= 500


def trouble_of(system: str, reply: httpx.Response | httpx.TransportError) -> Trouble:
    if isinstance(reply, httpx.TransportError):
        error = f"{type(reply).__name__}: {reply}"
        if isinstance(reply, httpx.TimeoutException):
            return Trouble(system, "slow", error)
        return Trouble(
            system, "unreachable" if isinstance(reply, httpx.ConnectError) else "down", error
        )
    state = {408: "slow", 429: "rate_limited"}.get(reply.status_code, "down")
    return Trouble(system, state, f"HTTP {reply.status_code}")


def retry_after_seconds(header: str | None) -> float | None:
    # Seconds or an HTTP-date (RFC 9110); None for anything else, so back-off applies.
    if not header:
        return None
    if header.isdecimal():
        return min(float(header), MAX_RETRY_AFTER_SECONDS)
    try:
        seconds = (parsedate_to_datetime(header) - datetime.now(UTC)).total_seconds()
    except (TypeError, ValueError):
        return None
    return min(max(seconds, 0.0), MAX_RETRY_AFTER_SECONDS)


async def send_with_retries(
    send: Callable[[], Awaitable[httpx.Response]],
    *,
    attempts: int,
    base_seconds: float,
    system: str = "warehouse",
    on_retry: Callable[[int, float, Trouble], None] | None = None,
) -> httpx.Response:
    for attempt in range(1, attempts + 1):
        retry_after = None
        try:
            response = await send()
        except httpx.TransportError as exc:
            trouble = trouble_of(system, exc)
        else:
            if not retryable(response):
                return response
            trouble = trouble_of(system, response)
            retry_after = retry_after_seconds(response.headers.get("Retry-After"))
        if attempt == attempts:
            raise RetryExhausted(trouble, attempts)
        if retry_after is None:
            delay = base_seconds * 2 ** (attempt - 1) * (1 + 0.2 * random.random())
        else:
            delay = retry_after
        if on_retry:
            on_retry(attempt, delay, trouble)
        await asyncio.sleep(delay)


async def with_retries(
    ctx: Context,
    system: str,
    send: Callable[[], Awaitable[httpx.Response]],
    on_retry: Callable[[int, float, Trouble], None] | None = None,
) -> httpx.Response:
    def noted(attempt: int, delay: float, trouble: Trouble) -> None:
        ctx.trouble[system] = (trouble.state, time.monotonic())
        if on_retry:
            on_retry(attempt, delay, trouble)

    try:
        response = await send_with_retries(
            send,
            attempts=ctx.tuning.retry_attempts,
            base_seconds=ctx.tuning.retry_base_seconds,
            system=system,
            on_retry=noted,
        )
    except RetryExhausted as exc:
        ctx.trouble[system] = (exc.trouble.state, time.monotonic())
        raise
    # It answered, so whatever went wrong before is over.
    ctx.trouble.pop(system, None)
    return response


def retry_logger(
    ctx: Context, correlation_id: str, entity_type: str, entity_id: str, **extra: object
) -> Callable[[int, float, Trouble], None]:
    def on_retry(attempt: int, delay: float, trouble: Trouble) -> None:
        record(
            ctx.db,
            correlation_id,
            entity_type,
            entity_id,
            "retry_scheduled",
            system=trouble.system,
            attempt=attempt,
            delay_seconds=round(delay, 1),
            problem=trouble.problem,
            error=trouble.error,
            **extra,
        )

    return on_retry
