from collections import Counter
from contextlib import suppress

import pytest

import glue.main
from glue import review, worker
from glue.retry import Problem
from tests.crash import CrashingConnection, Webhooks

# Glue's own changes to an order, each recorded once whether or not Glue stopped on the way.
STATE_CHANGES = (
    "order_allocated",
    "order_failed",
    "unfulfillable",
    "order_cancelled",
    "order_shipped",
    "emag_acknowledged",
)


async def nothing(systems) -> None:
    pass


async def reserved_on_shop(systems) -> str:
    order_id = await systems.buy_on_shop("WATCH-S10")
    await systems.run_worker()
    return order_id


async def sold_on_emag_first(systems) -> None:
    await systems.buy_on_emag("MBA-M4")
    await systems.run_worker()
    # The shop still shows the last unit: the push that zeroes it has not landed yet.
    systems.shop.state.stock["MBA-M4"] = 1


async def warehouse_down(systems) -> None:
    await systems.chaos("warehouse", down=True)


async def failed_in_outage(systems) -> int:
    await systems.chaos("warehouse", down=True)
    await systems.buy_on_shop("IPH16-256")
    await systems.run_worker()
    await systems.chaos("warehouse", down=False)
    [item] = systems.open_reviews()
    return item["id"]


async def failed_on_shop(systems) -> str:
    return systems.ctx.db.get_review(await failed_in_outage(systems))["order_id"]


async def failed_on_emag_then_emag_down(systems) -> int:
    await systems.chaos("warehouse", down=True)
    await systems.buy_on_emag("IPH16-256")
    await systems.run_worker()
    await systems.chaos("warehouse", down=False)
    await systems.chaos("emag", down=True)
    [item] = systems.open_reviews()
    return item["id"]


async def emag_down(systems) -> None:
    await systems.chaos("emag", down=True)


async def buy_on_shop(systems, _: None) -> None:
    await systems.buy_on_shop("MBA-M4")
    await systems.run_worker()


async def cancel_on_shop(systems, order_id: str) -> None:
    await systems.http.post(f"http://shop/orders/{order_id}/cancel")
    await systems.run_worker()


async def ship(systems, order_id: str) -> None:
    await systems.http.post(f"http://warehouse/orders/{order_id}/ship")
    await systems.run_worker()


async def buy_on_emag(systems, _: None) -> None:
    await systems.buy_on_emag("MBA-M4")
    await systems.run_worker()


async def recount_to_zero(systems, _: str) -> None:
    await systems.recount("WATCH-S10", 0)
    await systems.run_worker()


async def retry(systems, item_id: int) -> None:
    await review.decide(systems.ctx, item_id, "retry")


async def retry_again(systems) -> None:
    # The person never saw an answer, so they retry what is still waiting.
    for item in systems.open_reviews():
        if "retry" in review.allowed_actions(item, systems.ctx.db.get_order(item["order_id"])):
            await review.decide(systems.ctx, item["id"], "retry")


async def cancel(systems, item_id: int) -> None:
    # eMAG is down, so the cancel fails and the person is shown why.
    with suppress(Problem):
        await review.decide(systems.ctx, item_id, "cancel")


# Each is (setup, act, what a person does again after the restart); only the act can crash.
# The last four reach branches the others never do: a failed event, an item settled by the
# order's new status, a decision whose action fails, and a recount that finds the shelf short.
SCENARIOS = {
    "place-reserved": (nothing, buy_on_shop, nothing),
    "place-sold-elsewhere": (sold_on_emag_first, buy_on_shop, nothing),
    "place-in-outage": (warehouse_down, buy_on_shop, nothing),
    "cancel-reserved": (reserved_on_shop, cancel_on_shop, nothing),
    "ship-reserved": (reserved_on_shop, ship, nothing),
    "emag-order": (nothing, buy_on_emag, nothing),
    "decide-retry": (failed_in_outage, retry, retry_again),
    "emag-unreadable": (emag_down, buy_on_emag, nothing),
    "cancel-failed": (failed_on_shop, cancel_on_shop, nothing),
    "decide-cancel-fails": (failed_on_emag_then_emag_down, cancel, nothing),
    "recount-short": (reserved_on_shop, recount_to_zero, nothing),
}


async def restart(systems, crashed: CrashingConnection) -> None:
    # Closing without a commit rolls back an open transaction, as SQLite does after a crash.
    crashed.conn.close()
    systems.ctx = glue.main.build_context(systems.ctx.settings, systems.http)
    systems.glue.state.ctx = systems.ctx
    await systems.reconcile()


def orders(systems) -> list[tuple[str, str, object]]:
    # Labelled by channel and place in that channel's list: order numbers come from the clock.
    shop = [(order_id, order["status"]) for order_id, order in systems.shop.state.orders.items()]
    emag = [(f"emag-{n}", order["status"]) for n, order in systems.emag.state.orders.items()]
    return [
        (f"{order_id.split('-')[0]}#{place}", order_id, on_channel)
        for placed in (shop, emag)
        for place, (order_id, on_channel) in enumerate(placed, start=1)
    ]


def outcome(systems) -> dict[str, object]:
    # What every run must end with, the same as the run without a crash; keys name the invariant.
    db = systems.ctx.db
    seen = {
        "2. shop stock": dict(systems.shop.state.stock),
        "2. eMAG stock": dict(systems.emag.state.stock),
    }
    for label, order_id, on_channel in orders(systems):
        order = db.get_order(order_id)
        status = (order and order["status"], on_channel, len(db.open_reviews_for(order_id)))
        seen[f"2. {label} (Glue status, channel status, open items)"] = status
        rows = db.rows("SELECT action FROM audit_log WHERE entity_id = ?", (order_id,))
        recorded = Counter(row["action"] for row in rows)
        for action in STATE_CHANGES:
            seen[f"4. {label} {action} rows"] = recorded[action]
    return seen


def broken(systems) -> list[str]:
    db = systems.ctx.db
    problems = []

    allocated = db.rows("SELECT * FROM orders WHERE status = 'allocated'", (), "lines")
    warehouse = systems.warehouse.state
    held = {order["id"] for order in warehouse.orders.values() if order["status"] == "reserved"}
    if held != {order["order_id"] for order in allocated}:
        mine = sorted(order["order_id"] for order in allocated)
        problems.append(f"1. the warehouse holds {sorted(held)}, Glue has {mine} allocated")
    needed = Counter()
    for order in allocated:
        for line in order["lines"]:
            needed[line["sku"]] += line["qty"]
    reserved = Counter({sku: level["reserved"] for sku, level in warehouse.stock.items()})
    if reserved != needed:
        problems.append(f"1. the warehouse reserves {+reserved}, Glue's orders need {+needed}")

    items = db.rows("SELECT * FROM review_queue", (), "payload")
    waiting = [item for item in items if item["status"] == "open"]
    for order in db.rows("SELECT order_id FROM orders WHERE status = 'failed'"):
        count = sum(item["order_id"] == order["order_id"] for item in waiting)
        if count != 1:
            problems.append(f"3. failed order {order['order_id']} has {count} open items")
    same = Counter((i["order_id"], i["kind"], i["payload"].get("operation")) for i in waiting)
    problems += [f"3. {key} has {count} open items" for key, count in same.items() if count > 1]
    problems += [f"3. item {i['id']} is still acting" for i in items if i["status"] == "acting"]

    audit = db.rows(
        "SELECT action, entity_id, json_extract(detail, '$.review_id') AS item FROM audit_log"
    )
    by_entity = Counter((row["action"], row["entity_id"]) for row in audit)
    by_item = Counter((row["action"], row["item"]) for row in audit)
    events = db.rows("SELECT * FROM events_inbox", (), "payload")
    for event in events:
        count = by_entity["event_received", event["event_id"]]
        if count != 1:
            problems.append(f"4. event {event['event_id']} has {count} event_received rows")
    for item in items:
        resolved = int(item["action"] == "resolved")
        for action, want in (("review_opened", 1), ("review_resolved", resolved)):
            if by_item[action, item["id"]] != want:
                problems.append(
                    f"4. item {item['id']} has {by_item[action, item['id']]} {action} rows"
                )

    for event in events:
        order_id = worker.order_id_in(event)
        kept = event["status"] == "failed" and any(i["order_id"] == order_id for i in waiting)
        if event["status"] != "done" and not kept:
            problems.append(f"5. event {event['event_id']} ended {event['status']}, no open item")
    return problems


async def run(start_systems, name: str, at: int) -> tuple[CrashingConnection, dict, list[str]]:
    setup, act, again = SCENARIOS[name]
    async with start_systems(f"{name}-{at}") as systems:
        prepared = await setup(systems)
        webhooks = Webhooks(systems.http)
        for sender in (systems.shop, systems.emag, systems.warehouse):
            sender.state.http = webhooks
        conn = CrashingConnection(systems.ctx.db.conn, at)
        systems.ctx.db.conn = conn
        try:
            await act(systems, prepared)
        except BaseException:
            # A mock's middleware can turn the crash into an error of its own on the way out.
            if not conn.dead:
                raise
        await restart(systems, conn)
        await webhooks.send_again()
        await systems.run_worker()
        await again(systems)
        await systems.reconcile()
        return conn, outcome(systems), broken(systems)


@pytest.mark.parametrize("name", SCENARIOS)
async def test_glue_stopped_before_any_write_ends_as_if_it_never_stopped(
    start_systems, sleeps, name
):
    clean, expected, problems = await run(start_systems, name, at=0)
    assert problems == [], f"{name} without a crash: {problems}"
    failures = []
    for at, sql in enumerate(clean.writes, start=1):
        crashed, actual, problems = await run(start_systems, name, at)
        if not crashed.dead:
            problems.append(f"never reached write {at}")
        problems += [
            f"{key}: {actual.get(key)}, the crash-free run has {expected.get(key)}"
            for key in sorted(expected.keys() | actual.keys())
            if actual.get(key) != expected.get(key)
        ]
        failures += [f"{name}@write-{at} ({sql[:80]}): {problem}" for problem in problems]
    assert not failures, "\n".join(failures)
