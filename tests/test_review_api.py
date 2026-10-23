import time

import httpx
import pytest

from glue import review


async def oversell_then_outage(systems) -> list[str]:
    await systems.chaos("emag", freeze_stock=True)
    await systems.buy_on_shop("MBA-M4")
    await systems.run_worker()
    await systems.buy_on_emag("MBA-M4")
    await systems.run_worker()
    await systems.chaos("warehouse", down=True)
    failed = [await systems.buy_on_shop(sku) for sku in ("IPH16-128", "APP-3")]
    await systems.run_worker()
    return failed


async def open_items(systems) -> dict:
    response = await systems.http.get("http://glue/api/review")
    assert response.status_code == 200
    return response.json()


async def test_review_groups_by_cause(systems, sleeps):
    await oversell_then_outage(systems)

    review = await open_items(systems)
    outage = await systems.http.get("http://glue/api/review", params={"cause": "outage"})

    assert {g["cause"]: g["count"] for g in review["groups"]} == {"outage": 2, "soldout": 1}
    assert [item["cause"] for item in outage.json()["items"]] == ["outage", "outage"]
    soldout = next(item for item in review["items"] if item["cause"] == "soldout")
    assert soldout["order"]["product"] == "MacBook Air M4"
    assert soldout["allowed"] == ["cancel", "dismiss", "retry"]
    assert soldout["suggestion"] is None
    ids = [item["id"] for item in review["items"]]
    assert ids == sorted(ids, reverse=True)


async def test_a_sold_out_item_names_the_order_that_got_the_last_unit(systems, sleeps):
    await systems.chaos("emag", freeze_stock=True)
    shop_order = await systems.buy_on_shop("MBA-M4")
    await systems.run_worker()
    await systems.buy_on_emag("MBA-M4")
    await systems.run_worker()
    await systems.chaos("warehouse", down=True)
    await systems.buy_on_shop("APP-3")
    await systems.run_worker()

    items = (await open_items(systems))["items"]

    [reserved] = [
        r for r in systems.ctx.db.audit_for(shop_order) if r["action"] == "order_allocated"
    ]
    winners = {item["cause"]: item["winner"] for item in items}
    assert winners == {
        "soldout": {"order_id": shop_order, "channel": "shop", "reserved_at": reserved["ts"]},
        "outage": None,
    }


async def test_retry_all_outage(systems, sleeps):
    failed = await oversell_then_outage(systems)
    await systems.chaos("warehouse", down=False)

    response = await systems.act("/api/review/retry-all", cause="outage")

    assert response.json() == {"retried": 2}
    assert [systems.ctx.db.get_order(order_id)["status"] for order_id in failed] == [
        "allocated",
        "allocated",
    ]
    assert [g["cause"] for g in (await open_items(systems))["groups"]] == ["soldout"]
    decided = systems.ctx.db.list_review("decided")
    assert {(item["action"], item["decided_by"]) for item in decided} == {("retry", "operator")}


async def test_retry_all_refused_while_down(systems, sleeps):
    await oversell_then_outage(systems)

    response = await systems.act("/api/review/retry-all", cause="outage")

    assert response.status_code == 409
    assert response.json() == {"detail": "The warehouse is still not answering"}
    assert len(systems.open_reviews()) == 3


async def test_retry_all_names_the_state_the_warehouse_is_in(systems, sleeps):
    await oversell_then_outage(systems)
    await systems.chaos("warehouse", down=False)
    systems.ctx.trouble["warehouse"] = ("rate_limited", time.monotonic())

    response = await systems.act("/api/review/retry-all", cause="outage")

    assert response.status_code == 409
    assert response.json() == {"detail": "The warehouse is still limiting requests"}


async def test_decide_returns_item(systems, sleeps):
    await oversell_then_outage(systems)
    soldout = next(i for i in (await open_items(systems))["items"] if i["cause"] == "soldout")

    response = await systems.decide(soldout["id"], "cancel")
    again = await systems.decide(soldout["id"], "cancel")

    item = response.json()
    assert (item["status"], item["action"], item["decided_by"]) == ("decided", "cancel", "operator")
    assert item["order"]["status"] == "cancelled"
    assert item["allowed"] == []
    assert again.status_code == 409


async def test_a_failed_decision_puts_the_order_back_in_review(systems, sleeps):
    await systems.chaos("emag", freeze_stock=True)
    await systems.buy_on_shop("MBA-M4")
    await systems.run_worker()
    emag_order = await systems.buy_on_emag("MBA-M4")
    await systems.run_worker()
    [item] = systems.open_reviews()
    await systems.chaos("emag", down=True)

    response = await systems.decide(item["id"], "cancel")

    assert response.status_code == 502
    assert systems.ctx.db.get_review(item["id"])["status"] == "decided"
    [again] = systems.open_reviews()
    assert (again["order_id"], again["status"]) == (emag_order, "open")
    assert again["reason"] == "cancel failed: eMAG is not answering (tried 5 times)"
    assert response.json()["detail"] == again["reason"]


async def test_a_decision_on_an_item_claimed_since_it_was_read_is_refused(
    systems, sleeps, monkeypatch
):
    await systems.chaos("warehouse", down=True)
    order_id = await systems.buy_on_shop("IPH16-256")
    await systems.run_worker()
    [item] = systems.open_reviews()
    await systems.chaos("warehouse", down=False)
    # This decision read the item while it was open; another one claimed it since.
    monkeypatch.setattr(systems.ctx.db, "get_review", lambda item_id: item)
    systems.ctx.db.start_review(item["id"], "dismiss", "admin")

    with pytest.raises(review.Conflict):
        await review.decide(systems.ctx, item["id"], "retry")
    assert systems.ctx.db.get_order(order_id)["status"] == "failed"


async def test_viewer_cannot_decide(systems, sleeps):
    await oversell_then_outage(systems)
    [item, *_] = systems.open_reviews()
    await systems.sign_in("viewer")

    response = await systems.act(f"/api/review/{item['id']}/dismiss")

    assert response.status_code == 403
    assert response.json() == {"detail": "a viewer may not do this"}
    assert len(systems.open_reviews()) == 3


@pytest.mark.parametrize(
    "reason, cause",
    [
        ("the Bucharest warehouse is not answering (tried 5 times)", "outage"),
        ("the Bucharest warehouse took too long to answer (tried 5 times)", "outage"),
        ("the Bucharest warehouse could not be reached (tried 5 times)", "outage"),
        ("HTTP 503 after 5 attempts", "outage"),
        ("ReadTimeout: timed out after 5 attempts", "outage"),
        ("ConnectError: All connection attempts failed after 3 attempts", "outage"),
        ("ReadError: connection reset after 5 attempts", "outage"),
        ("RemoteProtocolError: Server disconnected after 5 attempts", "outage"),
        ("cancellation not delivered: the Bucharest warehouse is not answering", "outage"),
        ("warehouse cancel not delivered: HTTP 503 after 5 attempts", "outage"),
        ("KeyError: 'sku'", "other"),
        ("warehouse rejected: HTTP 400 bad request", "other"),
        ("eMAG is not answering (tried 5 times)", "other"),
        ("cancel failed: the shop could not be reached (tried 5 times)", "other"),
        ("channel not told it shipped: eMAG took too long to answer (tried 5 times)", "other"),
        ("channel not told it shipped: HTTP 503 after 5 attempts", "other"),
    ],
)
def test_failed_order_cause(reason, cause):
    assert review.cause_of({"kind": "order_failed", "reason": reason}) == cause


async def test_a_warehouse_that_timed_out_is_an_outage(systems, sleeps):
    async def time_out(*args: object) -> httpx.Response:
        raise httpx.ReadTimeout("timed out")

    systems.ctx.warehouse.create_order = time_out
    await systems.buy_on_shop("APP-3")
    await systems.run_worker()

    [item] = systems.open_reviews()
    assert item["reason"].startswith("the Bucharest warehouse took too long to answer")
    assert review.cause_of(item) == "outage"


async def test_an_emag_read_that_ran_out_of_tries_is_not_a_warehouse_outage(systems, sleeps):
    await systems.chaos("emag", down=True)
    await systems.buy_on_emag("APP-3")
    await systems.run_worker()

    [item] = systems.open_reviews()
    assert item["reason"].startswith("eMAG is not answering")
    assert review.cause_of(item) == "other"


async def test_a_shop_cancel_that_ran_out_of_tries_is_not_a_warehouse_outage(systems, sleeps):
    await systems.chaos("warehouse", down=True)
    order_id = await systems.buy_on_shop("APP-3")
    await systems.run_worker()
    await systems.chaos("warehouse", down=False)
    [item] = systems.open_reviews()

    async def refuse(*args: object) -> httpx.Response:
        return httpx.Response(503, request=httpx.Request("POST", "http://shop"))

    systems.ctx.shop.cancel = refuse
    response = await systems.decide(item["id"], "cancel")

    assert response.status_code == 502
    [again] = systems.open_reviews()
    assert again["reason"].startswith("cancel failed: the shop is not answering")
    assert review.cause_of(again) == "other"
    # Retry all re-sends placements to the warehouse; it must not re-place an order whose
    # cancellation the shop never took.
    retried = await systems.act("/api/review/retry-all", cause="outage")
    assert retried.json() == {"retried": 0}
    assert systems.ctx.db.get_order(order_id)["status"] == "failed"
