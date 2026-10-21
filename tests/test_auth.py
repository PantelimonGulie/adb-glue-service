from glue.auth import COOKIE


async def failed_order(systems) -> int:
    await systems.chaos("warehouse", down=True)
    await systems.buy_on_shop("IPH16-256")
    await systems.run_worker()
    await systems.chaos("warehouse", down=False)
    [item] = systems.open_reviews()
    return item["id"]


async def test_viewer_cannot_decide_but_operator_can(systems, sleeps):
    item_id = await failed_order(systems)
    await systems.sign_in("viewer")
    page = await systems.http.get("http://glue/review")
    refused = await systems.decide(item_id, "retry")
    await systems.sign_in("operator")
    allowed = await systems.decide(item_id, "retry")

    assert page.status_code == 200
    assert refused.status_code == 403
    assert allowed.status_code == 200
    [item] = systems.ctx.db.list_review("decided")
    assert item["decided_by"] == "operator"


async def test_only_admin_edits_rules_and_demo_controls(systems):
    refused = await systems.act("/rules/auto-retry", enabled="1")
    demo_refused = await systems.act("/demo/warehouse-down")
    await systems.sign_in("admin")
    saved = await systems.act("/rules/auto-retry", enabled="1")

    assert (refused.status_code, demo_refused.status_code, saved.status_code) == (403, 403, 200)
    assert systems.warehouse.state.chaos.down is False
    [rule] = systems.ctx.db.rules()
    assert (rule["name"], rule["enabled"], rule["updated_by"]) == ("auto-retry", 1, "admin")


async def test_wrong_password_and_tampered_cookie_are_rejected(systems):
    rejected = await systems.sign_in("admin", password="guess")
    assert rejected.status_code == 401

    await systems.sign_in("viewer")
    token = systems.http.cookies[COOKIE]
    systems.http.cookies.set(COOKIE, token.replace("viewer", "admin", 1))
    response = await systems.http.get("http://glue/")

    assert response.status_code == 303
    assert response.headers["location"].startswith("/sign-in")
    counters = systems.ctx.db.counters()
    assert counters["sign_in_rejected"] == 1
