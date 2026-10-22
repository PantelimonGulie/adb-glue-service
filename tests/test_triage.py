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
    model = systems.use_model(ANSWER)

    await triage.suggest(systems.ctx, item["id"])

    item = systems.ctx.db.get_review(item["id"])
    assert (item["status"], item["suggested_action"]) == ("open", "retry")
    assert item["suggested_reason"] == ANSWER.split("REASON: ")[1]
    assert systems.ctx.db.get_order(order_id)["status"] == "failed"
    assert systems.warehouse.state.stock["IPH16-256"]["reserved"] == 0
    assert "tools" not in model.requests[0]
    assert systems.ctx.db.counters()["triage_suggested"] == 1


async def test_triage_uses_local_model(systems, sleeps):
    order_id, item = await failed_order_review(systems)
    model = systems.use_model(ANSWER)

    response = await systems.act(f"/api/review/{item['id']}/triage")

    assert response.status_code == 200
    body = response.json()
    assert (body["id"], body["status"], body["order"]["order_id"]) == (item["id"], "open", order_id)
    assert body["suggestion"] == {"action": "retry", "reason": ANSWER.split("REASON: ")[1]}
    assert model.requests[0]["model"] == "qwen2.5:3b"
    assistant = (await systems.http.get("http://glue/api/assistant")).json()
    assert (assistant["used_today"], assistant["questions_today"]) == (60, 1)


async def test_triage_offline_returns_503(systems, sleeps):
    _, item = await failed_order_review(systems)
    model = systems.use_model(ANSWER)
    systems.ollama.up = False

    response = await systems.act(f"/api/review/{item['id']}/triage")

    assert response.status_code == 503
    assert "not answering" in response.json()["detail"]
    assert systems.ctx.db.get_review(item["id"])["suggested_reason"] is None
    assert model.requests == []


async def oversell_review(systems) -> dict:
    await systems.chaos("emag", freeze_stock=True)
    await systems.buy_on_shop("MBA-M4")
    await systems.run_worker()
    await systems.buy_on_emag("MBA-M4")
    await systems.run_worker()
    [item] = systems.open_reviews()
    return item


async def test_triage_hands_the_model_the_facts(systems, sleeps):
    item = await oversell_review(systems)
    model = systems.use_model("ACTION: cancel\nREASON: No MacBook Air M4 is free.")

    await triage.suggest(systems.ctx, item["id"])

    prompt = model.requests[0]["messages"][-1]["content"]
    assert "It asks for 1 × MacBook Air M4; 0 free in the warehouse." in prompt
    assert f"Order {item['order_id']} came from eMAG" in prompt
    assert "The Bucharest warehouse is answering right now." in prompt
    assert "- cancel: cancels the order on the customer's channel (eMAG)" in prompt
    assert "the free stock is less than the quantity asked, so suggest cancel" in prompt
    assert systems.ctx.db.get_review(item["id"])["suggested_action"] == "cancel"


async def test_triage_rule_suggests_retry_once_stock_covers_the_order(systems, sleeps):
    item = await oversell_review(systems)
    await systems.recount("MBA-M4", 5)
    await systems.run_worker()
    model = systems.use_model("ACTION: retry\nREASON: Four MacBook Air M4 are free again.")

    await triage.suggest(systems.ctx, item["id"])

    prompt = model.requests[0]["messages"][-1]["content"]
    assert "It asks for 1 × MacBook Air M4; 4 free in the warehouse." in prompt
    assert "the free stock covers every quantity, so suggest retry" in prompt


async def test_triage_drops_a_suggestion_about_another_order(systems, sleeps):
    item = await oversell_review(systems)
    systems.use_model("ACTION: dismiss\nREASON: Order shop-1041 already has the unit.")

    await triage.suggest(systems.ctx, item["id"])

    saved = systems.ctx.db.get_review(item["id"])
    assert saved["suggested_action"] is None
    assert saved["suggested_reason"].endswith("is about shop-1041, not this order.")
