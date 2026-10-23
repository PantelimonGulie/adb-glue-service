import asyncio
import time

import pytest

import emag.main
import shop.main
from common.models import Order
from glue import review, worker


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


async def test_a_failed_event_sent_again_goes_back_to_the_queue(systems, sleeps):
    await systems.chaos("emag", down=True)
    await systems.buy_on_emag("APP-3")
    await systems.run_worker()
    assert systems.ctx.db.rows("SELECT status FROM events_inbox") == [{"status": "failed"}]

    await systems.chaos("emag", down=False, renotify_now=True)

    [event] = systems.ctx.db.rows("SELECT status, error FROM events_inbox")
    assert event == {"status": "pending", "error": None}
    assert systems.ctx.db.counters()["event_received"] == 2
    assert "duplicate_dropped" not in systems.ctx.db.counters()


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


async def test_two_cancels_for_one_order_in_one_batch_cancel_it_once(systems):
    order_id = await systems.buy_on_shop("WATCH-S10")
    await systems.run_worker()
    sent = []
    cancel = systems.ctx.warehouse.cancel_order

    async def counted(order_id: str):
        sent.append(order_id)
        return await cancel(order_id)

    systems.ctx.warehouse.cancel_order = counted
    # Adobe Commerce may deliver the same cancellation twice under different event ids.
    for _ in range(2):
        await systems.send_event("shop", "order.cancelled", {"order_id": order_id})
    await systems.run_worker()

    assert sent == [order_id]
    counters = systems.ctx.db.counters()
    assert (counters["order_cancelled"], counters["cancel_repeated"]) == (1, 1)
    assert "order_known" not in counters
    assert systems.ctx.db.get_order(order_id)["status"] == "cancelled"


async def test_an_operator_cancel_and_a_customer_cancel_cancel_the_order_once(systems):
    order_id = await systems.buy_on_shop("APP-3")
    await systems.run_worker()
    await systems.recount("APP-3", 0)
    await systems.run_worker()
    [item] = systems.open_reviews()
    sent = []
    answer = asyncio.Event()
    cancel = systems.ctx.warehouse.cancel_order

    async def slow(order_id: str):
        sent.append(order_id)
        await answer.wait()
        return await cancel(order_id)

    systems.ctx.warehouse.cancel_order = slow
    operator = asyncio.create_task(review.decide(systems.ctx, item["id"], "cancel"))
    for _ in range(50):
        await asyncio.sleep(0)
    assert sent == [order_id]
    # The customer cancels too, while the operator's cancel waits on the warehouse.
    await systems.send_event("shop", "order.cancelled", {"order_id": order_id})
    customer = asyncio.create_task(systems.run_worker())
    for _ in range(50):
        await asyncio.sleep(0)
    answer.set()
    await asyncio.gather(operator, customer)

    assert sent == [order_id]
    assert systems.ctx.db.counters()["order_cancelled"] == 1


async def test_the_worker_loop_refills_a_slot_as_soon_as_it_frees(systems):
    orders = [await systems.buy_on_shop("APP-3") for _ in range(25)]
    loop = asyncio.create_task(worker.run_forever(systems.ctx))

    async def drained() -> None:
        inbox = systems.ctx.db.gauges()["inbox"]
        while inbox["pending"] or inbox["processing"]:
            await asyncio.sleep(0.01)
            inbox = systems.ctx.db.gauges()["inbox"]

    # 25 events through 10 slots: waiting the 0.5 s poll interval whenever every slot is busy
    # would take at least a second.
    try:
        await asyncio.wait_for(drained(), 0.5)
    finally:
        loop.cancel()
        await asyncio.gather(loop, return_exceptions=True)
    assert {systems.ctx.db.get_order(order_id)["status"] for order_id in orders} == {"allocated"}
