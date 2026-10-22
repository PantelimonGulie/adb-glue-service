import time

import pytest

import emag.main
import shop.main
from common.models import Order


async def test_duplicate_shop_events_create_one_order(systems):
    order_id = await systems.buy_on_shop("IPH16-128")
    await systems.chaos("shop", duplicate_last=True)
    # Adobe Commerce may also redeliver the same order under a new event id.
    await systems.send_event("shop", "order.placed", systems.shop.state.orders[order_id])
    await systems.run_worker()

    assert [order["order_id"] for order in systems.ctx.db.list_orders()[0]] == [order_id]
    assert systems.warehouse.state.stock["IPH16-128"]["reserved"] == 1
    counters = systems.ctx.db.counters()
    assert counters["duplicate_dropped"] == 1
    assert counters["order_known"] == 1


async def test_order_left_received_by_a_crash_is_sent_again(systems):
    order_id = await systems.buy_on_shop("IPH16-256")
    order = Order(**systems.shop.state.orders[order_id])
    # The glue saved the order, then stopped before the warehouse answer was recorded.
    systems.ctx.db.insert_order_if_new(order)
    await systems.run_worker()

    assert systems.ctx.db.get_order(order_id)["status"] == "allocated"
    assert systems.warehouse.state.stock["IPH16-256"]["reserved"] == 1
    assert systems.ctx.db.counters()["allocation_resumed"] == 1


async def test_emag_renotify_does_not_allocate_twice(systems):
    order_id = await systems.buy_on_emag("APP-3")
    await systems.chaos("emag", renotify_now=True)
    await systems.run_worker()
    # Acknowledged now, so eMAG has nothing left to re-send.
    await systems.chaos("emag", renotify_now=True)

    assert systems.ctx.db.get_order(order_id)["status"] == "allocated"
    assert systems.emag_order(order_id)["status"] == 2
    assert systems.warehouse.state.stock["APP-3"]["reserved"] == 1
    assert systems.ctx.db.counters()["duplicate_dropped"] == 1


async def test_warehouse_fails_twice_then_allocates(systems):
    await systems.chaos("warehouse", fail_next=2)
    order_id = await systems.buy_on_shop("IPAD-A16")
    await systems.run_worker()

    order = systems.ctx.db.get_order(order_id)
    assert order["status"] == "allocated"
    assert order["attempts"] == 3
    assert systems.ctx.db.counters()["retry_scheduled"] == 2


async def test_reading_stock_leaves_the_failures_for_order_placements(systems):
    await systems.chaos("warehouse", fail_next=2)
    stock = await systems.http.get("http://warehouse/stock")
    orders = await systems.http.get("http://warehouse/orders")

    assert (stock.status_code, orders.status_code) == (200, 200)
    assert systems.warehouse.state.chaos.fail_next == 2


@pytest.mark.parametrize(
    ("mock", "counter"), [(shop.main, "order_numbers"), (emag.main, "order_ids")]
)
def test_mock_order_numbers_never_repeat_after_a_restart(monkeypatch, mock, counter):
    monkeypatch.setattr(time, "time", lambda: 1_790_000_000.0)
    numbers = getattr(mock.create_app().state, counter)
    issued = [next(numbers) for _ in range(5)]
    # Glue keeps its orders, so a mock restarted a second later must not reuse a number.
    monkeypatch.setattr(time, "time", lambda: 1_790_000_001.0)
    restarted = next(getattr(mock.create_app().state, counter))

    assert restarted > issued[-1]


async def test_warehouse_down_queues_order_until_operator_retries(systems, sleeps):
    await systems.chaos("warehouse", down=True)
    order_id = await systems.buy_on_shop("IPH16-256")
    await systems.run_worker()

    assert systems.ctx.db.get_order(order_id)["status"] == "failed"
    assert sleeps == [2.0] * 4
    [item] = systems.open_reviews()
    assert (item["kind"], item["order_id"]) == ("order_failed", order_id)

    await systems.chaos("warehouse", down=False)
    await systems.decide(item["id"], "retry")

    assert systems.ctx.db.get_order(order_id)["status"] == "allocated"
    assert systems.open_reviews() == []


async def test_cancel_arriving_with_the_order_releases_the_reservation(systems):
    order_id = await systems.buy_on_shop("WATCH-S10")
    response = await systems.http.post(f"http://shop/orders/{order_id}/cancel")
    assert response.status_code == 303
    # Both events are pending, so the worker handles them in the same batch.
    await systems.run_worker()

    assert systems.ctx.db.get_order(order_id)["status"] == "cancelled"
    assert systems.warehouse.state.stock["WATCH-S10"]["reserved"] == 0
    assert systems.shop.state.stock["WATCH-S10"] == 8
    assert systems.open_reviews() == []


async def test_oversell_is_queued_and_operator_cancels_on_emag(systems):
    await systems.chaos("emag", freeze_stock=True)
    shop_order = await systems.buy_on_shop("MBA-M4")
    await systems.run_worker()
    assert systems.emag.state.stock["MBA-M4"] == 1
    emag_order = await systems.buy_on_emag("MBA-M4")
    await systems.run_worker()

    assert systems.ctx.db.get_order(shop_order)["status"] == "allocated"
    assert systems.ctx.db.get_order(emag_order)["status"] == "failed"
    [item] = systems.open_reviews()
    assert (item["kind"], item["order_id"]) == ("unfulfillable", emag_order)

    await systems.decide(item["id"], "cancel")

    assert systems.emag_order(emag_order)["status"] == 0
    assert systems.ctx.db.get_order(emag_order)["status"] == "cancelled"
    assert systems.warehouse.state.stock["MBA-M4"]["reserved"] == 1
