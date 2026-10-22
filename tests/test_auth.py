from glue.auth import COOKIE


async def test_sign_in_returns_user_and_cookie(systems):
    systems.http.cookies.clear()
    response = await systems.sign_in("operator")
    me = await systems.http.get("http://glue/api/me")

    assert response.status_code == 200
    user = {"name": "operator", "role": "operator", "permissions": ["ask", "decide", "view"]}
    assert response.json() == user
    assert COOKIE in response.cookies
    assert me.json() == user


async def test_wrong_password_401(systems):
    response = await systems.sign_in("admin", password="guess")

    assert response.status_code == 401
    assert systems.ctx.db.counters()["sign_in_rejected"] == 1


async def test_me_requires_session(systems):
    systems.http.cookies.clear()
    response = await systems.http.get("http://glue/api/me")

    assert response.status_code == 401


async def test_tampered_cookie_is_rejected(systems):
    await systems.sign_in("viewer")
    token = systems.http.cookies[COOKIE]
    systems.http.cookies.set(COOKIE, token.replace("viewer", "admin", 1))
    response = await systems.http.get("http://glue/api/me")

    assert response.status_code == 401


async def test_sign_out_clears_cookie(systems):
    response = await systems.http.delete("http://glue/api/session", headers={"X-Glue-Request": "1"})
    me = await systems.http.get("http://glue/api/me")

    assert response.status_code == 204
    assert COOKIE not in systems.http.cookies
    assert me.status_code == 401


async def test_viewer_gets_403_with_detail(systems):
    await systems.sign_in("viewer")
    response = await systems.act("/api/demo/reset")

    assert response.status_code == 403
    assert response.json()["detail"] == "a viewer may not do this"


async def test_only_admin_runs_demo_controls(systems):
    refused = await systems.act("/api/demo/warehouse-down")
    await systems.sign_in("admin")
    done = await systems.act("/api/demo/warehouse-down")

    assert refused.status_code == 403
    assert done.json() == {"ok": True, "message": "The warehouse answers 503 to every call."}
    assert systems.warehouse.state.chaos.down is True
