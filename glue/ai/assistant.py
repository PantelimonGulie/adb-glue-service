import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from glue import queries, tuning
from glue.context import Context

ROUNDS = {"low": 2, "medium": 4, "high": 6}
SYSTEM = (
    "You are the operations assistant for the Glue platform, which routes orders from the shop"
    " (Electronic Market) and eMAG to one warehouse and pushes true stock back to both channels."
    " Answer only from tool results; call tools before answering. Cite order ids, channels and"
    " UTC timestamps. If the tools do not show it, say you do not know. Be brief: a few sentences"
    " or a short list, plain text without markdown. You are read-only and cannot change anything."
)


@dataclass(frozen=True)
class AskResult:
    answer: str
    tools: list[str]
    tokens: int


def get_summary(ctx: Context, hours: int = 1) -> dict:
    hours = min(max(int(hours), 1), 168)
    since = (datetime.now(UTC) - timedelta(hours=hours)).isoformat(timespec="milliseconds")
    orders, _ = ctx.db.list_orders(since=since, limit=30)
    keys = ("order_id", "channel", "status", "attempts", "last_error", "updated_at")
    return {
        "hours": hours,
        "counters": ctx.db.counters(since),
        "orders_changed": [{k: o[k] for k in keys} for o in orders],
    }


def list_review_items(ctx: Context) -> list[dict]:
    return ctx.db.list_review()


def get_order(ctx: Context, order_id: str) -> dict:
    order_id = str(order_id)[:64]
    order = ctx.db.get_order(order_id)
    if order is None:
        return {"error": f"order {order_id} not found"}
    return {"order": order, "timeline": ctx.db.timeline(order_id)}


def get_stock(ctx: Context, sku: str) -> dict:
    sku = str(sku)[:64]
    row = next((r for r in queries.stock_rows(ctx) if r["sku"] == sku), None)
    return row or {"error": f"sku {sku} not found"}


TOOLS = {
    "get_summary": (
        get_summary,
        "Counts per action in the audit log and the orders changed in the last `hours` hours.",
        {"hours": {"type": "integer", "description": "1 to 168"}},
    ),
    "list_review_items": (list_review_items, "Open review items waiting for a decision.", {}),
    "get_order": (
        get_order,
        "One order with its full audit timeline.",
        {"order_id": {"type": "string"}},
    ),
    "get_stock": (
        get_stock,
        "Warehouse stock for a SKU, what should be sellable, and what each channel was last told.",
        {"sku": {"type": "string"}},
    ),
}
TOOL_SPECS = [
    {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": params, "required": list(params)},
        },
    }
    for name, (_, description, params) in TOOLS.items()
]


def run_tool(ctx: Context, name: str, arguments: str) -> str:
    try:
        result = TOOLS[name][0](ctx, **json.loads(arguments or "{}"))
    except (KeyError, TypeError, ValueError) as exc:
        result = {"error": f"bad tool call: {exc}"}
    return json.dumps(result, default=str)


async def ask(ctx: Context, turns: list[dict]) -> AskResult:
    limits = tuning.ai_limits(ctx.db)
    messages = [{"role": "system", "content": SYSTEM}, *turns]
    answer = "I could not find the answer within the allowed number of lookups."
    tools: list[str] = []
    tokens = 0
    try:
        for _ in range(ROUNDS[limits["effort"]]):
            response = await ctx.assistant.chat.completions.create(
                model=ctx.settings.llm_model,
                messages=messages,
                tools=TOOL_SPECS,
                max_tokens=limits["max_tokens_per_question"],
            )
            tokens += response.usage.total_tokens if response.usage else 0
            message = response.choices[0].message
            if not message.tool_calls:
                answer = message.content or "I do not know."
                break
            calls = [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {"name": call.function.name, "arguments": call.function.arguments},
                }
                for call in message.tool_calls
            ]
            messages.append(
                {"role": "assistant", "content": message.content or "", "tool_calls": calls}
            )
            for call in message.tool_calls:
                if call.function.name not in tools:
                    tools.append(call.function.name)
                content = run_tool(ctx, call.function.name, call.function.arguments)
                messages.append({"role": "tool", "tool_call_id": call.id, "content": content})
    finally:
        ctx.db.add_usage(tokens)
    return AskResult(answer, tools, tokens)
