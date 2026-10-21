import json
import sqlite3
from datetime import UTC, datetime

from common.models import Order

SCHEMA = """
CREATE TABLE IF NOT EXISTS events_inbox (
    event_id    TEXT PRIMARY KEY,
    source      TEXT NOT NULL,
    type        TEXT NOT NULL,
    payload     TEXT NOT NULL,
    received_at TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'pending',
    error       TEXT
);
CREATE INDEX IF NOT EXISTS events_inbox_status ON events_inbox(status, received_at);

CREATE TABLE IF NOT EXISTS orders (
    order_id         TEXT PRIMARY KEY,
    channel          TEXT NOT NULL,
    channel_order_id TEXT NOT NULL,
    lines            TEXT NOT NULL,
    customer         TEXT NOT NULL,
    status           TEXT NOT NULL,
    attempts         INTEGER NOT NULL DEFAULT 1,
    last_error       TEXT,
    updated_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS stock (
    sku      TEXT PRIMARY KEY,
    on_hand  INTEGER NOT NULL,
    reserved INTEGER NOT NULL,
    seen_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS channel_stock (
    channel   TEXT NOT NULL,
    sku       TEXT NOT NULL,
    qty       INTEGER NOT NULL,
    pushed_at TEXT NOT NULL,
    dirty     INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (channel, sku)
);

CREATE TABLE IF NOT EXISTS review_queue (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    kind       TEXT NOT NULL,
    order_id   TEXT,
    payload    TEXT NOT NULL,
    reason     TEXT NOT NULL,
    status     TEXT NOT NULL DEFAULT 'open',
    action     TEXT,
    decided_by TEXT,
    decided_at TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    ts             TEXT NOT NULL,
    correlation_id TEXT NOT NULL,
    entity_type    TEXT NOT NULL,
    entity_id      TEXT NOT NULL,
    action         TEXT NOT NULL,
    detail         TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS audit_log_entity ON audit_log(entity_id);
"""


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


def decoded(row: sqlite3.Row, json_column: str) -> dict:
    record = dict(row)
    record[json_column] = json.loads(record[json_column])
    return record


class Database:
    def __init__(self, path: str):
        self.conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.executescript(SCHEMA)
        # Events claimed by a previous run that never finished go back to the queue.
        self.conn.execute("UPDATE events_inbox SET status = 'pending' WHERE status = 'processing'")

    def close(self) -> None:
        self.conn.close()

    def insert_event_if_new(self, event_id: str, source: str, type: str, payload: dict) -> bool:
        # A redelivery of an event whose processing failed gets a fresh attempt.
        cursor = self.conn.execute(
            "INSERT INTO events_inbox (event_id, source, type, payload, received_at)"
            " VALUES (?, ?, ?, ?, ?)"
            " ON CONFLICT(event_id) DO UPDATE SET status = 'pending', error = NULL"
            " WHERE events_inbox.status = 'failed'",
            (event_id, source, type, json.dumps(payload), now()),
        )
        return cursor.rowcount == 1

    def claim_pending_events(self, limit: int) -> list[dict]:
        rows = self.conn.execute(
            "UPDATE events_inbox SET status = 'processing' WHERE event_id IN"
            " (SELECT event_id FROM events_inbox WHERE status = 'pending'"
            "  ORDER BY received_at LIMIT ?) RETURNING *",
            (limit,),
        ).fetchall()
        return [decoded(row, "payload") for row in rows]

    def finish_event(self, event_id: str, status: str, error: str | None = None) -> None:
        self.conn.execute(
            "UPDATE events_inbox SET status = ?, error = ? WHERE event_id = ?",
            (status, error, event_id),
        )

    def get_order(self, order_id: str) -> dict | None:
        row = self.conn.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,)).fetchone()
        return decoded(row, "lines") if row else None

    def list_orders(self) -> list[dict]:
        rows = self.conn.execute("SELECT * FROM orders ORDER BY updated_at DESC").fetchall()
        return [decoded(row, "lines") for row in rows]

    def insert_order_if_new(self, order: Order, status: str = "received") -> bool:
        cursor = self.conn.execute(
            "INSERT OR IGNORE INTO orders"
            " (order_id, channel, channel_order_id, lines, customer, status, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                order.id,
                order.channel,
                order.channel_order_id,
                json.dumps([line.model_dump() for line in order.lines]),
                order.customer,
                status,
                now(),
            ),
        )
        return cursor.rowcount == 1

    def set_order(self, order_id: str, **fields: object) -> None:
        fields["updated_at"] = now()
        assignments = ", ".join(f"{name} = ?" for name in fields)
        self.conn.execute(
            f"UPDATE orders SET {assignments} WHERE order_id = ?", (*fields.values(), order_id)
        )

    def open_review(
        self, kind: str, order_id: str | None, payload: dict, reason: str
    ) -> int | None:
        existing = self.conn.execute(
            "SELECT id FROM review_queue WHERE kind = ? AND order_id = ? AND status = 'open'",
            (kind, order_id),
        ).fetchone()
        if existing:
            return None
        cursor = self.conn.execute(
            "INSERT INTO review_queue (kind, order_id, payload, reason, created_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (kind, order_id, json.dumps(payload, default=str), reason, now()),
        )
        return cursor.lastrowid

    def audit(
        self, correlation_id: str, entity_type: str, entity_id: str, action: str, detail: dict
    ) -> None:
        self.conn.execute(
            "INSERT INTO audit_log (ts, correlation_id, entity_type, entity_id, action, detail)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (now(), correlation_id, entity_type, entity_id, action, json.dumps(detail)),
        )

    def audit_for(self, entity_id: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM audit_log WHERE entity_id = ? OR correlation_id = ? ORDER BY id",
            (entity_id, entity_id),
        ).fetchall()
        return [decoded(row, "detail") for row in rows]

    def audit_tail(self, limit: int = 100) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [decoded(row, "detail") for row in rows]
