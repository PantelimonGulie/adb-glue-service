import inspect
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from common.catalog import PRODUCTS
from glue import queries, ranges, tuning
from glue.ai import facts
from glue.context import Context

ROUNDS = {"low": 2, "medium": 4, "high": 6}
SYSTEM = (
    "You are the operations assistant for Glue. Glue takes orders from two sales channels,"
    " sends each one to the single Bucharest warehouse, and keeps the stock both channels show"
    " in step with the warehouse.\n"
    "Words: 'the shop' is Electronic Market, the reseller's own web shop (built on Adobe"
    " Commerce). 'eMAG' is the eMAG Marketplace, a separate channel where the reseller also"
    " sells. Never mix the two up.\n"
    "Rules: answer from the live facts below and from tool results only; if they do not show"
    " it, say you do not know. Name products by their names; never use product codes and never"
    " say 'SKU'. Never mention tool names. Times are Bucharest time. If the figures match, say"
    " they match and that nothing is out of step; never invent numbers. Say what happened and why;"
    " give no advice unless asked. Be brief: a few sentences or a short list, plain text"
    " without markdown. You are read-only and cannot change anything."
)


@dataclass(frozen=True)
class AskResult:
    answer: str
    tools: list[str]
    tokens: int


def get_summary(ctx: Context, hours: int = 1) -> dict:
    hours = min(max(int(hours), 1), 168)
    since = ranges.stamp(datetime.now(UTC) - timedelta(hours=hours))
    counts = queries.counters(ctx, since, "")
    failed, _ = ctx.db.list_orders(status="failed", since=since, limit=20)
    return {
        "hours": hours,
        "orders in": counts["received"],
        "reserved": counts["reserved"],
        "failed": counts["failed"],
        "calls retried": counts["retries"],
        "duplicates ignored": counts["duplicates"],
        "stock updates refused": ctx.db.counters(since).get("stock_push_failed", 0),
        "failed orders": [facts.order(row) for row in failed],
    }


def list_review_items(ctx: Context) -> list[dict]:
    items = []
    for item in ctx.db.list_review()[::-1][:20]:
        shown = queries.review_item(ctx, item)
        about = {"order": item["order_id"], "why": facts.CAUSES[shown["cause"]]}
        if shown["order"]:
            about["from"] = facts.CHANNELS[shown["order"]["channel"]]
            about["products"] = f"{shown['order']['qty']} × {shown['order']['product']}"
        if shown["winner"]:
            winner = shown["winner"]
            about["the last unit went to"] = (
                f"{winner['order_id']} from {facts.CHANNELS[winner['channel']]}"
            )
        items.append(about | {"what happened": item["reason"], "since": item["created_at"]})
    return items


def get_order(ctx: Context, order_id: str) -> dict:
    order_id = str(order_id)[:64]
    row = ctx.db.get_order(order_id)
    if row is None:
        return {"error": f"Glue has no order {order_id}"}
    history = [
        {"at": step["ts"], "step": step["action"].replace("_", " ")}
        | {key.replace("_", " "): value for key, value in step["detail"].items() if key != "error"}
        for step in ctx.db.timeline(order_id)
    ]
    return {"order": facts.order(row), "history": history}


def get_stock(ctx: Context, product: str) -> list[dict] | dict:
    wanted = str(product).lower()[:64]
    rows = [
        {
            "product": row["product"],
            "on the shelf": row["on_hand"],
            "reserved for orders": row["reserved"],
            "free to sell": row["free"],
            "the shop": facts.told(ctx, row, "shop"),
            "eMAG": facts.told(ctx, row, "emag"),
            "in short": facts.STOCK_STATES[row["state"]],
        }
        for row in queries.stock_rows(ctx)
        if wanted in f"{row['sku']} {PRODUCTS.get(row['sku'], '')}".lower()
    ]
    return rows or {"error": f"no product matches {product!r}"}


async def get_system_health(ctx: Context) -> dict:
    health = await queries.health_of(ctx)
    return {
        facts.SYSTEMS[name]: {"state": facts.STATES[h["state"]], "answer time ms": h["latency_ms"]}
        for name, h in health.items()
    }


TOOLS = {
    "get_system_health": (
        get_system_health,
        "Whether the shop, eMAG and the Bucharest warehouse answer right now.",
        {},
    ),
    "get_summary": (
        get_summary,
        "What came in, what was reserved and what failed in the last `hours` hours.",
        {"hours": {"type": "integer", "description": "1 to 168"}},
    ),
    "list_review_items": (
        list_review_items,
        "The orders waiting for a person to decide, newest first.",
        {},
    ),
    "get_order": (
        get_order,
        "One order and everything that happened to it.",
        {"order_id": {"type": "string", "description": "e.g. shop-1042 or emag-254867525"}},
    ),
    "get_stock": (
        get_stock,
        "Stock for a product: the shelf, the reservations, and what each channel shows.",
        {"product": {"type": "string", "description": "a product name, e.g. MacBook"}},
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


async def run_tool(ctx: Context, name: str, arguments: str) -> str:
    try:
        result = TOOLS[name][0](ctx, **json.loads(arguments or "{}"))
        if inspect.isawaitable(result):
            result = await result
    except (KeyError, TypeError, ValueError) as exc:
        result = {"error": f"bad tool call: {exc}"}
    return facts.readable(json.dumps(result, default=str), ctx.settings.zone)


async def ask(ctx: Context, turns: list[dict]) -> AskResult:
    limits = tuning.ai_limits(ctx.db)
    system = f"{SYSTEM}\n\n{await facts.live(ctx)}"
    messages = [{"role": "system", "content": system}, *turns]
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
                # The same question gets the same answer; a small model wanders when it samples.
                temperature=0,
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
                content = await run_tool(ctx, call.function.name, call.function.arguments)
                messages.append({"role": "tool", "tool_call_id": call.id, "content": content})
    finally:
        ctx.db.add_usage(tokens)
    return AskResult(answer, tools, tokens)
