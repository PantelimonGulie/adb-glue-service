ORDER_KEYS = {
    "order_id",
    "channel",
    "sku",
    "product",
    "qty",
    "status",
    "attempts",
    "last_error",
    "updated_at",
}


async def get(systems, path: str, **params: object) -> dict:
    response = await systems.http.get(f"http://glue{path}", params=params)
    assert response.status_code == 200, response.text
    return response.json()


async def test_orders_filter_and_page(systems):
    for sku in ("MBA-M4", "IPH16-128", "APP-3"):
        await systems.buy_on_shop(sku)
    for sku in ("IPAD-A16", "WATCH-S10"):
        await systems.buy_on_emag(sku)
    await systems.run_worker()

    emag = await get(systems, "/api/orders", channel="emag")
    second = await get(systems, "/api/orders", per_page=2, page=2)
    macbook = await get(systems, "/api/orders", q="macbook")

    assert emag["total"] == 2
    assert {row["channel"] for row in emag["rows"]} == {"emag"}
    assert (len(second["rows"]), second["total"]) == (2, 5)
    assert (second["page"], second["per_page"]) == (2, 2)
    [row] = macbook["rows"]
    assert set(row) == ORDER_KEYS
    assert (row["sku"], row["product"], row["qty"], row["status"]) == (
        "MBA-M4",
        "MacBook Air M4",
        1,
        "allocated",
    )


async def test_order_detail_has_timeline(systems):
    order_id = await systems.buy_on_shop("APP-3")
    await systems.run_worker()

    detail = await get(systems, f"/api/orders/{order_id}")
    missing = await systems.http.get("http://glue/api/orders/shop-999")

    assert detail["order"]["order_id"] == order_id
    actions = [row["action"] for row in detail["timeline"]]
    assert actions[:2] == ["event_received", "order_allocated"]
    assert isinstance(detail["timeline"][0]["detail"], dict)
    assert missing.status_code == 404


async def test_stock_rows_states(systems):
    await systems.chaos("emag", reject_sku="MBA-M4")
    await systems.reconcile()

    refused = await get(systems, "/api/stock")
    await systems.chaos("emag", reject_sku=None)
    pushed = await systems.act("/api/stock/push")
    fixed = await get(systems, "/api/stock")

    states = {row["sku"]: row["state"] for row in refused["rows"]}
    assert states.pop("MBA-M4") == "refused"
    assert set(states.values()) == {"in_sync"}
    row = next(row for row in refused["rows"] if row["sku"] == "IPH16-128")
    assert row["product"] == "iPhone 16 · 128GB"
    assert (row["free"], row["shop"]) == (25, {"qty": 25, "dirty": False})
    assert row["held_back"] == {"shop": 0, "emag": 0}
    assert refused["reconcile_seconds"] == systems.ctx.tuning.reconcile_interval_seconds
    assert pushed.status_code == 202
    assert {row["state"] for row in fixed["rows"]} == {"in_sync"}


async def test_viewer_cannot_push_stock(systems):
    await systems.sign_in("viewer")
    response = await systems.act("/api/stock/push")

    assert response.status_code == 403


async def test_events_cursor_pages(systems):
    start = systems.ctx.db.audit_tail(1)[0]["id"]
    for n in range(250):
        systems.ctx.db.audit(f"burst-{n}", "order", f"shop-{n}", "event_received", {})

    first = await get(systems, "/api/events", after=start, limit=200)
    rest = await get(systems, "/api/events", after=first["last_id"], limit=200)
    caught_up = await get(systems, "/api/events", after=rest["last_id"])

    assert (len(first["rows"]), first["more"]) == (200, True)
    assert first["last_id"] == first["rows"][-1]["id"]
    assert (len(rest["rows"]), rest["more"]) == (50, False)
    assert caught_up == {"rows": [], "last_id": rest["last_id"], "more": False}


async def test_activity_kinds(systems):
    await systems.buy_on_shop("IPH16-128")
    await systems.chaos("shop", duplicate_last=True)
    await systems.run_worker()

    duplicates = await get(systems, "/api/activity", kind="duplicates")
    everything = await get(systems, "/api/activity", per_page=5)

    assert duplicates["total"] == 1
    assert [row["action"] for row in duplicates["rows"]] == ["duplicate_dropped"]
    assert len(everything["rows"]) == 5
    assert everything["total"] > 5
    ids = [row["id"] for row in everything["rows"]]
    assert ids == sorted(ids, reverse=True)


async def test_overview_counts_the_range(systems):
    await systems.buy_on_shop("IPH16-128")
    await systems.chaos("shop", duplicate_last=True)
    await systems.run_worker()

    overview = await get(systems, "/api/overview", range="today")

    assert overview["counters"] == {
        "received": 1,
        "duplicates": 1,
        "reserved": 1,
        "retries": 0,
        "failed": 0,
    }
    assert overview["previous"] == {key: 0 for key in overview["counters"]}
    up = {name: system["ok"] for name, system in overview["systems"].items()}
    assert up == {"shop": True, "emag": True, "warehouse": True}
    assert (overview["open_reviews"], overview["review_groups"]) == (0, [])
    assert len(overview["latest"]) == 10
