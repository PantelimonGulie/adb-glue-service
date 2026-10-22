import json

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
    assert systems.ctx.db.list_orders() == []
    assert systems.ctx.db.counters()["event_rejected"] == 2


async def test_warehouse_signature_cannot_place_an_order(systems):
    order = {"id": "shop-1", "channel": "shop", "channel_order_id": "1", "customer": "Guest"}
    order["lines"] = [{"sku": "MBA-M4", "qty": 1}]

    response = await systems.send_event("warehouse", "order.placed", order)

    assert response.status_code == 422
    assert systems.ctx.db.list_orders() == []


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
