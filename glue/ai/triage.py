import re

from glue import queries, ranges, tuning
from glue.ai import triage_prompt
from glue.audit import record
from glue.context import Context

# No lookup tools: handed the facts, the small local model answers to the point; given tools,
# it wanders off into lookups and drifts from the rule.
SYSTEM = (
    "You help an operator decide what to do with an order that Glue, an order router, could not"
    " finish. Use only the facts given. Be brief and plain. You cannot change anything."
)
ANSWER = re.compile(r"ACTION:\s*(\w+)\s*REASON:\s*(.+)", re.IGNORECASE | re.DOTALL)
ORDER_ID = re.compile(r"\b(?:shop|emag)-(?:sample-)?\d+\b", re.IGNORECASE)
# Tool, function and field names: words joined by underscores never occur in plain English.
CODE_NAME = re.compile(r"\b[a-z]+(?:_[a-z0-9]+)+\b", re.IGNORECASE)


async def ask_model(ctx: Context, question: str) -> str:
    tokens = 0
    try:
        response = await ctx.assistant.chat.completions.create(
            model=ctx.settings.llm_model,
            messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": question}],
            max_tokens=tuning.ai_limits(ctx.db)["max_tokens_per_question"],
            temperature=0,
        )
        tokens = response.usage.total_tokens if response.usage else 0
    finally:
        ctx.db.add_usage(ranges.today(ctx.settings.zone), tokens)
    return response.choices[0].message.content or ""


def without_code_names(reason: str) -> str:
    # A name like list_review_items means nothing to an operator; the rest of the reason may.
    sentences = re.split(r"(?<=[.!?])\s+", reason)
    return " ".join(s for s in sentences if not CODE_NAME.search(s))


def foreign_order(reason: str, order_id: str | None) -> str | None:
    others = sorted({found.lower() for found in ORDER_ID.findall(reason)} - {order_id})
    return others[0] if others else None


async def suggest(ctx: Context, item_id: int) -> None:
    item = queries.review_item(ctx, ctx.db.get_review(item_id))
    order = ctx.db.get_order(item["order_id"]) if item["order_id"] else None
    stock = {row["sku"]: row for row in ctx.db.stock()}
    answering = (await queries.check_health(ctx.http, ctx.settings.warehouse_url))["ok"]
    answer = await ask_model(ctx, triage_prompt.question(item, order, stock, answering))
    match = ANSWER.search(answer)
    action = match.group(1).lower() if match else None
    reason = without_code_names((match.group(2) if match else answer).strip()[:2000])
    if action not in item["allowed"]:
        action = None
    if not reason:
        action, reason = None, "No suggestion this time: ask again."
    # A different order id in the reasoning means the model mixed up orders.
    other = foreign_order(reason, item["order_id"])
    if other:
        action = None
        reason += f"\n\nNo choice suggested: this reasoning is about {other}, not this order."
    ctx.db.set_suggestion(item_id, action, reason)
    record(
        ctx.db,
        f"review-{item_id}",
        "order",
        item["order_id"] or "-",
        "triage_suggested",
        review_id=item_id,
        suggested=action or "none",
        reason=reason[:300],
    )
