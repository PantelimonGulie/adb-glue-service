import json
from datetime import UTC, datetime
from types import SimpleNamespace

import httpx
from openai import APITimeoutError

from common.catalog import PRODUCTS
from glue import queries, ranges
from glue.ai import llm

QUESTION = "Which orders need a decision?"


async def ask(systems, **body: object) -> httpx.Response:
    return await systems.act("/api/assistant/ask", question=QUESTION, **body)


async def assistant_state(systems) -> dict:
    response = await systems.http.get("http://glue/api/assistant")
    assert response.status_code == 200
    return response.json()


async def test_assistant_reports_model_and_defaults(systems):
    state = await assistant_state(systems)

    assert state["model"] == {
        "id": "local",
        "label": "Local model (Ollama, Qwen 2.5 3B)",
        "status": "ready",
        "progress": 1.0,
    }
    assert [(m["id"], m["available"]) for m in state["models"]] == [
        ("local", True),
        ("claude", False),
        ("gpt", False),
        ("gemini", False),
    ]
    assert (state["effort"], state["max_tokens_per_question"]) == ("medium", 2000)
    assert (state["daily_token_budget"], state["used_today"], state["questions_today"]) == (
        200000,
        0,
        0,
    )


async def test_ask_while_downloading_returns_503(systems):
    model = systems.use_model("unused")
    systems.ctx.model_status, systems.ctx.model_progress = "downloading", 0.42

    response = await ask(systems)

    assert response.status_code == 503
    assert "downloading (42%)" in response.json()["detail"]
    assert (await assistant_state(systems))["model"]["status"] == "downloading"
    assert model.requests == []


async def test_ask_records_usage(systems):
    model = systems.use_model("Nothing is waiting for a decision.", [("list_review_items", {})])
    history = [{"role": "user", "content": "Hi"}, {"role": "assistant", "content": "Hello."}]

    response = await ask(systems, history=history)

    assert response.json() == {
        "answer": "Nothing is waiting for a decision.",
        "tools": ["list_review_items"],
        "tokens": 120,
    }
    assert model.requests[0]["messages"][1:4] == [*history, {"role": "user", "content": QUESTION}]
    assert (model.requests[0]["max_tokens"], model.requests[0]["temperature"]) == (2000, 0)
    state = await assistant_state(systems)
    assert (state["used_today"], state["questions_today"]) == (120, 1)


async def test_the_prompt_carries_live_facts_and_the_words_to_use(systems, sleeps):
    await systems.chaos("warehouse", down=True)
    order_id = await systems.buy_on_shop("MBA-M4")
    await systems.run_worker()
    retried = queries.counters(systems.ctx, "", "")["retries"]
    model = systems.use_model("No, the Bucharest warehouse is not answering.")

    await systems.act("/api/assistant/ask", question="Is the warehouse working?")

    system = model.requests[0]["messages"][0]["content"]
    assert "the shop (Electronic Market): working" in system
    assert "the Bucharest warehouse: not answering" in system
    assert "Waiting for a person: 1 warehouse outage." in system
    assert "- In the last hour 1 order came in; 0 of them were reserved at the warehouse." in system
    assert (
        f"- Glue retried {retried} calls in the last hour, across all orders and systems." in system
    )
    assert "- Glue ignored 0 duplicate messages in the last hour." in system
    assert "- 1 order that came in during the last hour failed:" in system
    assert (
        f"  - {order_id} from the shop, 1 × MacBook Air M4. Cause: warehouse outage."
        " Now: failed, waiting for a person." in system
    )
    assert "'the shop' is Electronic Market" in system
    assert "never say 'SKU'" in system
    assert "  - MacBook Air M4: 1 free; the shop shows 1; eMAG shows 1; in step." in system
    assert not any(code in system for code in PRODUCTS)


async def test_the_prompt_carries_every_product_when_nothing_is_out_of_step(systems):
    model = systems.use_model("Both channels show 1 MacBook Air M4.")

    await systems.act("/api/assistant/ask", question="Why is the MacBook different on eMAG?")

    system = model.requests[0]["messages"][0]["content"]
    lines = [line for line in system.splitlines() if line.startswith("  - ")]
    assert sorted(line.split(":")[0] for line in lines) == sorted(
        f"  - {name}" for name in PRODUCTS.values()
    )
    assert "  - MacBook Air M4: 1 free; the shop shows 1; eMAG shows 1; in step." in lines
    assert "If the figures match, say they match and that nothing is out of step" in system
    assert "never invent numbers" in system
    assert "- No order failed in the last hour." in system


async def test_an_order_that_failed_and_was_cancelled_is_still_named_as_failed(systems, sleeps):
    await systems.chaos("emag", freeze_stock=True)
    await systems.buy_on_shop("MBA-M4")
    await systems.run_worker()
    order_id = await systems.buy_on_emag("MBA-M4")
    await systems.run_worker()
    await systems.http.post(f"http://emag/orders/{order_id.removeprefix('emag-')}/cancel")
    await systems.run_worker()
    model = systems.use_model("One eMAG order failed.", [("get_summary", {"hours": 1})])

    await systems.act("/api/assistant/ask", question="What failed in the last hour?")

    system = model.requests[0]["messages"][0]["content"]
    failed = system.index("- 1 order that came in during the last hour failed:")
    assert system.index("  - MacBook Air M4: ") < failed
    assert (
        f"  - {order_id} from eMAG, 1 × MacBook Air M4. Cause: sold on the other channel."
        " Now: cancelled." in system
    )
    summary = json.loads(model.requests[-1]["messages"][-1]["content"])
    assert summary["failed"] == 1
    assert [order["order"] for order in summary["failed orders"]] == [order_id]


async def test_the_prompt_names_stock_a_channel_shows_differently(systems):
    await systems.chaos("emag", reject_sku="MBA-M4")
    await systems.recount("MBA-M4", 3)
    await systems.run_worker()
    model = systems.use_model("eMAG refused the update.")

    await systems.act("/api/assistant/ask", question="Why is the MacBook different on eMAG?")

    system = model.requests[0]["messages"][0]["content"]
    assert (
        "  - MacBook Air M4: 3 free; the shop shows 3;"
        " eMAG refused the update to 3, so it still shows 1; out of step." in system
    )


async def test_tools_answer_in_product_names_and_plain_words(systems, sleeps):
    order_id = await systems.buy_on_shop("MBA-M4")
    await systems.run_worker()
    await systems.chaos("emag", reject_sku="MBA-M4")
    await systems.recount("MBA-M4", 3)
    await systems.run_worker()
    calls = [
        ("get_system_health", {}),
        ("get_stock", {"product": "macbook"}),
        ("get_order", {"order_id": order_id}),
        ("get_summary", {"hours": 1}),
        ("list_review_items", {}),
    ]
    model = systems.use_model("eMAG refused the last MacBook update.", calls)
    await systems.sign_in("admin")
    await systems.put("/api/assistant/settings", effort="high")

    response = await systems.act("/api/assistant/ask", question="Why is the MacBook different?")

    results = [m["content"] for m in model.requests[-1]["messages"] if m["role"] == "tool"]
    assert response.json()["tools"] == [name for name, _ in calls]
    health, stock, order, summary, review = (json.loads(result) for result in results)
    assert health["the Bucharest warehouse"]["state"] == "working"
    assert stock[0]["product"] == "MacBook Air M4"
    assert stock[0]["eMAG"] == "refused the update to 2, so it still shows 0"
    assert stock[0]["in short"] == "eMAG refused the last stock update"
    assert order["order"]["products"] == "1 × MacBook Air M4"
    assert summary["orders in"] == 1
    assert review == []
    for result in results:
        assert "MBA-M4" not in result
        assert "sku" not in result.lower()
        assert "+00:00" not in result


async def test_a_review_item_reaches_the_model_as_its_plain_cause_never_its_stored_text(systems):
    raw = (
        "unexpected while handling emag.notification: HTTPStatusError: Client error"
        " '404 Not Found' for url 'http://emag:8002/api-3/order/read'"
    )
    systems.ctx.db.open_review("order_failed", "emag-254867525", {"operation": "place"}, raw)
    model = systems.use_model("One eMAG order needs a decision.", [("list_review_items", {})])

    await ask(systems)

    [result] = [m["content"] for m in model.requests[-1]["messages"] if m["role"] == "tool"]
    [item] = json.loads(result)
    assert (item["order"], item["why"]) == ("emag-254867525", "other problem")
    assert item["what that means"] == "something else went wrong while Glue handled this order"
    assert not any(
        raw_text in result for raw_text in ("404", "http", "HTTPStatusError", "unexpected")
    )


async def test_the_token_budget_day_turns_at_midnight_in_bucharest(systems, monkeypatch):
    clock = {"now": datetime(2026, 10, 22, 20, 59, tzinfo=UTC)}

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return clock["now"].astimezone(tz)

    monkeypatch.setattr(ranges, "datetime", Clock)
    systems.use_model("Nothing is waiting for a decision.")

    await ask(systems)
    before_midnight = await assistant_state(systems)
    clock["now"] = datetime(2026, 10, 22, 21, 1, tzinfo=UTC)
    after_midnight = await assistant_state(systems)
    await ask(systems)
    # Midnight UTC is 03:00 in Bucharest, the middle of the same business day.
    clock["now"] = datetime(2026, 10, 23, 0, 1, tzinfo=UTC)
    after_utc_midnight = await assistant_state(systems)

    assert before_midnight["used_today"] == 60
    assert after_midnight["used_today"] == 0
    assert after_utc_midnight["used_today"] == 60


async def test_budget_spent_returns_429(systems):
    model = systems.use_model("unused")
    systems.ctx.db.add_usage(ranges.today(systems.ctx.settings.zone), 200000)

    response = await ask(systems)

    assert response.status_code == 429
    assert "budget" in response.json()["detail"]
    assert model.requests == []


async def test_effort_limits_rounds(systems):
    await systems.sign_in("admin")
    saved = await systems.put("/api/assistant/settings", effort="low", max_tokens_per_question=500)
    assert (saved.json()["effort"], saved.json()["max_tokens_per_question"]) == ("low", 500)
    model = systems.use_model("unused", [("list_review_items", {})] * 10)

    response = await ask(systems)

    assert response.json()["answer"] == (
        "I could not find the answer within the allowed number of lookups."
    )
    assert [request["max_tokens"] for request in model.requests] == [500, 500]


async def test_assistant_settings_need_admin_and_bounds(systems):
    forbidden = await systems.put("/api/assistant/settings", effort="high")
    await systems.sign_in("admin")
    invalid = await systems.put("/api/assistant/settings", daily_token_budget=999)

    assert forbidden.status_code == 403
    assert invalid.status_code == 422
    assert invalid.json()["detail"][0]["loc"] == ["body", "daily_token_budget"]
    assert (await assistant_state(systems))["effort"] == "medium"


async def test_viewer_cannot_ask(systems):
    model = systems.use_model("unused")
    await systems.sign_in("viewer")

    response = await ask(systems)

    assert response.status_code == 403
    assert model.requests == []


async def test_timeout_returns_503_and_keeps_usage(systems):
    model = systems.use_model("unused", [("list_review_items", {})])
    first_round = model.create

    async def time_out_after_first_round(**request: object) -> object:
        if model.requests:
            raise APITimeoutError(httpx.Request("POST", "http://ollama/v1/chat/completions"))
        return await first_round(**request)

    model.chat.completions.create = time_out_after_first_round

    response = await ask(systems)

    assert response.status_code == 503
    assert "took longer" in response.json()["detail"]
    state = await assistant_state(systems)
    assert (state["used_today"], state["questions_today"]) == (60, 1)


async def test_first_start_downloads_the_model(systems, caplog):
    systems.ollama.models.clear()

    await llm.ensure_model(systems.ctx)

    assert (await assistant_state(systems))["model"]["status"] == "ready"
    assert systems.ollama.models == ["qwen2.5:3b"]
    assert "Downloading local model qwen2.5:3b (about 2 GB, one time)" in caplog.messages
    assert "Local model qwen2.5:3b is ready" in caplog.messages


async def test_unexpected_error_does_not_stop_the_model_check(systems, monkeypatch, caplog):
    statuses_while_waiting: list[str] = []

    async def sleep(seconds: float) -> None:
        statuses_while_waiting.append(systems.ctx.model_status)

    monkeypatch.setattr(llm, "asyncio", SimpleNamespace(sleep=sleep))
    systems.ollama.models.clear()
    systems.ollama.total = "four"

    await llm.ensure_model(systems.ctx)

    assert statuses_while_waiting == ["offline"]
    assert systems.ctx.model_status == "ready"
    assert "local model check failed" in caplog.messages
