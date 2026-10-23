import asyncio
import sqlite3

import pytest

import glue.main
from glue import db, reconciler, review, worker
from glue.ai import llm
from glue.db import Database
from glue.demo import traffic


async def test_shutdown_lets_the_background_loops_stop_before_closing_the_db(systems, monkeypatch):
    stopped = []

    async def loop(ctx) -> None:
        try:
            await asyncio.Event().wait()
        finally:
            # A loop cut short mid-step still writes what it was doing.
            stopped.append(ctx.db.counters())

    async def nothing(ctx) -> None:
        pass

    monkeypatch.setattr(reconciler, "reconcile_all", nothing)
    for module in (worker, reconciler, traffic):
        monkeypatch.setattr(module, "run_forever", loop)
    monkeypatch.setattr(llm, "ensure_model", loop)
    app = glue.main.create_app(systems.ctx.settings)

    async with glue.main.lifespan(app):
        await asyncio.sleep(0)

    assert len(stopped) == 4


async def test_an_event_claimed_when_glue_stopped_is_handled_once_after_a_restart(systems):
    order_id = await systems.buy_on_shop("IPH16-128")
    # The worker took the event, then Glue stopped before finishing it.
    [claimed] = systems.ctx.db.claim_pending_events(10)

    restarted = glue.main.build_context(systems.ctx.settings, systems.http)
    assert restarted.db.rows("SELECT status FROM events_inbox") == [{"status": "pending"}]
    while await worker.process_pending(restarted):
        pass

    assert restarted.db.get_order(order_id)["status"] == "allocated"
    assert systems.warehouse.state.stock["IPH16-128"]["reserved"] == 1
    assert restarted.db.rows("SELECT status FROM events_inbox") == [{"status": "done"}]
    restarted.db.close()


async def test_a_decision_cut_short_is_open_again_after_a_restart(systems, sleeps):
    await systems.chaos("warehouse", down=True)
    order_id = await systems.buy_on_shop("IPH16-256")
    await systems.run_worker()
    [item] = systems.open_reviews()
    await systems.chaos("warehouse", down=False)

    async def cut_short(order):
        # Stands in for the process stopping, or the request being cancelled, mid-call.
        raise asyncio.CancelledError

    systems.ctx.warehouse.create_order = cut_short
    with pytest.raises(asyncio.CancelledError):
        await review.decide(systems.ctx, item["id"], "retry")
    listed = (await systems.http.get("http://glue/api/review")).json()["items"]

    assert [(i["id"], i["status"], i["allowed"]) for i in listed] == [(item["id"], "acting", [])]

    restarted = glue.main.build_context(systems.ctx.settings, systems.http)
    [reopened] = restarted.db.list_review()
    assert (reopened["id"], reopened["status"], reopened["action"]) == (item["id"], "open", None)

    await review.decide(restarted, item["id"], "retry")
    assert restarted.db.get_order(order_id)["status"] == "allocated"
    restarted.db.close()


async def test_a_decision_cut_short_after_it_took_effect_is_closed_after_a_restart(systems, sleeps):
    await systems.chaos("warehouse", down=True)
    order_id = await systems.buy_on_shop("IPH16-256")
    await systems.run_worker()
    [item] = systems.open_reviews()
    await systems.chaos("warehouse", down=False)

    async def stopped():
        raise asyncio.CancelledError

    # The allocation lands; Glue stops during the stock check that follows it.
    systems.ctx.warehouse.stock = stopped
    with pytest.raises(asyncio.CancelledError):
        await review.decide(systems.ctx, item["id"], "retry")

    restarted = glue.main.build_context(systems.ctx.settings, systems.http)
    assert restarted.db.get_order(order_id)["status"] == "allocated"
    assert restarted.db.list_review() == []
    [closed] = restarted.db.list_review("decided")
    assert (closed["id"], closed["action"], closed["decided_by"]) == (
        item["id"],
        "resolved",
        "glue",
    )
    restarted.db.close()


async def test_a_retry_cut_short_after_it_failed_again_leaves_one_item(systems, sleeps):
    await systems.chaos("warehouse", down=True)
    order_id = await systems.buy_on_shop("IPH16-256")
    await systems.run_worker()
    [item] = systems.open_reviews()

    def killed(*args):
        raise asyncio.CancelledError

    # The retry fails again and opens a fresh item; Glue stops before it closes the old one.
    systems.ctx.db.decide_review = killed
    with pytest.raises(asyncio.CancelledError):
        await review.decide(systems.ctx, item["id"], "retry")

    restarted = glue.main.build_context(systems.ctx.settings, systems.http)
    [fresh] = restarted.db.list_review()
    assert fresh["id"] != item["id"]
    [closed] = restarted.db.list_review("decided")
    assert (closed["id"], closed["action"], closed["decided_by"]) == (
        item["id"],
        "resolved",
        "glue",
    )
    assert restarted.db.get_order(order_id)["status"] == "failed"
    restarted.db.close()


def test_a_database_from_before_versioning_upgrades_in_place(tmp_path):
    path = str(tmp_path / "glue.db")
    # What every existing volume holds: schema.sql as first shipped, user_version 0.
    old = sqlite3.connect(path)
    old.executescript(db.SCHEMA)
    old.execute(
        "INSERT INTO events_inbox (event_id, source, type, payload, received_at, status)"
        " VALUES ('e-1', 'shop', 'order.placed', '{}', '2026-10-22T10:00:00.000+00:00', 'done')"
    )
    old.commit()
    old.close()

    upgraded = Database(path)
    upgraded.close()
    reopened = Database(path)

    assert reopened.conn.execute("PRAGMA user_version").fetchone()[0] == len(db.MIGRATIONS)
    assert reopened.rows("SELECT event_id, source, status FROM events_inbox") == [
        {"event_id": "e-1", "source": "shop", "status": "done"}
    ]
    assert not reopened.insert_event_if_new("e-1", "shop", "order.placed", {})
    assert reopened.insert_event_if_new("e-1", "warehouse", "stock.adjusted", {})
    reopened.close()


def test_orders_saved_before_received_at_existed_take_their_last_update(tmp_path):
    path = str(tmp_path / "glue.db")
    old = sqlite3.connect(path)
    for step in db.MIGRATIONS[:2]:
        old.executescript(step)
    old.execute("PRAGMA user_version = 2")
    old.execute(
        "INSERT INTO orders (order_id, channel, channel_order_id, lines, customer, status,"
        " updated_at) VALUES ('shop-1', 'shop', '1', '[]', 'Guest', 'shipped',"
        " '2026-10-22T10:00:00.000+00:00')"
    )
    old.commit()
    old.close()

    upgraded = Database(path)

    assert upgraded.get_order("shop-1")["received_at"] == "2026-10-22T10:00:00.000+00:00"
    upgraded.close()
