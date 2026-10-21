import json
from datetime import UTC, datetime, timedelta

import httpx
from openai import APIConnectionError, APIStatusError, AsyncOpenAI, RateLimitError

from glue import views
from glue.context import Context
from glue.settings import Settings

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
MAX_ROUNDS = 6
SYSTEM = (
    "You are the operations assistant for the Glue platform, which routes orders from the shop"
    " (Electronic Market) and eMAG to one warehouse and pushes true stock back to both channels."
    " Answer only from tool results; call tools before answering. Cite order ids, channels and"
    " UTC timestamps. If the tools do not show it, say you do not know. Be brief: a few sentences"
    " or a short list, plain text without markdown. You are read-only and cannot change anything."
)


def client(settings: Settings, http: httpx.AsyncClient) -> AsyncOpenAI | None:
    if not settings.gemini_api_key:
        return None
    return AsyncOpenAI(
        api_key=settings.gemini_api_key, base_url=GEMINI_URL, http_client=http, timeout=30
    )


def get_summary(ctx: Context, hours: int = 1) -> dict:
    hours = min(max(int(hours), 1), 168)
    since = (datetime.now(UTC) - timedelta(hours=hours)).isoformat(timespec="milliseconds")
    orders = [o for o in ctx.db.list_orders() if o["updated_at"] >= since][:30]
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
    row = next((r for r in views.stock(ctx)["rows"] if r["sku"] == sku), None)
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


async def ask(ctx: Context, turns: list[dict]) -> str:
    messages = [{"role": "system", "content": SYSTEM}, *turns]
    for _ in range(MAX_ROUNDS):
        response = await ctx.assistant.chat.completions.create(
            model=ctx.settings.gemini_model, messages=messages, tools=TOOL_SPECS
        )
        message = response.choices[0].message
        if not message.tool_calls:
            return message.content or "I do not know."
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
            content = run_tool(ctx, call.function.name, call.function.arguments)
            messages.append({"role": "tool", "tool_call_id": call.id, "content": content})
    return "I could not find the answer within the allowed number of lookups."


def failure_message(exc: Exception) -> str:
    if isinstance(exc, RateLimitError):
        return "The model is rate limited right now. Try again in a minute."
    if isinstance(exc, APIStatusError):
        return f"The model API refused the request (HTTP {exc.status_code}). Check GEMINI_API_KEY."
    if isinstance(exc, APIConnectionError):
        return "Could not reach the model API. Check the network and try again."
    return "The assistant hit an unexpected error. It is logged; try again."


def parse_history(raw: str) -> list[dict]:
    try:
        turns = json.loads(raw or "[]")
    except ValueError:
        return []
    if not isinstance(turns, list):
        return []
    clean = [
        {"role": t["role"], "content": t["content"][:4000]}
        for t in turns
        if isinstance(t, dict)
        and t.get("role") in ("user", "assistant")
        and isinstance(t.get("content"), str)
    ]
    return clean[-12:]
