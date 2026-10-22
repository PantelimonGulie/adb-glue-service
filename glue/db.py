import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from common.catalog import PRODUCTS
from common.models import Order, StockLevel

SCHEMA = Path(__file__).with_name("schema.sql").read_text()
# An empty filter value means "any"; :skus is a JSON list of the products the search matches.
ORDER_FILTER = (
    "(:channel = '' OR channel = :channel) AND (:status = '' OR status = :status)"
    " AND updated_at >= :since AND (:until = '' OR updated_at < :until)"
    " AND (:q = '' OR order_id LIKE '%' || :q || '%' OR EXISTS (SELECT 1 FROM json_each(lines)"
    " WHERE json_extract(value, '$.sku') IN (SELECT value FROM json_each(:skus))))"
)
AUDIT_FILTER = (
    "ts >= :since AND (:until = '' OR ts < :until)"
    " AND (:kinds IS NULL OR action IN (SELECT value FROM json_each(:kinds)))"
    " AND (:entity = '' OR entity_id = :entity OR correlation_id = :entity)"
)


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


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

    def rows(
        self, sql: str, params: tuple | dict = (), json_column: str | None = None
    ) -> list[dict]:
        records = [dict(row) for row in self.conn.execute(sql, params).fetchall()]
        if json_column:
            for record in records:
                record[json_column] = json.loads(record[json_column])
        return records

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
        return self.rows(
            "UPDATE events_inbox SET status = 'processing' WHERE event_id IN"
            " (SELECT event_id FROM events_inbox WHERE status = 'pending'"
            "  ORDER BY received_at LIMIT ?) RETURNING *",
            (limit,),
            "payload",
        )

    def finish_event(self, event_id: str, status: str, error: str | None = None) -> None:
        self.conn.execute(
            "UPDATE events_inbox SET status = ?, error = ? WHERE event_id = ?",
            (status, error, event_id),
        )

    def get_order(self, order_id: str) -> dict | None:
        rows = self.rows("SELECT * FROM orders WHERE order_id = ?", (order_id,), "lines")
        return rows[0] if rows else None

    def orders_in(self, order_ids: list[str]) -> list[dict]:
        return self.rows(
            "SELECT * FROM orders WHERE order_id IN (SELECT value FROM json_each(?))",
            (json.dumps(order_ids),),
            "lines",
        )

    def page(
        self, table: str, where: str, order_by: str, params: dict, json_column: str
    ) -> tuple[list[dict], int]:
        count = f"SELECT COUNT(*) FROM {table} WHERE {where}"
        total = self.conn.execute(count, params).fetchone()[0]
        rows = self.rows(
            f"SELECT * FROM {table} WHERE {where} ORDER BY {order_by} LIMIT :limit OFFSET :offset",
            params,
            json_column,
        )
        return rows, total

    def list_orders(
        self,
        q: str = "",
        channel: str = "",
        status: str = "",
        since: str = "",
        until: str = "",
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        skus = [sku for sku, name in PRODUCTS.items() if q.lower() in f"{sku} {name}".lower()]
        params = {
            "q": q,
            "skus": json.dumps(skus),
            "channel": channel,
            "status": status,
            "since": since,
            "until": until,
            "limit": limit,
            "offset": offset,
        }
        return self.page("orders", ORDER_FILTER, "updated_at DESC", params, "lines")

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
        return self.rows(
            "SELECT DISTINCT o.* FROM orders o, json_each(o.lines) line"
            " WHERE o.status = 'allocated' AND json_extract(line.value, '$.sku') = ?"
            " ORDER BY o.updated_at",
            (sku,),
            "lines",
        )

    def record_stock(self, rows: list[StockLevel]) -> None:
        self.conn.executemany(
            "INSERT INTO stock (sku, on_hand, reserved, seen_at) VALUES (?, ?, ?, ?)"
            " ON CONFLICT(sku) DO UPDATE SET on_hand = excluded.on_hand,"
            " reserved = excluded.reserved, seen_at = excluded.seen_at",
            [(row.sku, row.on_hand, row.reserved, now()) for row in rows],
        )

    def stock(self) -> list[dict]:
        return self.rows("SELECT *, on_hand - reserved AS available FROM stock ORDER BY sku")

    def channel_stock(self, channel: str) -> list[dict]:
        return self.rows("SELECT * FROM channel_stock WHERE channel = ? ORDER BY sku", (channel,))

    def set_channel_stock(self, channel: str, sku: str, qty: int, dirty: bool) -> bool:
        before = self.conn.execute(
            "SELECT qty, dirty FROM channel_stock WHERE channel = ? AND sku = ?", (channel, sku)
        ).fetchone()
        self.conn.execute(
            "INSERT INTO channel_stock (channel, sku, qty, pushed_at, dirty) VALUES (?, ?, ?, ?, ?)"
            " ON CONFLICT(channel, sku) DO UPDATE SET qty = excluded.qty,"
            " pushed_at = excluded.pushed_at, dirty = excluded.dirty",
            (channel, sku, qty, now(), int(dirty)),
        )
        return before is None or (before["qty"], before["dirty"]) != (qty, int(dirty))

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
        rows = self.rows("SELECT * FROM review_queue WHERE id = ?", (item_id,), "payload")
        return rows[0] if rows else None

    def list_review(self, status: str = "open") -> list[dict]:
        return self.rows(
            "SELECT * FROM review_queue WHERE status = ? ORDER BY id", (status,), "payload"
        )

    def decide_review(self, item_id: int, action: str, decided_by: str) -> None:
        self.conn.execute(
            "UPDATE review_queue SET status = 'decided', action = ?, decided_by = ?, decided_at = ?"
            " WHERE id = ?",
            (action, decided_by, now(), item_id),
        )

    def set_suggestion(self, item_id: int, action: str | None, reason: str) -> None:
        self.conn.execute(
            "UPDATE review_queue SET suggested_action = ?, suggested_reason = ? WHERE id = ?",
            (action, reason, item_id),
        )

    def rules(self) -> list[dict]:
        return self.rows("SELECT * FROM rules", (), "config")

    def set_rule(self, name: str, enabled: bool, config: dict, updated_by: str) -> None:
        self.conn.execute(
            "INSERT INTO rules (name, enabled, config, updated_by, updated_at)"
            " VALUES (?, ?, ?, ?, ?)"
            " ON CONFLICT(name) DO UPDATE SET enabled = excluded.enabled, config = excluded.config,"
            " updated_by = excluded.updated_by, updated_at = excluded.updated_at",
            (name, int(enabled), json.dumps(config), updated_by, now()),
        )

    def settings(self) -> dict[str, str]:
        return {row["key"]: row["value"] for row in self.rows("SELECT key, value FROM settings")}

    def set_setting(self, key: str, value: str, by: str) -> None:
        self.conn.execute(
            "INSERT INTO settings (key, value, updated_by, updated_at) VALUES (?, ?, ?, ?)"
            " ON CONFLICT(key) DO UPDATE SET value = excluded.value,"
            " updated_by = excluded.updated_by, updated_at = excluded.updated_at",
            (key, value, by, now()),
        )

    def add_usage(self, tokens: int) -> None:
        self.conn.execute(
            "INSERT INTO ai_usage (day, tokens, questions) VALUES (?, ?, 1)"
            " ON CONFLICT(day) DO UPDATE SET tokens = tokens + excluded.tokens,"
            " questions = questions + 1",
            (now()[:10], tokens),
        )

    def usage_today(self) -> dict:
        row = self.conn.execute(
            "SELECT tokens, questions FROM ai_usage WHERE day = ?", (now()[:10],)
        ).fetchone()
        return dict(row) if row else {"tokens": 0, "questions": 0}

    def audit(
        self, correlation_id: str, entity_type: str, entity_id: str, action: str, detail: dict
    ) -> None:
        self.conn.execute(
            "INSERT INTO audit_log (ts, correlation_id, entity_type, entity_id, action, detail)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (now(), correlation_id, entity_type, entity_id, action, json.dumps(detail)),
        )

    def audit_for(self, entity_id: str) -> list[dict]:
        return self.rows(
            "SELECT * FROM audit_log WHERE entity_id = ? OR correlation_id = ? ORDER BY id",
            (entity_id, entity_id),
            "detail",
        )

    def audit_tail(self, limit: int = 100) -> list[dict]:
        return self.rows("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,), "detail")

    def audit_page(
        self,
        kinds: list[str] | None = None,
        entity: str = "",
        since: str = "",
        until: str = "",
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        params = {
            "kinds": None if kinds is None else json.dumps(kinds),
            "entity": entity,
            "since": since,
            "until": until,
            "limit": limit,
            "offset": offset,
        }
        return self.page("audit_log", AUDIT_FILTER, "id DESC", params, "detail")

    def audit_between(self, since: str, until: str) -> list[dict]:
        # By time first: loaded sample history has later ids than live rows but older times.
        return self.rows(
            "SELECT * FROM audit_log WHERE ts >= ? AND ts < ? ORDER BY ts, id",
            (since, until),
            "detail",
        )

    def audit_after(self, after_id: int, limit: int) -> list[dict]:
        return self.rows(
            "SELECT * FROM audit_log WHERE id > ? ORDER BY id LIMIT ?", (after_id, limit), "detail"
        )

    def timeline(self, order_id: str) -> list[dict]:
        # Pulls in rows that share a correlation id with the order, e.g. the inbound event
        # and the stock pushes it triggered.
        return self.rows(
            "SELECT * FROM audit_log WHERE entity_id = ? OR correlation_id IN"
            " (SELECT correlation_id FROM audit_log WHERE entity_id = ?) ORDER BY id",
            (order_id, order_id),
            "detail",
        )

    def counters(self, since: str = "", until: str = "") -> dict[str, int]:
        rows = self.rows(
            "SELECT action, COUNT(*) AS n FROM audit_log"
            " WHERE ts >= :since AND (:until = '' OR ts < :until) GROUP BY action",
            {"since": since, "until": until},
        )
        return {row["action"]: row["n"] for row in rows}
