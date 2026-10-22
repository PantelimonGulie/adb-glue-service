import random
from datetime import UTC, datetime, timedelta

from glue.context import Context
from glue.sample_orders import REASONS, History, place

SEED = 2026
DAY = timedelta(days=1)
# Orders per UTC hour relative to the day's mean: quiet nights, a lunch bump, an evening peak.
HOURLY = [0.15] * 7 + [0.7] * 3 + [1.4] * 3 + [1.0] * 5 + [1.6] * 4 + [0.6] * 2
ORDERS_PER_DAY = 70
WEEKEND = 1.4
SHOP_SHARE = 0.64


def outage(h: History, midnight: datetime) -> None:
    start = h.later(midnight, 9 * 3600, 21 * 3600)
    end = h.later(start, 8 * 60, 30 * 60)
    h.outages.append((start, end))
    run = f"sample-run-{start:%Y%m%d%H%M}"
    problem = REASONS["order_failed"]
    h.log(
        h.later(start, 1, 10), run, "stock", "warehouse", "warehouse_unreachable", problem=problem
    )
    qty = h.rng.randint(8, 30)
    h.log(h.later(end, 1, 10), run, "stock", "IPH16-128", "stock_pushed", channel="shop", qty=qty)


def load(ctx: Context, days: int = 30) -> int:
    ctx.db.delete_sample()
    now = datetime.now(UTC)
    h = History(random.Random(SEED), now)
    first = now.replace(hour=0, minute=0, second=0, microsecond=0) - (days - 1) * DAY
    for day in range(days):
        if (days - 1 - day) % 9 == 4:
            outage(h, first + day * DAY)
    for day in range(days):
        midnight = first + day * DAY
        busy = (WEEKEND if midnight.weekday() >= 5 else 1) * h.rng.uniform(0.8, 1.2)
        for hour, weight in enumerate(HOURLY):
            expected = ORDERS_PER_DAY * busy * weight / sum(HOURLY)
            start = midnight + timedelta(hours=hour)
            times = [
                h.later(start, 0, 3600) for _ in range(round(expected * h.rng.uniform(0.6, 1.4)))
            ]
            for at in sorted(times):
                # Leaves room for retries and shipping to finish before now.
                if at < now - timedelta(minutes=5):
                    place(h, "shop" if h.rng.random() < SHOP_SHARE else "emag", at)
    h.audit.sort(key=lambda row: row["ts"])
    ctx.db.insert_sample(h.orders, h.audit)
    return len(h.orders)


def clear(ctx: Context) -> int:
    return ctx.db.delete_sample()
