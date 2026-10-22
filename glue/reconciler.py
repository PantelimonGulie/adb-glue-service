import asyncio
import logging
from collections.abc import Callable
from functools import partial

from common.models import StockLevel
from glue import review, rules
from glue.audit import record
from glue.context import Context
from glue.db import now
from glue.retry import RetryExhausted, with_retries

log = logging.getLogger(__name__)


async def reconcile_all(ctx: Context) -> None:
    await reconcile_skus(ctx, None, f"run-{now()}")


async def reconcile_sku(ctx: Context, event: dict) -> None:
    await reconcile_skus(ctx, [event["payload"]["sku"]], event["event_id"])


async def reconcile_skus(ctx: Context, skus: list[str] | None, correlation_id: str) -> None:
    async with ctx.reconcile_lock:
        try:
            response = await with_retries(ctx, ctx.warehouse.stock)
        except RetryExhausted as exc:
            if not ctx.warehouse_down:
                record(
                    ctx.db,
                    correlation_id,
                    "stock",
                    "warehouse",
                    "warehouse_unreachable",
                    problem=str(exc),
                )
            ctx.warehouse_down = True
            return
        recovered = ctx.warehouse_down
        ctx.warehouse_down = False
        ctx.db.record_stock([StockLevel.model_validate(row) for row in response.json()])
        rows = [row for row in ctx.db.stock() if skus is None or row["sku"] in skus]
        await push_channels(ctx, rows, correlation_id)
        for row in rows:
            if row["available"] < 0:
                open_conflicts(ctx, row, correlation_id)
    # Outside the lock: a retried allocation reconciles its own SKUs.
    if recovered:
        await rules.retry_after_recovery(ctx, correlation_id)


async def push_channels(ctx: Context, rows: list[dict], correlation_id: str) -> None:
    # Every SKU given is pushed, even if the cache says the channel already has that figure:
    # a restarted or unfrozen channel would otherwise keep stale numbers until the next change.
    sellable = {row["sku"]: max(0, row["available"]) for row in rows}
    if not sellable:
        return
    for channel, push in (("shop", push_shop), ("emag", push_emag)):
        held = rules.held_back(ctx, channel, list(sellable))
        pending = {sku: max(0, qty - held[sku]) for sku, qty in sellable.items()}
        await push(ctx, pending, correlation_id, held)


async def push_shop(
    ctx: Context, pending: dict[str, int], correlation_id: str, held: dict[str, int]
) -> None:
    for sku, qty in pending.items():
        on_retry = retry_logger(ctx, correlation_id, "shop", [sku])
        try:
            response = await with_retries(ctx, partial(ctx.shop.set_stock, sku, qty), on_retry)
        except RetryExhausted as exc:
            note_push(ctx, correlation_id, "shop", sku, qty, str(exc), held[sku])
            continue
        problem = None if response.is_success else f"HTTP {response.status_code}"
        note_push(ctx, correlation_id, "shop", sku, qty, problem, held[sku])


async def push_emag(
    ctx: Context, pending: dict[str, int], correlation_id: str, held: dict[str, int]
) -> None:
    offers = list(pending.items())
    on_retry = retry_logger(ctx, correlation_id, "emag", list(pending))
    try:
        response = await with_retries(ctx, partial(ctx.emag.save_offers, offers), on_retry)
    except RetryExhausted as exc:
        for sku, qty in offers:
            note_push(ctx, correlation_id, "emag", sku, qty, str(exc), held[sku])
        return
    body = response.json() if response.is_success else {}
    results = {result["part_number"]: result for result in body.get("results", [])}
    for sku, qty in offers:
        result = results.get(sku, {"ok": False, "message": f"HTTP {response.status_code}"})
        problem = None if result["ok"] else result["message"]
        note_push(ctx, correlation_id, "emag", sku, qty, problem, held[sku])


def retry_logger(
    ctx: Context, correlation_id: str, channel: str, skus: list[str]
) -> Callable[[int, float, str], None]:
    def on_retry(attempt: int, delay: float, problem: str) -> None:
        record(
            ctx.db,
            correlation_id,
            "stock",
            channel,
            "retry_scheduled",
            attempt=attempt,
            delay_seconds=round(delay, 2),
            problem=problem,
            skus=skus,
        )

    return on_retry


def note_push(
    ctx: Context,
    correlation_id: str,
    channel: str,
    sku: str,
    qty: int,
    problem: str | None,
    held: int = 0,
) -> None:
    changed = ctx.db.set_channel_stock(channel, sku, qty, dirty=problem is not None)
    by_rule = {"rule": "stock-buffer", "held_back": held} if held else {}
    if problem is not None:
        record(
            ctx.db,
            correlation_id,
            "stock",
            sku,
            "stock_push_failed",
            channel=channel,
            qty=qty,
            problem=problem,
            **by_rule,
        )
    elif changed:
        detail = {"channel": channel, "qty": qty, **by_rule}
        record(ctx.db, correlation_id, "stock", sku, "stock_pushed", **detail)


def open_conflicts(ctx: Context, row: dict, correlation_id: str) -> None:
    reason = f"recount: {row['on_hand']} on hand, {row['reserved']} reserved"
    for order in ctx.db.orders_allocated_for(row["sku"]):
        order_id = order["order_id"]
        if review.open(ctx, "unfulfillable", order_id, reason, correlation_id, payload=order):
            record(ctx.db, correlation_id, "order", order_id, "unfulfillable", reason=reason)


async def run_forever(ctx: Context) -> None:
    while True:
        await asyncio.sleep(ctx.tuning.reconcile_interval_seconds)
        try:
            await reconcile_all(ctx)
        except Exception:
            log.exception("reconcile failed")
