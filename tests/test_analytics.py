import json
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from common.models import Order, OrderLine

BUCHAREST = ZoneInfo("Europe/Bucharest")


async def get(systems, path: str = "/api/analytics", **params: object) -> dict:
    response = await systems.http.get(f"http://glue{path}", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def log(systems, ts: str, correlation_id: str, entity_id: str, action: str, **detail) -> None:
    entity_type = "event" if action == "event_received" else "order"
    systems.ctx.db.conn.execute(
        "INSERT INTO audit_log (ts, correlation_id, entity_type, entity_id, action, detail)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (ts, correlation_id, entity_type, entity_id, action, json.dumps(detail)),
    )


def local(day_offset: int, clock: str) -> str:
    day = datetime.now(BUCHAREST).date() + timedelta(days=day_offset)
    moment = datetime.combine(day, time.fromisoformat(clock), BUCHAREST)
    return moment.astimezone(UTC).isoformat(timespec="milliseconds")


def today_at(clock: str) -> str:
    # Ranges and buckets follow Bucharest days and hours.
    return local(0, clock)


async def test_analytics_empty_range(systems):
    report = await get(systems, range="today")

    assert report["range"]["unit"] == "hour"
    assert report["range"]["labels"][:3] == ["00:00", "01:00", "02:00"]
    assert len(report["range"]["labels"]) == 24
    for group in report["series"].values():
        assert all(values == [0] * 24 for values in group.values())
    assert set(report["funnel"].values()) == {0}
    assert report["parts"]["warehouse"]["first_try_pct"] == 0
    assert report["parts"]["glue"]["lost"] == 0
    assert (report["by_product"], report["failure_causes"]) == ([], [])
    assert report["previous"] is None
    assert report["sample"] is False


async def test_funnel_counts(systems):
    await systems.chaos("warehouse", fail_next=1)
    for sku in ("IPH16-128", "APP-3", "MBA-M4"):
        await systems.buy_on_shop(sku)
    await systems.chaos("shop", duplicate_last=True)
    await systems.run_worker()

    report = await get(systems, range="today")

    assert report["funnel"] == {
        "received": 4,
        "duplicates": 1,
        "sent": 3,
        "first_try": 2,
        "after_retry": 1,
        "failed": 0,
    }
    assert report["parts"]["shop"] == {"orders": 3, "duplicates": 1, "refused": 0}
    warehouse = report["parts"]["warehouse"]
    assert (warehouse["received"], warehouse["first_try_pct"], warehouse["retries"]) == (3, 66.7, 1)
    assert {row["sku"]: row["reserved"] for row in report["by_product"]} == {
        "IPH16-128": 1,
        "APP-3": 1,
        "MBA-M4": 1,
    }


async def test_an_order_dismissed_without_a_fix_counts_as_lost(systems, sleeps):
    await systems.chaos("warehouse", down=True)
    await systems.chaos("emag", down=True)
    await systems.buy_on_shop("APP-3")
    # eMAG cannot be read, so this order never even gets a row in Glue.
    await systems.buy_on_emag("IPAD-A16")
    await systems.run_worker()
    waiting = await get(systems, range="today")
    for item in systems.open_reviews():
        await systems.decide(item["id"], "dismiss")
    dismissed = await get(systems, range="today")
    await systems.chaos("warehouse", down=False)
    await systems.chaos("emag", down=False)
    await systems.chaos("emag", renotify_now=True)
    await systems.run_worker()
    healed = await get(systems, range="today")

    lost = [report["parts"]["glue"]["lost"] for report in (waiting, dismissed, healed)]
    assert lost == [0, 2, 1]


async def test_totals_count_order_placements_only(systems):
    shop_order = await systems.buy_on_shop("IPH16-128")
    await systems.buy_on_emag("APP-3")
    await systems.run_worker()
    await systems.http.post(f"http://warehouse/orders/{shop_order}/ship")
    await systems.recount("WATCH-S10", 4)
    await systems.run_worker()

    report = await get(systems, range="today")

    assert report["totals"]["received"] == report["funnel"]["received"] == 2


async def test_overview_flow_and_orders_page_agree_on_one_day(systems, sleeps):
    first_try = await systems.buy_on_shop("APP-3")
    await systems.chaos("shop", duplicate_last=True)
    await systems.run_worker()
    await systems.chaos("warehouse", fail_next=1)
    after_retry = await systems.buy_on_shop("IPAD-A16")
    await systems.run_worker()
    await systems.chaos("emag", freeze_stock=True)
    await systems.buy_on_shop("MBA-M4")
    await systems.run_worker()
    sold_out = await systems.buy_on_emag("MBA-M4")
    await systems.run_worker()
    # A reserved order the shelf can no longer cover is not a failed order.
    recounted = await systems.buy_on_shop("WATCH-S10")
    await systems.run_worker()
    await systems.recount("WATCH-S10", 0)
    await systems.run_worker()
    await systems.chaos("warehouse", down=True)
    outage = await systems.buy_on_shop("IPH16-128")
    await systems.run_worker()

    counters = (await get(systems, "/api/overview", range="today"))["counters"]
    report = await get(systems, range="today")
    orders = await get(systems, "/api/orders", range="today")

    funnel, problems = report["funnel"], report["series"]["problems"]
    assert counters == report["totals"]
    assert counters["received"] == orders["total"] == funnel["sent"] == 6
    assert counters["reserved"] == funnel["first_try"] + funnel["after_retry"] == 4
    assert counters["failed"] == funnel["failed"] == report["parts"]["warehouse"]["failed"] == 2
    assert (sum(problems["retried"]), sum(problems["failed"])) == (1, 2)
    assert counters["retries"] == systems.ctx.db.counters()["retry_scheduled"]
    assert {c["cause"]: c["count"] for c in report["failure_causes"]} == {
        "outage": 1,
        "soldout": 1,
        "recount": 1,
    }
    assert {r["order_id"] for r in orders["rows"] if r["status"] == "failed"} == {sold_out, outage}
    assert {first_try, after_retry, recounted} <= {r["order_id"] for r in orders["rows"]}


async def test_an_emag_order_short_on_the_shelf_is_not_one_sold_after_it_ran_out(systems):
    await systems.buy_on_emag("WATCH-S10")
    await systems.run_worker()
    await systems.recount("WATCH-S10", 0)
    await systems.run_worker()

    report = await get(systems, range="today")

    [item] = systems.open_reviews()
    assert "recount" in item["reason"]
    assert report["parts"]["emag"]["sold_out"] == 0


async def test_by_product_leaves_out_orders_without_lines(systems, sleeps):
    await systems.buy_on_shop("APP-3")
    await systems.chaos("emag", down=True)
    await systems.buy_on_emag("IPAD-A16")
    await systems.run_worker()

    report = await get(systems, range="today")

    assert [row["sku"] for row in report["by_product"]] == ["APP-3"]


async def test_series_by_channel(systems):
    await systems.buy_on_shop("IPH16-128")
    await systems.buy_on_shop("APP-3")
    await systems.buy_on_emag("IPAD-A16")
    await systems.run_worker()

    report = await get(systems, range="live")

    orders = report["series"]["orders"]
    assert report["range"]["unit"] == "minute"
    assert len(orders["shop"]) == len(report["range"]["labels"])
    assert (sum(orders["shop"]), sum(orders["emag"])) == (2, 1)
    assert report["parts"]["emag"]["orders"] == 1


async def test_latency_percentiles(systems):
    for number, received, reserved in (
        (901, "10:00:00.000", "10:00:01.000"),
        (902, "10:05:00.000", "10:05:03.000"),
    ):
        order_id, event_id = f"shop-{number}", f"event-{number}"
        line = OrderLine(sku="APP-3", qty=1)
        order = Order(
            id=order_id,
            channel="shop",
            channel_order_id=str(number),
            lines=[line],
            customer="Guest",
        )
        systems.ctx.db.insert_order_if_new(order)
        log(
            systems,
            today_at(received),
            event_id,
            event_id,
            "event_received",
            source="shop",
            type="order.placed",
        )
        log(
            systems,
            today_at(reserved),
            event_id,
            order_id,
            "order_allocated",
            lines=[line.model_dump()],
        )

    report = await get(systems, range="today")

    glue = report["parts"]["glue"]
    latency = report["series"]["latency"]
    assert (glue["p50_seconds"], glue["p95_seconds"]) == (2.0, 2.9)
    ten = report["range"]["labels"].index("10:00")
    assert (latency["p50"][ten], latency["p95"][ten]) == (2.0, 2.9)
    assert latency["p50"][ten - 1] == 0
    [product] = report["by_product"]
    assert (product["product"], product["orders"], product["p50_seconds"]) == (
        "AirPods Pro 3",
        2,
        2.0,
    )


async def test_compare_returns_previous(systems):
    old = local(-1, "12:00")
    order = Order(id="shop-900", channel="shop", channel_order_id="900", lines=[], customer="")
    systems.ctx.db.insert_order_if_new(order)
    systems.ctx.db.conn.execute("UPDATE orders SET received_at = ?", (old,))

    compared = await get(systems, range="today", compare=1)
    plain = await get(systems, range="today", compare=0)

    assert (compared["previous"]["received"], compared["totals"]["received"]) == (1, 0)
    assert plain["previous"] is None


async def test_csv_has_header_and_total(systems):
    await systems.buy_on_shop("IPH16-128")
    await systems.run_worker()

    response = await systems.http.get("http://glue/api/analytics.csv", params={"range": "today"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    disposition = response.headers["content-disposition"]
    assert disposition == 'attachment; filename="glue-flow-today.csv"'
    lines = response.text.splitlines()
    assert lines[0] == "bucket,orders,retried,failed"
    assert lines[1].startswith("00:00,")
    assert len(lines) == 26
    assert lines[-1] == "total,1,0,0"


async def test_custom_range_over_a_year_is_rejected(systems):
    params = {"range": "custom", "from": "2024-01-01", "to": "2025-01-01"}

    report = await systems.http.get("http://glue/api/analytics", params=params)
    export = await systems.http.get("http://glue/api/analytics.csv", params=params)

    assert (report.status_code, export.status_code) == (422, 422)
    assert report.json()["detail"][0]["msg"] == "a custom range can cover at most a year"


async def test_analytics_needs_sign_in(systems):
    await systems.http.delete("http://glue/api/session", headers={"X-Glue-Request": "1"})

    report = await systems.http.get("http://glue/api/analytics", params={"range": "today"})
    export = await systems.http.get("http://glue/api/analytics.csv", params={"range": "today"})

    assert (report.status_code, export.status_code) == (401, 401)
