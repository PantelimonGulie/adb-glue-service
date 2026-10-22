import httpx
from fastapi import FastAPI

from glue.spa import mount_spa


async def test_spa_serves_index_for_its_own_pages_only(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app.js").write_text("start()")
    (tmp_path / "index.html").write_text("<div id=root></div>")
    app = FastAPI()
    mount_spa(app, tmp_path)

    transport = httpx.ASGITransport(app)
    async with httpx.AsyncClient(transport=transport, base_url="http://glue") as http:
        page = await http.get("/orders/shop-1")
        script = await http.get("/assets/app.js")
        others = [
            await http.get(path)
            for path in ("/api/nope", "/events", "/emag/notifications", "/health/x")
        ]

    assert (page.status_code, page.text) == (200, "<div id=root></div>")
    assert script.text == "start()"
    assert [r.status_code for r in others] == [404, 404, 404, 404]


def test_spa_is_skipped_without_a_build(tmp_path):
    app = FastAPI()
    routes = list(app.routes)
    mount_spa(app, tmp_path / "dist")

    assert app.routes == routes


async def test_spa_needs_index_html_and_survives_missing_assets(tmp_path):
    (tmp_path / "assets").mkdir()
    without_index = FastAPI()
    routes = list(without_index.routes)
    mount_spa(without_index, tmp_path)

    only_index = tmp_path / "only-index"
    only_index.mkdir()
    (only_index / "index.html").write_text("<div id=root></div>")
    app = FastAPI()
    mount_spa(app, only_index)
    transport = httpx.ASGITransport(app)
    async with httpx.AsyncClient(transport=transport, base_url="http://glue") as http:
        page = await http.get("/orders")

    assert without_index.routes == routes
    assert page.text == "<div id=root></div>"
