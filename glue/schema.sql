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
    created_at TEXT NOT NULL,
    suggested_action TEXT,
    suggested_reason TEXT
);

CREATE TABLE IF NOT EXISTS rules (
    name       TEXT PRIMARY KEY,
    enabled    INTEGER NOT NULL DEFAULT 0,
    config     TEXT NOT NULL DEFAULT '{}',
    updated_by TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    updated_by TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ai_usage (
    day       TEXT PRIMARY KEY,
    tokens    INTEGER NOT NULL,
    questions INTEGER NOT NULL
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
