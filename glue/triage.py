import re

from glue import assistant, views
from glue.audit import record
from glue.context import Context

PROMPT = (
    "Review item {id} is waiting for a decision. Kind: {kind}. Reason: {reason}. Order: {order}."
    " The person may choose one of: {allowed}. Look up the order's timeline and the stock of its"
    " SKUs with the tools, then recommend exactly one of those choices. Answer in two lines:"
    " 'ACTION: <choice>' then 'REASON: <one paragraph citing the facts you found>'."
)
ANSWER = re.compile(r"ACTION:\s*(\w+)\s*REASON:\s*(.+)", re.IGNORECASE | re.DOTALL)


async def suggest(ctx: Context, item_id: int) -> None:
    card = views.review_card(ctx, item_id)
    item, allowed = card["item"], sorted(card["allowed"])
    question = PROMPT.format(
        id=item_id,
        kind=item["kind"],
        reason=item["reason"],
        order=item["order_id"] or "none",
        allowed=", ".join(allowed),
    )
    answer = await assistant.ask(ctx, [{"role": "user", "content": question}])
    match = ANSWER.search(answer)
    action = match.group(1).lower() if match else None
    reason = (match.group(2) if match else answer).strip()[:2000]
    if action not in allowed:
        action = None
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
