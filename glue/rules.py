import logging

from glue import review
from glue.audit import record
from glue.context import Context

log = logging.getLogger(__name__)

# What a rule does before an admin ever saves it; an empty sku means every SKU.
DEFAULTS = {
    "stock-buffer": {"channel": "emag", "units": 1, "sku": ""},
    "auto-retry": {},
}


def all_rules(ctx: Context) -> dict[str, dict]:
    stored = {row["name"]: row | {"enabled": bool(row["enabled"])} for row in ctx.db.rules()}
    return {
        name: {
            "name": name,
            "enabled": False,
            "config": config,
            "updated_by": None,
            "updated_at": None,
        }
        | stored.get(name, {})
        for name, config in DEFAULTS.items()
    }


def get(ctx: Context, name: str) -> dict:
    return all_rules(ctx)[name]


def save(ctx: Context, name: str, enabled: bool, config: dict, user: str) -> None:
    ctx.db.set_rule(name, enabled, config, user)
    record(ctx.db, f"rule-{name}", "rule", name, "rule_changed", enabled=enabled, by=user, **config)


def held_back(ctx: Context, channel: str, skus: list[str]) -> dict[str, int]:
    rule = get(ctx, "stock-buffer")
    config = rule["config"]
    applies = bool(rule["enabled"]) and config["channel"] == channel
    return {sku: config["units"] if applies and config["sku"] in ("", sku) else 0 for sku in skus}


async def retry_after_recovery(ctx: Context, correlation_id: str) -> None:
    if not get(ctx, "auto-retry")["enabled"]:
        return
    for item in ctx.db.list_review():
        order = ctx.db.get_order(item["order_id"]) if item["order_id"] else None
        technical = item["kind"] == "order_failed"
        placing = item["payload"].get("operation", "place") == "place"
        if not (technical and placing and "retry" in review.allowed_actions(item, order)):
            continue
        record(
            ctx.db,
            correlation_id,
            "order",
            item["order_id"],
            "rule_applied",
            rule="auto-retry",
            review_id=item["id"],
        )
        try:
            await review.decide(ctx, item["id"], "retry", decided_by="rule:auto-retry")
        except Exception as exc:
            # decide has already re-queued the order with the new reason.
            log.warning("auto-retry of %s failed: %s", item["order_id"], exc)
