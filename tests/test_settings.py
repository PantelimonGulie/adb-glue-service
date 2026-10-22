import glue.main
from glue import tuning


async def test_settings_change_applies_to_retries(systems, sleeps):
    await systems.sign_in("admin")
    response = await systems.put("/api/settings", retry_attempts=2)

    assert response.status_code == 200
    body = response.json()
    assert (body["retry_attempts"], body["http_timeout_seconds"]) == (2, 2)
    assert [(c["name"], c["ok"]) for c in body["connections"]] == [
        ("shop", True),
        ("emag", True),
        ("warehouse", True),
    ]

    await systems.chaos("warehouse", down=True)
    order_id = await systems.buy_on_shop("IPAD-A16")
    await systems.run_worker()

    order = systems.ctx.db.get_order(order_id)
    assert (order["status"], order["attempts"]) == ("failed", 2)
    [change] = [r for r in systems.ctx.db.audit_tail() if r["action"] == "settings_changed"]
    assert change["detail"] == {"retry_attempts": 2, "by": "admin"}


async def test_settings_validation(systems):
    await systems.sign_in("admin")
    response = await systems.put("/api/settings", retry_attempts=0)

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "retry_attempts"]
    assert systems.ctx.tuning.retry_attempts == 5


async def test_operator_cannot_change_settings(systems):
    response = await systems.put("/api/settings", retry_attempts=2)

    assert response.status_code == 403
    assert systems.ctx.tuning.retry_attempts == 5


async def test_settings_survive_restart(systems):
    tuning.save(systems.ctx, {"retry_attempts": 2}, "admin")
    restarted = glue.main.build_context(systems.ctx.settings, systems.http)

    assert restarted.tuning.retry_attempts == 2
    restarted.db.close()


async def test_users_lists_three_roles(systems):
    response = await systems.http.get("http://glue/api/users")

    users = response.json()
    assert [(u["name"], u["role"]) for u in users] == [
        ("viewer", "viewer"),
        ("operator", "operator"),
        ("admin", "admin"),
    ]
    assert users[2]["permissions"] == ["ask", "decide", "demo", "rules", "settings", "view"]
