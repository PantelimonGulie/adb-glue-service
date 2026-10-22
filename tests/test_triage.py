import json

from glue import triage

ANSWER = (
    "ACTION: retry\nREASON: The order failed only because the warehouse answered 503 five"
    " times; stock for IPH16-256 is available, so a retry should allocate it."
)


async def failed_order_review(systems) -> tuple[str, dict]:
    await systems.chaos("warehouse", down=True)
    order_id = await systems.buy_on_shop("IPH16-256")
    await systems.run_worker()
    await systems.chaos("warehouse", down=False)
    [item] = systems.open_reviews()
    return order_id, item


async def test_triage_suggests_without_acting(systems, sleeps):
    order_id, item = await failed_order_review(systems)
    model = systems.use_model(ANSWER, [("get_order", {"order_id": order_id})])

    await triage.suggest(systems.ctx, item["id"])

    item = systems.ctx.db.get_review(item["id"])
    assert (item["status"], item["suggested_action"]) == ("open", "retry")
    assert item["suggested_reason"] == ANSWER.split("REASON: ")[1]
    assert systems.ctx.db.get_order(order_id)["status"] == "failed"
    assert systems.warehouse.state.stock["IPH16-256"]["reserved"] == 0
    tool_result = json.loads(model.requests[1]["messages"][-1]["content"])
    assert tool_result["order"]["order_id"] == order_id
    assert systems.ctx.db.counters()["triage_suggested"] == 1


async def test_triage_uses_local_model(systems, sleeps):
    order_id, item = await failed_order_review(systems)
    model = systems.use_model(ANSWER, [("get_order", {"order_id": order_id})])

    response = await systems.act(f"/api/review/{item['id']}/triage")

    assert response.status_code == 200
    body = response.json()
    assert (body["id"], body["status"], body["order"]["order_id"]) == (item["id"], "open", order_id)
    assert body["suggestion"] == {"action": "retry", "reason": ANSWER.split("REASON: ")[1]}
    assert model.requests[0]["model"] == "qwen2.5:3b"
    assistant = (await systems.http.get("http://glue/api/assistant")).json()
    assert (assistant["used_today"], assistant["questions_today"]) == (120, 1)


async def test_triage_offline_returns_503(systems, sleeps):
    _, item = await failed_order_review(systems)
    model = systems.use_model(ANSWER)
    systems.ollama.up = False

    response = await systems.act(f"/api/review/{item['id']}/triage")

    assert response.status_code == 503
    assert "not answering" in response.json()["detail"]
    assert systems.ctx.db.get_review(item["id"])["suggested_reason"] is None
    assert model.requests == []
