from common.catalog import product_name

CAUSES = {
    "outage": "the Bucharest warehouse did not answer when Glue sent the order",
    "soldout": "the last unit was sold on the other channel first, so the warehouse refused it",
    "recount": "the warehouse counted fewer units than are promised to customers",
    "other": "something else went wrong, see what Glue saw",
}
# A failed customer cancellation leaves the order reserved; retrying re-sends the cancellation.
CANCELLING = {
    "outage": "the customer cancelled, but the warehouse did not answer the cancellation",
    "other": "the customer cancelled, but Glue could not cancel the order at the warehouse",
}
CHANNELS = {"shop": "the shop", "emag": "eMAG"}
PROMPT = (
    "Review item {id} needs a decision. The facts:\n{facts}\n"
    "The person may choose one of:\n{choices}\n"
    "Rule for this cause: {playbook}.\n"
    "Use these facts. Recommend exactly one of those choices. Answer in two lines:"
    " 'ACTION: <choice>' then 'REASON: <one short paragraph citing the facts>'."
)


def question(item: dict, order: dict | None, stock: dict[str, dict], answering: bool) -> str:
    return PROMPT.format(
        id=item["id"],
        facts=facts(item, order, stock, answering),
        choices=choices(item, order),
        playbook=playbook(item, order, stock, answering),
    )


def clean(text: object) -> str:
    # Reasons and product codes come from other systems; one short line each keeps the
    # prompt's own lines (the rule, the choices) from being imitated.
    return " ".join(str(text).split())[:300]


def cancelling(item: dict) -> bool:
    return item["payload"].get("operation") == "cancel"


def facts(item: dict, order: dict | None, stock: dict[str, dict], answering: bool) -> str:
    cause = CAUSES[item["cause"]]
    if cancelling(item):
        cause = CANCELLING.get(item["cause"], cause)
    lines = [f"- Cause: {cause}.", f"- What Glue saw: {clean(item['reason'])}."]
    if order:
        channel = CHANNELS[order["channel"]]
        lines.append(
            f"- Order {clean(order['order_id'])} came from {channel}; now {order['status']}."
        )
        for line in order["lines"]:
            name = clean(product_name(line["sku"]))
            lines.append(f"- It asks for {line['qty']} × {name}; {shelf(stock.get(line['sku']))}.")
    state = "is answering" if answering else "is not answering"
    lines.append(f"- The Bucharest warehouse {state} right now.")
    return "\n".join(lines)


def shelf(row: dict | None) -> str:
    if row is None:
        return "stock unknown"
    free = max(0, row["available"])
    return f"the warehouse has {row['on_hand']} on hand, {row['reserved']} reserved, {free} free"


def covered(order: dict, stock: dict[str, dict]) -> bool:
    # A reserved order is already inside `reserved`; a failed one still needs its units.
    held = order["status"] == "allocated"
    for line in order["lines"]:
        row = stock.get(line["sku"])
        if row is None or row["available"] < (0 if held else line["qty"]):
            return False
    return True


# The small local model follows a rule that names one choice, but not a conditional one,
# so the condition is checked here and the model only explains it. Every rule names only
# choices in `allowed`.
def playbook(item: dict, order: dict | None, stock: dict[str, dict], answering: bool) -> str:
    allowed = item["allowed"]
    if item["cause"] == "outage" and "retry" in allowed:
        if answering:
            return "the warehouse is answering again, so suggest retry"
        return "the warehouse is not answering yet, so suggest retry once it answers"
    if item["cause"] in ("soldout", "recount") and order:
        enough = covered(order, stock)
        if not enough and "cancel" in allowed:
            return "the warehouse cannot cover this order, so suggest cancel"
        if enough:
            pick = "retry" if "retry" in allowed else "dismiss"
            return f"the warehouse covers this order again, so suggest {pick}"
    options = [action for action in ("retry", "cancel") if action in allowed]
    if order is None or not options:
        return "nothing is left to do for this order, so suggest dismiss"
    return f"the order is still {order['status']}, so suggest {' or '.join(options)}, not dismiss"


def choices(item: dict, order: dict | None) -> str:
    channel = CHANNELS[order["channel"]] if order else "its channel"
    what = {
        "retry": "sends the order to the Bucharest warehouse again",
        "cancel": f"cancels the order on the customer's channel ({channel})",
        "dismiss": "closes this item without changing anything",
    }
    if cancelling(item):
        what["retry"] = "asks the Bucharest warehouse again to cancel it"
    return "\n".join(f"- {action}: {what[action]}" for action in item["allowed"])
