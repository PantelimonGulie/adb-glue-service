import sqlite3

from glue import db
from glue.db import Database


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
