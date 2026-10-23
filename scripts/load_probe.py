import argparse
import asyncio
import logging
import tempfile
import time
from contextlib import suppress
from pathlib import Path

import httpx

import emag.main
import glue.main
import shop.main
import warehouse.main
from common.events import emit
from common.models import Order, OrderLine
from glue import analytics_series, queries, reconciler, worker
from glue.settings import Settings

SKU = "APP-3"
SECRET = "probe-shop"


def placed(n: int) -> dict:
    order = Order(
        id=f"shop-{n}",
        channel="shop",
        channel_order_id=str(n),
        lines=[OrderLine(sku=SKU, qty=1)],
        customer="Probe",
    )
    return order.model_dump()


async def probe(orders: int, db_path: str) -> dict:
    settings = Settings(
        shop_url="http://shop",
        emag_url="http://emag",
        warehouse_url="http://warehouse",
        shop_webhook_secret=SECRET,
        db_path=db_path,
    )
    apps = {
        "shop": shop.main.create_app(),
        "emag": emag.main.create_app(),
        "warehouse": warehouse.main.create_app(),
        "glue": glue.main.create_app(settings),
    }
    apps["warehouse"].state.stock[SKU]["on_hand"] = orders
    mounts = {f"all://{name}": httpx.ASGITransport(app) for name, app in apps.items()}
    async with httpx.AsyncClient(mounts=mounts) as http:
        # As the tests do: the context without the lifespan, so only the worker loop runs.
        ctx = glue.main.build_context(settings, http)
        apps["glue"].state.ctx = ctx
        await reconciler.reconcile_all(ctx)

        started = time.perf_counter()
        for n in range(orders):
            data = placed(n)
            assert await emit(
                http, "http://glue/events", "order.placed", data, f"probe-{n}", "shop", SECRET
            )
        ingested = time.perf_counter()
        loop = asyncio.create_task(worker.run_forever(ctx))
        while any(ctx.db.gauges()["inbox"][state] for state in ("pending", "processing")):
            await asyncio.sleep(0.01)
        handled = time.perf_counter()
        loop.cancel()
        with suppress(asyncio.CancelledError):
            await loop

        rows = ctx.db.audit_between("", "9999")
        seconds = [trip.seconds for trip in analytics_series.trips(rows).values() if trip.reserved]
        counts = ctx.db.counters()
        ctx.db.close()
    numbers = {
        "ingest_per_second": orders / (ingested - started),
        "orders_per_second": orders / (handled - ingested),
        "p50_seconds": analytics_series.percentile(seconds, 0.5),
        "p95_seconds": analytics_series.percentile(seconds, 0.95),
        "reserved": apps["warehouse"].state.stock[SKU]["reserved"],
        "allocated": counts.get("order_allocated", 0),
        "duplicates": sum(counts.get(action, 0) for action in queries.COUNTERS["duplicates"]),
    }
    assert numbers["reserved"] == numbers["allocated"] == orders, numbers
    assert numbers["duplicates"] == 0, numbers
    return numbers


def main() -> None:
    parser = argparse.ArgumentParser(description="Send signed shop orders through Glue in-process.")
    parser.add_argument("--orders", type=int, default=300)
    args = parser.parse_args()
    logging.disable(logging.INFO)
    with tempfile.TemporaryDirectory() as folder:
        numbers = asyncio.run(probe(args.orders, str(Path(folder) / "glue.db")))
    print(
        f"{args.orders} shop orders, in-process, worker concurrency {Settings.worker_concurrency}"
    )
    print(f"ingest    {numbers['ingest_per_second']:,.0f} events/s")
    print(f"worker    {numbers['orders_per_second']:,.0f} orders/s")
    # Every order is queued before the worker starts, so the latency includes the inbox wait.
    print(f"received -> allocated  p50 {numbers['p50_seconds']} s  p95 {numbers['p95_seconds']} s")
    print(f"reservations {numbers['reserved']}, duplicates {numbers['duplicates']}")


if __name__ == "__main__":
    main()
