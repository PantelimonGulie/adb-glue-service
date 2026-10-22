import pytest

from glue import review


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


async def test_recount_below_reserved_caps_channels_and_queues_each_order(systems):
    shop_order = await systems.buy_on_shop("IPH16-128")
    emag_order = await systems.buy_on_emag("IPH16-128")
    await systems.run_worker()
    await systems.recount("IPH16-128", 1)
    await systems.run_worker()
    # A later periodic run sees the same shortfall and must not queue the orders again.
    await systems.reconcile()

    assert systems.shop.state.stock["IPH16-128"] == 0
    assert systems.emag.state.stock["IPH16-128"] == 0
    items = systems.open_reviews()
    assert sorted(item["order_id"] for item in items) == sorted([shop_order, emag_order])
    assert {item["kind"] for item in items} == {"unfulfillable"}

    # Both orders still hold their reservation, so there is no allocation to retry.
    with pytest.raises(review.Conflict):
        await systems.decide(items[0]["id"], "retry")
