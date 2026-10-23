import json
from types import SimpleNamespace

import httpx
from openai import APITimeoutError

from common.catalog import PRODUCTS
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
    assert model.requests[0]["max_tokens"] == 2000
    state = await assistant_state(systems)
    assert (state["used_today"], state["questions_today"]) == (120, 1)


async def test_the_prompt_carries_live_facts_and_the_words_to_use(systems, sleeps):
    await systems.chaos("warehouse", down=True)
    await systems.buy_on_shop("MBA-M4")
    await systems.run_worker()
    model = systems.use_model("No, the Bucharest warehouse is not answering.")

    await systems.act("/api/assistant/ask", question="Is the warehouse working?")

    system = model.requests[0]["messages"][0]["content"]
    assert "the shop (Electronic Market): working" in system
    assert "the Bucharest warehouse: not answering" in system
    assert "Waiting for a person: 1 warehouse outage." in system
    assert "Last hour: 1 order in, 0 reserved, 1 failed" in system
    assert "'the shop' is Electronic Market" in system
    assert "never say 'SKU'" in system
    assert not any(code in system for code in PRODUCTS)


async def test_tools_answer_in_product_names_and_plain_words(systems, sleeps):
    order_id = await systems.buy_on_shop("MBA-M4")
    await systems.run_worker()
    await systems.chaos("emag", reject_sku="MBA-M4")
    await systems.reconcile()
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
    assert stock[0]["state"] == "eMAG refused the last stock update"
    assert order["order"]["products"] == "1 × MacBook Air M4"
    assert summary["orders in"] == 1
    assert review == []
    for result in results:
        assert "MBA-M4" not in result
        assert "sku" not in result.lower()
        assert "+00:00" not in result


async def test_budget_spent_returns_429(systems):
    model = systems.use_model("unused")
    systems.ctx.db.add_usage(200000)

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
