import json
import logging
import sys
from datetime import UTC, datetime

from glue.db import Database

ACTIONS = frozenset(
    {
        "event_received",
        "duplicate_dropped",
        "signature_rejected",
        "event_rejected",
        "order_known",
        "allocation_resumed",
        "event_failed",
        "emag_acknowledged",
        "order_allocated",
        "retry_scheduled",
        "order_failed",
        "unfulfillable",
        "order_shipped",
        "order_cancelled",
        "placed_after_cancel",
        "stock_pushed",
        "stock_push_failed",
        "warehouse_unreachable",
        "review_opened",
        "review_decided",
        "review_resolved",
        "rule_changed",
        "rule_applied",
        "settings_changed",
        "triage_suggested",
        "signed_in",
        "sign_in_rejected",
    }
)

log = logging.getLogger("glue.audit")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        line = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            **getattr(record, "fields", {}),
        }
        if record.exc_info:
            line["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(line, default=str)


def configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)
    # httpx logs a line per outbound request; the audit log is the record that matters.
    logging.getLogger("httpx").setLevel(logging.WARNING)


def record(
    db: Database, correlation_id: str, entity_type: str, entity_id: str, action: str, **detail
) -> None:
    if action not in ACTIONS:
        raise ValueError(f"unknown audit action {action!r}")
    db.audit(correlation_id, entity_type, entity_id, action, detail)
    fields = {
        "correlation_id": correlation_id,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "action": action,
        **detail,
    }
    log.info(action, extra={"fields": fields})
