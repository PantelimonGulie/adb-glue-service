import asyncio
import sqlite3

import pytest

import glue.main
from glue import db, review
from glue.db import Database


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
