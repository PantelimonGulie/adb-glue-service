import httpx

from glue import review


async def shipped_while_emag_down(systems) -> tuple[str, dict]:
    order_id = await systems.buy_on_emag("APP-3")
    await systems.run_worker()
    await systems.chaos("emag", down=True)
    await systems.http.post(f"http://warehouse/orders/{order_id}/ship")
    await systems.run_worker()
    [item] = systems.open_reviews()
    return order_id, item


async def test_a_ship_notice_the_channel_missed_is_retried_from_review(systems, sleeps):
    order_id, item = await shipped_while_emag_down(systems)
    order = systems.ctx.db.get_order(order_id)

    assert (order["status"], item["payload"]["operation"]) == ("shipped", "ship")
    assert review.allowed_actions(item, order) == {"retry", "dismiss"}

    await systems.chaos("emag", down=False)
    response = await systems.decide(item["id"], "retry")

    assert response.status_code == 200
    assert systems.emag_order(order_id)["status"] == 4
    assert systems.open_reviews() == []


async def test_a_ship_notice_behind_a_failed_cancel_still_gets_its_own_retry(systems, sleeps):
    order_id = await systems.buy_on_emag("APP-3")
    await systems.run_worker()
    await systems.chaos("warehouse", down=True)
    await systems.http.post(f"http://emag/orders/{order_id.removeprefix('emag-')}/cancel")
    await systems.run_worker()
    await systems.chaos("warehouse", down=False)
    await systems.chaos("emag", down=True)
    await systems.http.post(f"http://warehouse/orders/{order_id}/ship")
    await systems.run_worker()

    cancel, ship = systems.open_reviews()
    assert (cancel["payload"]["operation"], ship["payload"]["operation"]) == ("cancel", "ship")

    await systems.chaos("emag", down=False)
    response = await systems.decide(ship["id"], "retry")

    assert response.status_code == 200
    assert systems.emag_order(order_id)["status"] == 4
    assert [i["id"] for i in systems.open_reviews()] == [cancel["id"]]


def resolved(systems) -> list[tuple[str, str, str]]:
    decided = systems.ctx.db.list_review("decided")
    return [(item["order_id"], item["action"], item["decided_by"]) for item in decided]


async def test_a_customer_cancel_resolves_the_oversell_item(systems, sleeps):
    await systems.chaos("emag", freeze_stock=True)
    await systems.buy_on_shop("MBA-M4")
    await systems.run_worker()
    emag_order = await systems.buy_on_emag("MBA-M4")
    await systems.run_worker()
    [item] = systems.open_reviews()

    emag_id = emag_order.removeprefix("emag-")
    await systems.http.post(f"http://emag/orders/{emag_id}/cancel")
    await systems.run_worker()

    assert systems.ctx.db.get_order(emag_order)["status"] == "cancelled"
    assert systems.open_reviews() == []
    assert resolved(systems) == [(emag_order, "resolved", "glue")]
    assert systems.ctx.db.counters()["review_resolved"] == 1


async def test_a_customer_cancel_before_a_failed_import_heals_resolves_its_item(systems, sleeps):
    await systems.chaos("emag", down=True)
    order_id = await systems.buy_on_emag("APP-3")
    await systems.run_worker()
    await systems.chaos("emag", down=False)

    await systems.http.post(f"http://emag/orders/{order_id.removeprefix('emag-')}/cancel")
    await systems.run_worker()

    assert systems.ctx.db.get_order(order_id)["status"] == "cancelled"
    assert systems.open_reviews() == []
    assert resolved(systems) == [(order_id, "resolved", "glue")]


async def test_an_order_that_ships_resolves_its_recount_item(systems, sleeps):
    order_id = await systems.buy_on_shop("IPH16-128")
    await systems.run_worker()
    await systems.recount("IPH16-128", 0)
    await systems.run_worker()
    [item] = systems.open_reviews()

    await systems.http.post(f"http://warehouse/orders/{order_id}/ship")
    await systems.run_worker()

    assert (item["kind"], systems.ctx.db.get_order(order_id)["status"]) == (
        "unfulfillable",
        "shipped",
    )
    assert systems.open_reviews() == []
    assert resolved(systems) == [(order_id, "resolved", "glue")]


async def test_a_failed_customer_cancel_stays_open_when_the_order_ships(systems, sleeps):
    order_id = await systems.buy_on_emag("APP-3")
    await systems.run_worker()
    await systems.chaos("emag", down=True)
    await systems.http.post(f"http://emag/orders/{order_id.removeprefix('emag-')}/cancel")
    await systems.run_worker()
    [item] = systems.open_reviews()
    await systems.chaos("emag", down=False)

    await systems.http.post(f"http://warehouse/orders/{order_id}/ship")
    await systems.run_worker()

    # The customer cancelled but got the parcel anyway: a person has to sort that out.
    assert systems.ctx.db.get_order(order_id)["status"] == "shipped"
    assert [i["id"] for i in systems.open_reviews()] == [item["id"]]
    assert item["payload"]["operation"] == "cancel"


async def test_an_item_that_does_not_say_what_failed_is_left_for_a_person(systems, sleeps):
    order_id = await systems.buy_on_shop("WATCH-S10")
    await systems.run_worker()
    # Shaped like an item saved before items recorded their operation.
    item_id = systems.ctx.db.open_review("order_failed", order_id, {}, "HTTP 503 after 5 attempts")

    await systems.http.post(f"http://shop/orders/{order_id}/cancel")
    await systems.run_worker()

    assert systems.ctx.db.get_order(order_id)["status"] == "cancelled"
    assert [i["id"] for i in systems.open_reviews()] == [item_id]


async def test_a_redelivered_event_that_fails_again_keeps_its_item_open(systems, sleeps):
    await systems.chaos("emag", down=True)
    order_id = await systems.buy_on_emag("APP-3")
    await systems.run_worker()
    [item] = systems.open_reviews()

    await systems.chaos("warehouse", down=True)
    await systems.chaos("emag", down=False, renotify_now=True)
    await systems.run_worker()

    assert systems.ctx.db.get_order(order_id)["status"] == "failed"
    assert [i["id"] for i in systems.open_reviews()] == [item["id"]]


async def test_a_recount_found_while_an_event_heals_leaves_only_the_recount(systems, sleeps):
    await systems.chaos("emag", down=True)
    order_id = await systems.buy_on_emag("MBA-M4")
    await systems.run_worker()
    create_order = systems.ctx.warehouse.create_order

    async def then_recounted(order):
        response = await create_order(order)
        systems.warehouse.state.stock["MBA-M4"]["on_hand"] = 0
        return response

    systems.ctx.warehouse.create_order = then_recounted
    await systems.chaos("emag", down=False, renotify_now=True)
    await systems.run_worker()

    [recount] = systems.open_reviews()
    assert (recount["kind"], recount["order_id"]) == ("unfulfillable", order_id)
    assert resolved(systems) == [(order_id, "resolved", "glue")]


async def test_a_failed_emag_import_healed_on_renotify_resolves_its_item(systems, sleeps):
    await systems.chaos("emag", down=True)
    order_id = await systems.buy_on_emag("APP-3")
    await systems.run_worker()
    [item] = systems.open_reviews()
    assert systems.ctx.db.get_order(order_id) is None

    await systems.chaos("emag", down=False, renotify_now=True)
    await systems.run_worker()

    assert systems.ctx.db.get_order(order_id)["status"] == "allocated"
    assert systems.open_reviews() == []
    assert resolved(systems) == [(order_id, "resolved", "glue")]


async def test_an_acknowledge_that_fails_after_the_reservation_heals_on_renotify(systems, sleeps):
    acknowledge = systems.ctx.emag.acknowledge
    calls = []

    async def busy_for_one_round(emag_id: int) -> httpx.Response:
        calls.append(emag_id)
        if len(calls) <= systems.ctx.tuning.retry_attempts:
            return httpx.Response(503, request=httpx.Request("POST", "http://emag/ack"))
        return await acknowledge(emag_id)

    systems.ctx.emag.acknowledge = busy_for_one_round
    order_id = await systems.buy_on_emag("APP-3")
    await systems.run_worker()

    assert systems.ctx.db.get_order(order_id)["status"] == "allocated"
    assert systems.emag_order(order_id)["status"] == 1
    [item] = systems.open_reviews()

    await systems.chaos("emag", renotify_now=True)
    await systems.run_worker()

    assert systems.emag_order(order_id)["status"] == 2
    assert systems.warehouse.state.stock["APP-3"]["reserved"] == 1
    assert systems.open_reviews() == []
    assert resolved(systems) == [(order_id, "resolved", "glue")]
