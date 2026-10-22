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
