import asyncio
import logging
from functools import partial

from common.models import StockLevel
from glue import review, rules, settle
from glue.audit import record
from glue.context import Context
from glue.db import now
from glue.retry import RetryExhausted, retry_logger, with_retries

log = logging.getLogger(__name__)


async def reconcile_all(ctx: Context) -> None:
    await reconcile_skus(ctx, None, f"run-{now()}")


async def reconcile_sku(ctx: Context, event: dict) -> None:
    await reconcile_skus(ctx, [event["payload"]["sku"]], event["event_id"])


async def reconcile_skus(ctx: Context, skus: list[str] | None, correlation_id: str) -> None:
    async with ctx.reconcile_lock:
        try:
            response = await with_retries(ctx, "warehouse", ctx.warehouse.stock)
        except RetryExhausted as exc:
            if not ctx.warehouse_down:
                record(
                    ctx.db,
                    correlation_id,
                    "stock",
                    "warehouse",
                    "warehouse_unreachable",
                    problem=str(exc),
                    error=exc.error,
                )
            ctx.warehouse_down = True
            return
        recovered = ctx.warehouse_down
        ctx.warehouse_down = False
        ctx.db.record_stock([StockLevel.model_validate(row) for row in response.json()])
        rows = [row for row in ctx.db.stock() if skus is None or row["sku"] in skus]
        await push_channels(ctx, rows, correlation_id)
        for row in rows:
            recount_conflicts(ctx, row, correlation_id)
        if skus is None:
            ctx.last_reconcile_ok_at = now()
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
        on_retry = retry_logger(ctx, correlation_id, "stock", "shop", skus=[sku])
        send = partial(ctx.shop.set_stock, sku, qty)
        try:
            response = await with_retries(ctx, "shop", send, on_retry)
        except RetryExhausted as exc:
            note_push(ctx, correlation_id, "shop", sku, qty, str(exc), held[sku])
            continue
        problem = None if response.is_success else "the shop refused the update"
        note_push(ctx, correlation_id, "shop", sku, qty, problem, held[sku])


async def push_emag(
    ctx: Context, pending: dict[str, int], correlation_id: str, held: dict[str, int]
) -> None:
    offers = list(pending.items())
    on_retry = retry_logger(ctx, correlation_id, "stock", "emag", skus=list(pending))
    try:
        response = await with_retries(ctx, "emag", partial(ctx.emag.save_offers, offers), on_retry)
    except RetryExhausted as exc:
        for sku, qty in offers:
            note_push(ctx, correlation_id, "emag", sku, qty, str(exc), held[sku])
        return
    body = response.json() if response.is_success else {}
    results = {result["part_number"]: result for result in body.get("results", [])}
    for sku, qty in offers:
        result = results.get(sku, {"ok": False, "message": "eMAG refused the update"})
        problem = None if result["ok"] else result["message"]
        note_push(ctx, correlation_id, "emag", sku, qty, problem, held[sku])


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


def recount_conflicts(ctx: Context, row: dict, correlation_id: str) -> None:
    # By the warehouse's own figures, only as many of the newest orders as the shelf is short go
    # to review: Glue may count more reserved orders than the warehouse still holds.
    sku = row["sku"]
    short = row["reserved"] - row["on_hand"]
    waiting = {item["order_id"]: item for item in ctx.db.open_recount_items(sku)}
    reason = f"recount: {row['on_hand']} on hand, {row['reserved']} reserved"
    newest_first = ctx.db.orders_allocated_for(sku) if short > 0 else []
    for order in newest_first:
        if short <= 0:
            break
        short -= sum(line["qty"] for line in order["lines"] if line["sku"] == sku)
        order_id = order["order_id"]
        if waiting.pop(order_id, None):
            continue
        payload = {**order, "operation": "place", "sku": sku}
        with ctx.db.transaction():
            if review.queue_item(ctx, "unfulfillable", order_id, reason, correlation_id, payload):
                record(ctx.db, correlation_id, "order", order_id, "unfulfillable", reason=reason)
    for item in waiting.values():
        settle.resolve(ctx, item, correlation_id, "a later count covers this order again")


async def run_forever(ctx: Context) -> None:
    while True:
        await asyncio.sleep(ctx.tuning.reconcile_interval_seconds)
        try:
            await reconcile_all(ctx)
        except Exception:
            log.exception("reconcile failed")
