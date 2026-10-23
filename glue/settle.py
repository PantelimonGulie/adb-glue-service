from glue import review
from glue.audit import record
from glue.context import Context

# Failed operations an order's new status makes moot: it got there another way, or the
# customer no longer wants it. A failed cancel stays open on a shipped order: it needs a person,
# and so does an item that does not say which operation failed.
SETTLED_BY = {"shipped": ("place",), "cancelled": ("place", "cancel")}


def resolve(ctx: Context, item: dict, correlation_id: str, why: str) -> None:
    ctx.db.decide_review(item["id"], "resolved", "glue")
    record(
        ctx.db,
        correlation_id,
        "order",
        item["order_id"] or "-",
        "review_resolved",
        review_id=item["id"],
        kind=item["kind"],
        why=why,
    )


def settle(ctx: Context, order_id: str, status: str, correlation_id: str) -> None:
    for item in ctx.db.open_reviews_for(order_id):
        if item["payload"].get("operation") in SETTLED_BY[status]:
            resolve(ctx, item, correlation_id, f"the order is {status}")


def settle_event(ctx: Context, order_id: str | None, event: dict) -> None:
    # The item a failed event opened is moot once a redelivery of that event goes through.
    for item in ctx.db.open_reviews_for(order_id):
        failed = item["payload"]
        if (failed.get("source"), failed.get("event_id")) == (event["source"], event["event_id"]):
            resolve(ctx, item, event["event_id"], "its event went through when sent again")


def interrupted_decisions(ctx: Context) -> None:
    # A decision a stop cut short goes back to the queue, as an interrupted event does, unless
    # the order has moved on and its action is no longer one to take.
    for item in ctx.db.list_review("acting"):
        order = ctx.db.get_order(item["order_id"]) if item["order_id"] else None
        if item["action"] in review.allowed_actions({**item, "status": "open"}, order):
            ctx.db.reopen_review(item["id"])
        else:
            why = "the order moved on before Glue stopped mid-decision"
            resolve(ctx, item, f"review-{item['id']}", why)
