from datetime import UTC, datetime, timedelta

from glue.db import now


def seconds_ago(seconds: int) -> str:
    return (datetime.now(UTC) - timedelta(seconds=seconds)).isoformat(timespec="milliseconds")


async def test_metrics_show_what_waits_and_for_how_long(systems, sleeps):
    db = systems.ctx.db
    await systems.chaos("emag", reject_sku="MBA-M4")
    await systems.reconcile()
    db.conn.execute("UPDATE channel_stock SET pushed_at = ? WHERE dirty = 1", (seconds_ago(60),))
    before = now()
    # Refused again: the row has still not reached eMAG since a minute ago.
    await systems.reconcile()
    after = now()

    await systems.chaos("warehouse", down=True)
    await systems.buy_on_shop("APP-3")
    await systems.send_event("warehouse", "order.shipped", {"order_id": "shop-999"})
    await systems.run_worker()
    await systems.reconcile()
    for sku in ("IPH16-128", "IPAD-A16"):
        await systems.buy_on_shop(sku)
    db.claim_pending_events(1)
    db.conn.execute(
        "UPDATE events_inbox SET received_at = ? WHERE status = 'pending'", (seconds_ago(120),)
    )
    unknown = next(item for item in systems.open_reviews() if item["order_id"] == "shop-999")
    db.start_review(unknown["id"], "dismiss", "operator")
    db.conn.execute(
        "UPDATE review_queue SET created_at = ? WHERE status = 'open'", (seconds_ago(300),)
    )

    metrics = (await systems.http.get("http://glue/metrics")).json()

    inbox, stock, review = metrics["inbox"], metrics["stock"], metrics["review"]
    assert (inbox["pending"], inbox["processing"], inbox["failed"]) == (1, 1, 1)
    assert 120 <= inbox["oldest_pending_seconds"] < 130
    assert stock["dirty_rows"] == 1
    assert 60 <= stock["oldest_dirty_seconds"] < 70
    assert (review["open"], review["acting"]) == (1, 1)
    assert 300 <= review["oldest_open_seconds"] < 310
    assert metrics["warehouse_down"] is True
    assert before <= metrics["last_reconcile_ok_at"] <= after
    assert metrics["open_review_items"] == 2
    assert metrics["total"]["order_failed"] == 1


async def test_metrics_when_nothing_waits(systems):
    metrics = (await systems.http.get("http://glue/metrics")).json()

    assert metrics["inbox"] == {
        "pending": 0,
        "processing": 0,
        "failed": 0,
        "oldest_pending_seconds": None,
    }
    assert metrics["stock"] == {"dirty_rows": 0, "oldest_dirty_seconds": None}
    assert metrics["review"] == {"open": 0, "acting": 0, "oldest_open_seconds": None}
    assert metrics["warehouse_down"] is False


async def test_health_stays_up_and_reports_each_system(systems):
    await systems.chaos("emag", down=True)

    response = await systems.http.get("http://glue/health")

    assert response.status_code == 200
    health = response.json()
    assert (health["status"], health["db"]) == ("ok", "ok")
    up = {name: system["ok"] for name, system in health["systems"].items()}
    assert up == {"shop": True, "emag": False, "warehouse": True}
    assert health["systems"]["emag"]["state"] == "Answering HTTP 503"
