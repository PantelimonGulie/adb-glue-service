from glue import rules


async def hold_back_on_emag(systems, units: int, sku: str = "") -> None:
    config = {"channel": "emag", "units": units, "sku": sku}
    rules.save(systems.ctx, "stock-buffer", True, config, "admin")
    await systems.reconcile()


async def test_stock_buffer_holds_units_back_from_one_channel(systems):
    await hold_back_on_emag(systems, 2)

    assert systems.emag.state.stock["IPH16-128"] == 23
    assert systems.emag.state.stock["MBA-M4"] == 0
    assert systems.shop.state.stock["IPH16-128"] == 25
    pushes = [r for r in systems.ctx.db.audit_for("IPH16-128") if r["action"] == "stock_pushed"]
    expected = {"channel": "emag", "qty": 23, "rule": "stock-buffer", "held_back": 2}
    assert pushes[-1]["detail"] == expected

    await hold_back_on_emag(systems, 1, sku="APP-3")

    assert systems.emag.state.stock["APP-3"] == 39
    assert systems.emag.state.stock["IPH16-128"] == 25


async def test_auto_retry_fires_once_when_the_warehouse_recovers(systems, sleeps):
    rules.save(systems.ctx, "auto-retry", True, {}, "admin")
    await systems.chaos("warehouse", down=True)
    order_id = await systems.buy_on_shop("IPAD-A16")
    await systems.run_worker()
    await systems.reconcile()
    assert systems.ctx.db.get_order(order_id)["status"] == "failed"
    assert systems.ctx.warehouse_down is True

    await systems.chaos("warehouse", down=False)
    await systems.reconcile()
    await systems.reconcile()

    assert systems.ctx.db.get_order(order_id)["status"] == "allocated"
    assert systems.open_reviews() == []
    [item] = systems.ctx.db.list_review("decided")
    assert (item["action"], item["decided_by"]) == ("retry", "rule:auto-retry")
    applied = [r for r in systems.ctx.db.audit_for(order_id) if r["action"] == "rule_applied"]
    assert [r["detail"]["rule"] for r in applied] == ["auto-retry"]


async def test_operator_cannot_save_rule(systems):
    response = await systems.put("/api/rules/auto-retry", enabled=True, config={})

    assert response.status_code == 403
    assert systems.ctx.db.rules() == []


async def test_admin_saves_stock_buffer_and_channels_follow(systems):
    await systems.sign_in("admin")
    config = {"channel": "emag", "units": 2, "sku": ""}
    saved = await systems.put("/api/rules/stock-buffer", enabled=True, config=config)
    listed = await systems.http.get("http://glue/api/rules")

    assert saved.status_code == 200
    assert saved.json()["enabled"] is True
    assert saved.json()["config"] == config
    assert systems.emag.state.stock["IPH16-128"] == 23
    assert [rule["name"] for rule in listed.json()] == ["stock-buffer", "auto-retry"]
    assert listed.json()[1]["enabled"] is False
