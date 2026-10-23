def dirty_skus(systems, channel: str) -> set[str]:
    return {row["sku"] for row in systems.ctx.db.channel_stock(channel) if row["dirty"]}


async def test_rejected_offer_is_flagged_and_fixed_on_next_run(systems):
    await systems.chaos("emag", reject_sku="MBA-M4")
    await systems.recount("IPH16-128", 20)
    await systems.recount("MBA-M4", 3)
    await systems.reconcile()

    assert systems.emag.state.stock["IPH16-128"] == 20
    assert systems.emag.state.stock["MBA-M4"] == 1
    assert dirty_skus(systems, "emag") == {"MBA-M4"}

    await systems.chaos("emag", reject_sku=None)
    await systems.reconcile()

    assert systems.emag.state.stock["MBA-M4"] == 3
    assert dirty_skus(systems, "emag") == set()


async def test_recount_below_reserved_caps_channels_and_queues_the_newest_order(systems):
    await systems.buy_on_shop("IPH16-128")
    await systems.run_worker()
    emag_order = await systems.buy_on_emag("IPH16-128")
    await systems.run_worker()
    await systems.recount("IPH16-128", 1)
    await systems.run_worker()
    # A later periodic run sees the same shortfall and must not queue the orders again.
    await systems.reconcile()

    assert systems.shop.state.stock["IPH16-128"] == 0
    assert systems.emag.state.stock["IPH16-128"] == 0
    [item] = systems.open_reviews()
    assert (item["kind"], item["order_id"]) == ("unfulfillable", emag_order)
    assert "recount" in item["reason"]

    # The order still holds its reservation, so there is no allocation to retry.
    response = await systems.decide(item["id"], "retry")
    assert response.status_code == 409


def flagged(systems) -> list[str]:
    return [item["order_id"] for item in systems.open_reviews()]


async def test_a_shortfall_of_two_flags_the_two_newest_orders_and_a_restock_closes_them(systems):
    orders = []
    for _ in range(20):
        orders.append(await systems.buy_on_shop("IPH16-128"))
        await systems.run_worker()

    await systems.recount("IPH16-128", 18)
    await systems.run_worker()
    await systems.reconcile()

    assert sorted(flagged(systems)) == sorted(orders[-2:])
    assert systems.ctx.db.counters()["unfulfillable"] == 2

    await systems.recount("IPH16-128", 19)
    await systems.run_worker()

    assert flagged(systems) == [orders[-1]]

    await systems.recount("IPH16-128", 22)
    await systems.run_worker()

    assert flagged(systems) == []
    closed = systems.ctx.db.list_review("decided")
    assert {(i["order_id"], i["action"], i["decided_by"]) for i in closed} == {
        (orders[-2], "resolved", "glue"),
        (orders[-1], "resolved", "glue"),
    }
    assert systems.shop.state.stock["IPH16-128"] == 2


async def test_a_two_product_order_keeps_its_item_while_only_one_product_is_short(systems):
    lines = [{"sku": "APP-3", "qty": 1}, {"sku": "IPAD-A16", "qty": 1}]
    order = {"id": "shop-77", "channel": "shop", "channel_order_id": "77", "lines": lines}
    await systems.send_event("shop", "order.placed", {**order, "customer": "Guest"})
    await systems.run_worker()
    await systems.recount("APP-3", 0)
    await systems.run_worker()
    # Every periodic run checks IPAD-A16 too, which still covers the order.
    await systems.reconcile()
    await systems.reconcile()

    assert flagged(systems) == ["shop-77"]
    assert systems.ctx.db.counters()["unfulfillable"] == 1

    await systems.recount("APP-3", 1)
    await systems.run_worker()

    assert flagged(systems) == []
