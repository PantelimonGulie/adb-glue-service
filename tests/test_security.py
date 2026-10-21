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


async def test_dashboard_actions_need_the_htmx_header_from_same_origin(systems):
    no_header = await systems.http.post("http://glue/review/1/dismiss")
    demo = await systems.http.post("http://glue/demo/warehouse-down")
    cross_site = await systems.http.post(
        "http://glue/review/1/dismiss",
        headers={"HX-Request": "true", "Origin": "http://attacker.example"},
    )

    assert [r.status_code for r in (no_header, demo, cross_site)] == [403, 403, 403]
    assert systems.warehouse.state.chaos.down is False
