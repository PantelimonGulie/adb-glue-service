import json
from types import SimpleNamespace

ANSWER = (
    "ACTION: retry\nREASON: The order failed only because the warehouse answered 503 five"
    " times; stock for IPH16-256 is available, so a retry should allocate it."
)


class StubModel:
    # Stands in for AsyncOpenAI: first asks for the order, then answers from the tool result.
    def __init__(self, order_id: str):
        self.order_id = order_id
        self.requests: list[list[dict]] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    async def create(self, model: str, messages: list[dict], tools: list[dict]) -> SimpleNamespace:
        self.requests.append(messages)
        if len(self.requests) == 1:
            function = SimpleNamespace(
                name="get_order", arguments=json.dumps({"order_id": self.order_id})
            )
            call = SimpleNamespace(id="call-1", function=function)
            message = SimpleNamespace(content=None, tool_calls=[call])
        else:
            message = SimpleNamespace(content=ANSWER, tool_calls=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


async def test_triage_suggests_without_acting(systems, sleeps):
    await systems.chaos("warehouse", down=True)
    order_id = await systems.buy_on_shop("IPH16-256")
    await systems.run_worker()
    await systems.chaos("warehouse", down=False)
    [item] = systems.open_reviews()
    systems.ctx.assistant = StubModel(order_id)

    response = await systems.act(f"/triage/{item['id']}")

    assert response.status_code == 200
    assert "Assistant suggests" in response.text and ANSWER.split("\n")[1][8:] in response.text
    item = systems.ctx.db.get_review(item["id"])
    assert (item["status"], item["suggested_action"]) == ("open", "retry")
    assert systems.ctx.db.get_order(order_id)["status"] == "failed"
    assert systems.warehouse.state.stock["IPH16-256"]["reserved"] == 0
    tool_result = json.loads(systems.ctx.assistant.requests[1][-1]["content"])
    assert tool_result["order"]["order_id"] == order_id
    assert systems.ctx.db.counters()["triage_suggested"] == 1


async def test_triage_button_is_disabled_offline(systems, sleeps):
    await systems.chaos("warehouse", down=True)
    await systems.buy_on_shop("IPH16-256")
    await systems.run_worker()
    [item] = systems.open_reviews()

    page = await systems.http.get("http://glue/review")
    refused = await systems.act(f"/triage/{item['id']}")

    assert 'hx-post="/triage/1" disabled' in page.text
    assert refused.status_code == 409
