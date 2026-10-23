import itertools
import json

import httpx

from common import signing

STOCK = {"sku": "MBA-M4", "on_hand": 0, "reserved": 0}


async def test_unsigned_and_forged_webhooks_are_rejected(systems):
    body = json.dumps({"type": "stock.adjusted", "data": STOCK}).encode()
    unsigned = await systems.http.post(
        "http://glue/events",
        content=body,
        headers={"x-adobe-event-id": "e-1", "x-source": "warehouse"},
    )
    forged = await systems.send_event("warehouse", "stock.adjusted", STOCK, secret="guessed")
    notification = json.dumps({"order_id": 500123, "type": "new"}).encode()
    # A valid signature from another source must not open the eMAG endpoint.
    wrong_source = await systems.http.post(
        "http://glue/emag/notifications",
        content=notification,
        headers=signing.headers(systems.ctx.settings.shop_webhook_secret, notification),
    )

    assert [r.status_code for r in (unsigned, forged, wrong_source)] == [401, 401, 401]
    counters = systems.ctx.db.counters()
    assert counters["signature_rejected"] == 3
    assert "event_received" not in counters


async def test_a_captured_event_replayed_under_a_new_event_id_is_rejected(systems):
    captured: list[httpx.Request] = []

    async def capture(request: httpx.Request) -> None:
        if request.url.path == "/events":
            captured.append(request)

    systems.http.event_hooks["request"].append(capture)
    await systems.buy_on_shop("APP-3")
    [placed] = captured
    headers = {name: placed.headers[name] for name in ("content-type", "x-source", "x-signature")}

    replayed = await systems.http.post(
        "http://glue/events",
        content=placed.content,
        headers={**headers, "x-adobe-event-id": "replayed-1"},
    )

    assert replayed.status_code == 401
    counters = systems.ctx.db.counters()
    assert (counters["event_received"], counters["signature_rejected"]) == (1, 1)


async def test_signed_but_invalid_event_is_rejected(systems):
    order = {"id": "shop-1", "channel": "shop", "channel_order_id": "1", "customer": "Guest"}
    order["lines"] = [{"sku": "MBA-M4", "qty": 0}]

    response = await systems.send_event("shop", "order.placed", order)

    assert response.status_code == 422
    assert systems.ctx.db.counters()["event_rejected"] == 1
    assert "event_received" not in systems.ctx.db.counters()


async def test_shop_signature_cannot_carry_an_emag_order(systems):
    order = {"id": "emag-500123", "channel": "emag", "channel_order_id": "500123"}
    order |= {"lines": [{"sku": "MBA-M4", "qty": 1}], "customer": "Guest"}

    placed = await systems.send_event("shop", "order.placed", order)
    cancelled = await systems.send_event("shop", "order.cancelled", {"order_id": "emag-500123"})
    await systems.run_worker()

    assert [r.status_code for r in (placed, cancelled)] == [422, 422]
    assert systems.ctx.db.list_orders() == ([], 0)
    assert systems.ctx.db.counters()["event_rejected"] == 2


async def test_warehouse_signature_cannot_place_an_order(systems):
    order = {"id": "shop-1", "channel": "shop", "channel_order_id": "1", "customer": "Guest"}
    order["lines"] = [{"sku": "MBA-M4", "qty": 1}]

    response = await systems.send_event("warehouse", "order.placed", order)

    assert response.status_code == 422
    assert systems.ctx.db.list_orders() == ([], 0)


async def test_a_shop_order_without_lines_is_rejected(systems):
    order = {"id": "shop-1", "channel": "shop", "channel_order_id": "1", "customer": "Guest"}

    response = await systems.send_event("shop", "order.placed", order | {"lines": []})

    assert response.status_code == 422
    assert systems.ctx.db.counters()["event_rejected"] == 1
    assert "event_received" not in systems.ctx.db.counters()


async def test_an_emag_order_without_products_is_not_reserved(systems):
    order_id = await systems.buy_on_emag("APP-3")
    systems.emag_order(order_id)["products"] = []
    await systems.run_worker()

    assert systems.ctx.db.get_order(order_id) is None
    assert systems.warehouse.state.stock["APP-3"]["reserved"] == 0
    [item] = systems.open_reviews()
    assert (item["order_id"], item["payload"]["status"]) == (order_id, "processing")
    assert "List should have at least 1 item" in item["reason"]


async def test_an_event_id_from_one_sender_does_not_hide_another_senders_event(systems):
    systems.emag.state.order_ids = itertools.count(777)
    shop_order = await systems.buy_on_shop("APP-3")
    body = json.dumps({"type": "order.placed", "data": systems.shop.state.orders[shop_order]})
    # A shop event whose id is the one Glue gives eMAG's notice about order 777.
    event_id = "emag-notify-777-new"
    message = signing.event_message(event_id, body.encode())
    headers = {"x-adobe-event-id": event_id, "x-source": "shop"}
    headers |= signing.headers(systems.ctx.settings.shop_webhook_secret, message)
    await systems.http.post("http://glue/events", content=body, headers=headers)
    emag_order = await systems.buy_on_emag("APP-3")
    await systems.run_worker()

    assert emag_order == "emag-777"
    assert systems.ctx.db.get_order(emag_order)["status"] == "allocated"
    assert "duplicate_dropped" not in systems.ctx.db.counters()


async def notify_emag(systems, order_id: str, kind: str) -> None:
    body = json.dumps({"order_id": int(order_id.removeprefix("emag-")), "type": kind}).encode()
    headers = signing.headers(systems.ctx.settings.emag_webhook_secret, body)
    response = await systems.http.post(
        "http://glue/emag/notifications", content=body, headers=headers
    )
    assert response.status_code == 202
    await systems.run_worker()


async def test_a_cancel_notice_for_an_order_emag_still_shows_open_changes_nothing(systems):
    order_id = await systems.buy_on_emag("APP-3")
    await systems.run_worker()

    await notify_emag(systems, order_id, "cancelled")

    assert systems.emag_order(order_id)["status"] == 2
    assert systems.ctx.db.get_order(order_id)["status"] == "allocated"
    assert systems.warehouse.state.stock["APP-3"]["reserved"] == 1
    assert systems.open_reviews() == []
    [ignored] = [
        row for row in systems.ctx.db.audit_for(order_id) if row["action"] == "cancel_ignored"
    ]
    assert ignored["detail"]["reason"] == (
        "eMAG still shows this order as in progress, so Glue did not cancel it"
    )


async def test_a_new_order_notice_for_an_order_emag_shows_cancelled_reserves_nothing(systems):
    order_id = await systems.buy_on_emag("APP-3")
    systems.emag_order(order_id)["status"] = 0
    await systems.run_worker()

    assert systems.ctx.db.get_order(order_id)["status"] == "cancelled"
    assert systems.warehouse.state.stock["APP-3"]["reserved"] == 0


def test_an_empty_secret_verifies_nothing():
    body = b'{"type": "order.cancelled"}'

    assert signing.verify("", body, signing.sign("", body)) is False


async def test_mutation_needs_glue_header(systems):
    await systems.sign_in("admin")
    await systems.chaos("warehouse", down=True)
    no_header = await systems.http.post("http://glue/api/demo/reset")
    cross_site = await systems.http.post(
        "http://glue/api/demo/reset",
        headers={"X-Glue-Request": "1", "Origin": "http://attacker.example"},
    )
    sign_in = await systems.http.post(
        "http://glue/api/session", json={"username": "admin", "password": "admin"}
    )

    assert [r.status_code for r in (no_header, cross_site, sign_in)] == [403, 403, 403]
    assert systems.warehouse.state.chaos.down is True

    same_origin = await systems.http.post(
        "http://glue/api/demo/reset", headers={"X-Glue-Request": "1", "Origin": "http://glue"}
    )

    assert same_origin.status_code == 200
    assert systems.warehouse.state.chaos.down is False
