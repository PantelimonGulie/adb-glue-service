from datetime import UTC, datetime, timedelta

from glue.db import now
from glue.demo import sample, traffic

ORDER_EVENTS = ("order.placed", "emag.notification")


def inbox(systems) -> list[str]:
    return [row["type"] for row in systems.ctx.db.rows("SELECT type FROM events_inbox")]


def audit_rows(systems) -> list[dict]:
    return systems.ctx.db.rows("SELECT * FROM audit_log ORDER BY id", (), "detail")


async def analytics(systems, **params: object) -> dict:
    response = await systems.http.get("http://glue/api/analytics", params=params)
    assert response.status_code == 200, response.text
    return response.json()


async def test_traffic_tick_buys(systems):
    await traffic.tick(systems.ctx)

    assert sum(kind in ORDER_EVENTS for kind in inbox(systems)) == 1


async def test_traffic_restocks_low_product(systems):
    await traffic.tick(systems.ctx)

    stock = systems.warehouse.state.stock
    assert stock["MBA-M4"]["on_hand"] == 21
    assert stock["APP-3"]["on_hand"] == 40
    assert inbox(systems).count("stock.adjusted") == 1


async def test_traffic_ships_every_sixth_tick(systems):
    for _ in range(6):
        await traffic.tick(systems.ctx)
        await systems.run_worker()

    statuses = [order["status"] for order in systems.warehouse.state.orders.values()]
    assert statuses.count("shipped") == 1


async def test_history_load_and_clear(systems):
    await systems.sign_in("admin")
    real_order = await systems.buy_on_shop("APP-3")
    await systems.run_worker()
    real_rows = audit_rows(systems)
    before = await analytics(systems, range="week")

    loaded = sample.load(systems.ctx, days=2)
    report = await analytics(systems, range="week")

    assert loaded > 0
    assert report["totals"]["received"] > before["totals"]["received"]
    assert report["sample"] is True
    assert max(row["ts"] for row in audit_rows(systems)) < now()

    cleared = await systems.act("/api/demo/history-clear")

    assert cleared.json()["ok"] is True
    assert audit_rows(systems) == real_rows
    assert [row["order_id"] for row in systems.ctx.db.list_orders()[0]] == [real_order]
    assert (await analytics(systems, range="week"))["sample"] is False


async def test_history_load_fills_a_month_the_same_way_every_time(systems):
    await systems.sign_in("admin")
    first = await systems.act("/api/demo/history-load")
    second = await systems.act("/api/demo/history-load")
    today = datetime.now(UTC).date()
    since = str(today - timedelta(days=29))
    report = await analytics(systems, range="custom", **{"from": since, "to": str(today)})

    assert first.json() == second.json()
    assert first.json()["ok"] is True
    assert report["sample"] is True
    assert {group["cause"] for group in report["failure_causes"]} == {"outage", "soldout"}
    funnel = report["funnel"]
    assert funnel["duplicates"] > 0 and funnel["after_retry"] > 0 and funnel["failed"] > 0
    assert report["parts"]["warehouse"]["longest_outage_minutes"] > 0
    daily = [shop + emag for shop, emag in zip(*report["series"]["orders"].values(), strict=True)]
    assert len(set(daily)) > 10
    states = {row["status"] for row in systems.ctx.db.list_orders(limit=10_000)[0]}
    assert states <= {"shipped", "failed", "cancelled"}


async def test_fake_signature_is_rejected(systems):
    await systems.sign_in("admin")
    response = await systems.act("/api/demo/fake-signature")

    assert response.json()["ok"] is True
    assert "401" in response.json()["message"]
    assert systems.ctx.db.counters()["signature_rejected"] == 1


async def test_demo_needs_admin(systems):
    state = await systems.http.get("http://glue/api/demo")
    refused = await systems.act("/api/demo/history-load")
    recount = await systems.act("/api/demo/recount", sku="APP-3", on_hand=0)

    assert state.status_code == 200
    assert (refused.status_code, recount.status_code) == (403, 403)
    assert state.json()["sample_history"] is False


async def test_demo_state_shows_traffic_and_faults(systems):
    await systems.sign_in("admin")
    await systems.act("/api/demo/warehouse-down")
    await systems.act("/api/demo/speed-fast")
    started = await systems.act("/api/demo/traffic-start")
    state = (await systems.http.get("http://glue/api/demo")).json()

    assert started.json() == {"ok": True, "message": "New orders arrive every 0.45 seconds."}
    assert state["traffic"] == {"running": True, "speed": "fast"}
    assert state["faults"]["warehouse"]["down"] is True
    assert state["faults"]["emag"]["freeze_stock"] is False


async def test_ship_oldest_customer_cancel_and_recount(systems):
    oldest = await systems.buy_on_shop("APP-3")
    newest = await systems.buy_on_shop("IPAD-A16")
    await systems.run_worker()
    await systems.sign_in("admin")

    shipped = await systems.act("/api/demo/ship-oldest")
    cancelled = await systems.act("/api/demo/customer-cancel")
    recounted = await systems.act("/api/demo/recount", sku="WATCH-S10", on_hand=3)
    unknown = await systems.act("/api/demo/recount", sku="NOPE-1", on_hand=3)
    await systems.run_worker()

    assert shipped.json() == {"ok": True, "message": f"The warehouse shipped {oldest}."}
    assert cancelled.json()["message"] == f"A customer cancelled {newest} on Electronic Market."
    assert recounted.json()["message"] == "The warehouse now counts 3 Apple Watch S10 on the shelf."
    assert unknown.json()["ok"] is False
    assert systems.ctx.db.get_order(oldest)["status"] == "shipped"
    assert systems.ctx.db.get_order(newest)["status"] == "cancelled"
    assert systems.warehouse.state.stock["WATCH-S10"]["on_hand"] == 3
