async def page(systems, system: str, **params: str) -> str:
    response = await systems.http.get(f"http://{system}/", params=params)
    assert response.status_code == 200
    return response.text


async def test_shop_page_shows_orders_in_customer_words(systems):
    shipped = await systems.buy_on_shop("APP-3")
    cancelled = await systems.buy_on_shop("MBA-M4")
    await systems.run_worker()
    await systems.http.post(f"http://shop/orders/{cancelled}/cancel")
    await systems.http.post(f"http://warehouse/orders/{shipped}/ship")
    await systems.buy_on_shop("IPH16-128")
    await systems.run_worker()

    html = await page(systems, "shop")

    assert 'src="/static/common/products/IPH16-128.svg"' in html
    assert html.count('class="status is-open">Processing') == 1
    assert html.count('class="status is-shipped">Shipped') == 1
    assert html.count('class="status is-cancelled">Cancelled') == 1
    assert html.count("Cancel order<span") == 1


async def test_shop_search_and_category_filter_the_catalog(systems):
    by_query = await page(systems, "shop", q="macbook")
    by_category = await page(systems, "shop", category="phones")

    assert by_query.count('<article class="card') == 1
    assert by_category.count('<article class="card') == 2
    assert "Nothing matches “pixel”." in await page(systems, "shop", q="pixel")
    assert "There is no such category." in await page(systems, "shop", category="cameras")


async def test_marketplace_page_shows_callbacks_acknowledges_and_seller_cancels(systems):
    acknowledged = await systems.buy_on_emag("APP-3")
    await systems.run_worker()
    await systems.recount("IPH16-128", 0)
    sold_out = await systems.buy_on_emag("IPH16-128")
    await systems.buy_on_emag("IPAD-A16")
    await systems.chaos("emag", renotify_now=True)

    html = await page(systems, "emag")

    assert f"← order/acknowledge {acknowledged.removeprefix('emag-')} · 200" in html
    assert html.count("sent 2× · every 20 s") == 2
    assert html.count(">not yet<") == 2

    await systems.run_worker()
    [item] = [i for i in systems.open_reviews() if i["order_id"] == sold_out]
    await systems.decide(item["id"], "cancel")
    html = await page(systems, "emag")

    assert "0 · Cancelled by seller" in html
    assert "33.3% <span>1 of 3 orders</span>" in html


async def test_marketplace_counts_only_delivered_callbacks(systems):
    # Glue refuses a callback signed with the wrong secret, so it is never delivered.
    systems.emag.state.secret = "not-the-shared-secret"
    order_id = await systems.buy_on_emag("APP-3")

    html = await page(systems, "emag")

    assert "sent 0× · every 20 s" in html
    assert f"order {order_id.removeprefix('emag-')} · new · not delivered" in html


async def test_marketplace_page_shows_how_each_offer_update_went(systems):
    await systems.chaos("emag", reject_sku="MBA-M4")
    await systems.reconcile()
    await systems.chaos("emag", rate_limit=True)
    await systems.http.post("http://emag/api-3/order/read", json={"id": 1})

    html = await page(systems, "emag")

    assert html.count("rejected: validation error") == 1
    assert html.count(">applied<") == 5
    assert "← product_offer/save · 6 items · 1 rejected" in html
    assert "← order/read · 429 · Retry-After 1" in html


async def test_warehouse_page_lists_picks_by_bin_and_the_outbox(systems):
    order_id = await systems.buy_on_shop("MBA-M4")
    await systems.run_worker()

    html = await page(systems, "warehouse")

    assert f'<td class="order">{order_id}</td>' in html
    assert '1 × MBA-M4 <span class="name">MacBook Air M4</span>' in html
    assert '<span class="bin-label">Bin</span><span class="line">A-03-2</span>' in html
    assert f"201 order accepted · {order_id}" in html

    await systems.http.post(f"http://warehouse/orders/{order_id}/ship")
    await systems.recount("IPAD-A16", 0)
    html = await page(systems, "warehouse")

    assert "Nothing to pick" in html
    assert f"→ order.shipped · {order_id} · delivered" in html
    assert "→ stock.adjusted · IPAD-A16 on hand 0 · delivered" in html


async def test_warehouse_outage_is_shown_and_turns_off_ship_and_save(systems, sleeps):
    await systems.chaos("warehouse", down=True)
    order_id = await systems.buy_on_shop("APP-3")
    await systems.run_worker()

    html = await page(systems, "warehouse")

    assert "Warehouse API offline" in html
    assert f"503 order refused, API offline · key {order_id}" in html
    assert html.count("disabled>Save") == 6


async def test_mock_pages_load_vendored_fonts_and_art(systems):
    for path in (
        "http://shop/static/shop.css",
        "http://shop/static/common/fonts/schibsted-grotesk-latin-800-normal.woff2",
        "http://shop/static/common/products/WATCH-S10.svg",
        "http://emag/static/marketplace.css",
        "http://warehouse/static/warehouse.css",
        "http://warehouse/static/common/fonts/jetbrains-mono-latin-400-normal.woff2",
    ):
        assert (await systems.http.get(path)).status_code == 200
