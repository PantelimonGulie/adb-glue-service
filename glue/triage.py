import re

from common.catalog import product_name
from glue import queries, tuning
from glue.audit import record
from glue.context import Context

CAUSES = {
    "outage": "the Bucharest warehouse did not answer when Glue sent the order",
    "soldout": "the last unit was sold on the other channel first, so the warehouse refused it",
    "recount": "the warehouse counted fewer units than are promised to customers",
    "other": "something else went wrong, see what Glue saw",
}
CHANNELS = {"shop": "the shop", "emag": "eMAG"}
# No lookup tools: handed the facts, the small local model answers to the point; given tools,
# it wanders off into lookups and drifts from the rule.
SYSTEM = (
    "You help an operator decide what to do with an order that Glue, an order router, could not"
    " finish. Use only the facts given. Be brief and plain. You cannot change anything."
)
PROMPT = (
    "Review item {id} needs a decision. The facts:\n{facts}\n"
    "The person may choose one of:\n{choices}\n"
    "Rule for this cause: {playbook}.\n"
    "Use these facts. Recommend exactly one of those choices. Answer in two lines:"
    " 'ACTION: <choice>' then 'REASON: <one short paragraph citing the facts>'."
)
ANSWER = re.compile(r"ACTION:\s*(\w+)\s*REASON:\s*(.+)", re.IGNORECASE | re.DOTALL)
ORDER_ID = re.compile(r"\b(?:shop|emag)-(?:sample-)?\d+\b", re.IGNORECASE)


def facts(item: dict, order: dict | None, free: dict[str, int], answering: bool) -> str:
    lines = [f"- Cause: {CAUSES[item['cause']]}.", f"- What Glue saw: {item['reason']}."]
    if order:
        channel = CHANNELS[order["channel"]]
        lines.append(f"- Order {order['order_id']} came from {channel}; now {order['status']}.")
        for line in order["lines"]:
            stock = free.get(line["sku"], "unknown")
            name = product_name(line["sku"])
            lines.append(f"- It asks for {line['qty']} × {name}; {stock} free in the warehouse.")
    state = "is answering" if answering else "is not answering"
    lines.append(f"- The Bucharest warehouse {state} right now.")
    return "\n".join(lines)


# The small local model follows a rule that names one choice, but not a conditional one,
# so the condition is checked here and the model only explains it.
def playbook(cause: str, order: dict | None, free: dict[str, int], answering: bool) -> str:
    if cause == "outage" and answering:
        return "the warehouse is answering again, so suggest retry"
    if cause == "outage":
        return "the warehouse is not answering yet, so suggest retry once it answers"
    if cause in ("soldout", "recount") and order:
        if all(free.get(line["sku"], 0) >= line["qty"] for line in order["lines"]):
            return "the free stock covers every quantity, so suggest retry"
        return "the free stock is less than the quantity asked, so suggest cancel"
    if not order or order["status"] in ("shipped", "cancelled"):
        return "the order is settled, so suggest dismiss"
    return f"the order is still {order['status']}, so suggest retry or cancel, not dismiss"


def choices(allowed: list[str], order: dict | None) -> str:
    channel = CHANNELS[order["channel"]] if order else "its channel"
    what = {
        "retry": "sends the order to the Bucharest warehouse again",
        "cancel": f"cancels the order on the customer's channel ({channel})",
        "dismiss": "closes this item without changing anything",
    }
    return "\n".join(f"- {action}: {what[action]}" for action in allowed)


async def ask_model(ctx: Context, question: str) -> str:
    tokens = 0
    try:
        response = await ctx.assistant.chat.completions.create(
            model=ctx.settings.llm_model,
            messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": question}],
            max_tokens=tuning.ai_limits(ctx.db)["max_tokens_per_question"],
        )
        tokens = response.usage.total_tokens if response.usage else 0
    finally:
        ctx.db.add_usage(tokens)
    return response.choices[0].message.content or ""


def foreign_order(reason: str, order_id: str | None) -> str | None:
    others = sorted({found.lower() for found in ORDER_ID.findall(reason)} - {order_id})
    return others[0] if others else None


async def suggest(ctx: Context, item_id: int) -> None:
    item = queries.review_item(ctx, ctx.db.get_review(item_id))
    order = ctx.db.get_order(item["order_id"]) if item["order_id"] else None
    allowed = item["allowed"]
    free = {row["sku"]: max(0, row["available"]) for row in ctx.db.stock()}
    answering = (await queries.check_health(ctx.http, ctx.settings.warehouse_url))["ok"]
    question = PROMPT.format(
        id=item_id,
        facts=facts(item, order, free, answering),
        choices=choices(allowed, order),
        playbook=playbook(item["cause"], order, free, answering),
    )
    answer = await ask_model(ctx, question)
    match = ANSWER.search(answer)
    action = match.group(1).lower() if match else None
    reason = (match.group(2) if match else answer).strip()[:2000]
    if action not in allowed:
        action = None
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
