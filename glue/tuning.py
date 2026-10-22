from dataclasses import dataclass, fields, replace
from typing import TYPE_CHECKING

from glue.audit import record
from glue.db import Database
from glue.settings import Settings

if TYPE_CHECKING:
    from glue.context import Context

LIMITS = {
    "retry_attempts": (1, 10),
    "retry_base_seconds": (0.1, 10),
    "reconcile_interval_seconds": (2, 300),
}
AI_KEYS = {
    "effort": "ai_effort",
    "max_tokens_per_question": "ai_max_tokens",
    "daily_token_budget": "ai_daily_budget",
}


@dataclass(frozen=True)
class Tuning:
    retry_attempts: int
    retry_base_seconds: float
    reconcile_interval_seconds: float


def load(db: Database, settings: Settings) -> Tuning:
    stored = db.settings()
    values = {}
    for field in fields(Tuning):
        raw = stored.get(field.name)
        values[field.name] = getattr(settings, field.name) if raw is None else field.type(raw)
    return Tuning(**values)


def save(ctx: "Context", values: dict, user: str) -> Tuning:
    for key, value in values.items():
        low, high = LIMITS[key]
        if not low <= value <= high:
            raise ValueError(f"{key} must be between {low} and {high}")
    changed = {key: value for key, value in values.items() if value != getattr(ctx.tuning, key)}
    for key, value in changed.items():
        ctx.db.set_setting(key, str(value), user)
    if changed:
        record(ctx.db, "settings", "settings", "settings", "settings_changed", by=user, **changed)
    ctx.tuning = replace(ctx.tuning, **changed)
    return ctx.tuning


def ai_limits(db: Database) -> dict:
    stored = db.settings()
    return {
        "effort": stored.get("ai_effort", "medium"),
        "max_tokens_per_question": int(stored.get("ai_max_tokens", 2000)),
        "daily_token_budget": int(stored.get("ai_daily_budget", 200000)),
    }


def save_ai_limits(ctx: "Context", values: dict, user: str) -> None:
    current = ai_limits(ctx.db)
    changed = {key: value for key, value in values.items() if value != current[key]}
    for key, value in changed.items():
        ctx.db.set_setting(AI_KEYS[key], str(value), user)
    if changed:
        record(ctx.db, "settings", "settings", "settings", "settings_changed", by=user, **changed)
