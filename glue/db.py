import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from common.models import Order, StockLevel

SCHEMA = Path(__file__).with_name("schema.sql").read_text()


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

    def orders_allocated_for(self, sku: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT DISTINCT o.* FROM orders o, json_each(o.lines) line"
            " WHERE o.status = 'allocated' AND json_extract(line.value, '$.sku') = ?"
            " ORDER BY o.updated_at",
            (sku,),
        ).fetchall()
        return [decoded(row, "lines") for row in rows]

    def record_stock(self, rows: list[StockLevel]) -> None:
        self.conn.executemany(
            "INSERT INTO stock (sku, on_hand, reserved, seen_at) VALUES (?, ?, ?, ?)"
            " ON CONFLICT(sku) DO UPDATE SET on_hand = excluded.on_hand,"
            " reserved = excluded.reserved, seen_at = excluded.seen_at",
            [(row.sku, row.on_hand, row.reserved, now()) for row in rows],
        )

    def stock(self) -> list[dict]:
        rows = self.conn.execute(
            "SELECT *, on_hand - reserved AS available FROM stock ORDER BY sku"
        ).fetchall()
        return [dict(row) for row in rows]

    def channel_stock(self, channel: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM channel_stock WHERE channel = ? ORDER BY sku", (channel,)
        ).fetchall()
        return [dict(row) for row in rows]

    def set_channel_stock(self, channel: str, sku: str, qty: int, dirty: bool) -> None:
        self.conn.execute(
            "INSERT INTO channel_stock (channel, sku, qty, pushed_at, dirty) VALUES (?, ?, ?, ?, ?)"
            " ON CONFLICT(channel, sku) DO UPDATE SET qty = excluded.qty,"
            " pushed_at = excluded.pushed_at, dirty = excluded.dirty",
            (channel, sku, qty, now(), int(dirty)),
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

    def get_review(self, item_id: int) -> dict | None:
        row = self.conn.execute("SELECT * FROM review_queue WHERE id = ?", (item_id,)).fetchone()
        return decoded(row, "payload") if row else None

    def list_review(self, status: str = "open") -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM review_queue WHERE status = ? ORDER BY id", (status,)
        ).fetchall()
        return [decoded(row, "payload") for row in rows]

    def decide_review(self, item_id: int, action: str, decided_by: str) -> None:
        self.conn.execute(
            "UPDATE review_queue SET status = 'decided', action = ?, decided_by = ?, decided_at = ?"
            " WHERE id = ?",
            (action, decided_by, now(), item_id),
        )

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

    def timeline(self, order_id: str) -> list[dict]:
        # Pulls in rows that share a correlation id with the order, e.g. the inbound event
        # and the stock pushes it triggered.
        rows = self.conn.execute(
            "SELECT * FROM audit_log WHERE entity_id = ? OR correlation_id IN"
            " (SELECT correlation_id FROM audit_log WHERE entity_id = ?) ORDER BY id",
            (order_id, order_id),
        ).fetchall()
        return [decoded(row, "detail") for row in rows]

    def counters(self, since: str = "") -> dict[str, int]:
        rows = self.conn.execute(
            "SELECT action, COUNT(*) AS n FROM audit_log WHERE ts >= ? GROUP BY action", (since,)
        ).fetchall()
        return {row["action"]: row["n"] for row in rows}
