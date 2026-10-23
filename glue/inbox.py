import re
from typing import Annotated, Literal

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field, ValidationError

from common import signing
from common.models import EmagNotification, Event, Order, OrderLine, OrderRef, StockAdjusted
from glue.audit import record
from glue.context import Context

router = APIRouter()
EVENT_ID = re.compile(r"^[A-Za-z0-9-]{1,64}$")


# The shop's signature only vouches for shop orders. eMAG orders enter through
# /emag/notifications alone; the warehouse ships orders from either channel.
class ShopOrder(Order):
    channel: Literal["shop"]
    lines: list[OrderLine] = Field(min_length=1)


class ShopOrderRef(BaseModel):
    order_id: str = Field(pattern=r"^shop-\d+$")


# Which event types each signed source may post to /events. eMAG has its own endpoint.
SOURCES = {
    "shop": {"order.placed": ShopOrder, "order.cancelled": ShopOrderRef},
    "warehouse": {"order.shipped": OrderRef, "stock.adjusted": StockAdjusted},
    "emag": {},
}


async def verified_body(request: Request, source: str, event_id: str | None = None) -> bytes:
    ctx: Context = request.app.state.ctx
    body = await request.body()
    signed = body if event_id is None else signing.event_message(event_id, body)
    secret = ctx.settings.webhook_secret(source)
    if not signing.verify(secret, signed, request.headers.get(signing.HEADER)):
        known = source if source in SOURCES else "unknown"
        record(ctx.db, "-", "webhook", known, "signature_rejected", path=request.url.path)
        raise HTTPException(401, "missing or invalid signature")
    return body


def rejected(ctx: Context, event_id: str, source: str, error: str) -> HTTPException:
    record(ctx.db, event_id, "event", event_id, "event_rejected", source=source, error=error)
    return HTTPException(422, error)


def first_error(exc: ValidationError) -> str:
    error = exc.errors()[0]
    where = ".".join(str(part) for part in error["loc"])
    return f"{where}: {error['msg']}" if where else error["msg"]


def accept(ctx: Context, event_id: str, source: str, event_type: str, payload: dict) -> None:
    about = {}
    order_id = payload.get("id") or payload.get("order_id")
    if order_id is not None:
        about["order_id"] = f"emag-{order_id}" if source == "emag" else order_id
    if event_type == "stock.adjusted":
        about |= {"sku": payload["sku"], "on_hand": payload["on_hand"]}
        if payload["note"]:
            about["note"] = payload["note"]
    # The event and its audit row land together before the 202, or neither does and the
    # sender, with no answer, sends it again.
    with ctx.db.transaction():
        if ctx.db.insert_event_if_new(event_id, source, event_type, payload):
            action = "event_received"
        else:
            action = "duplicate_dropped"
        record(ctx.db, event_id, "event", event_id, action, source=source, type=event_type, **about)


@router.post("/events", status_code=202)
async def events(
    request: Request,
    x_adobe_event_id: Annotated[str, Header()] = "",
    x_source: Annotated[str, Header()] = "",
) -> dict:
    ctx: Context = request.app.state.ctx
    body = await verified_body(request, x_source, x_adobe_event_id)
    if not EVENT_ID.match(x_adobe_event_id):
        raise rejected(ctx, "-", x_source, "x-adobe-event-id: missing or malformed")
    try:
        event = Event.model_validate_json(body)
        model = SOURCES[x_source].get(event.type)
        if model is None:
            raise rejected(ctx, x_adobe_event_id, x_source, f"type: unknown {event.type!r}")
        data = model.model_validate(event.data)
    except ValidationError as exc:
        raise rejected(ctx, x_adobe_event_id, x_source, first_error(exc)) from None
    accept(ctx, x_adobe_event_id, x_source, event.type, data.model_dump())
    return {"accepted": x_adobe_event_id}


@router.post("/emag/notifications", status_code=202)
async def emag_notifications(request: Request) -> dict:
    ctx: Context = request.app.state.ctx
    # No event id to sign: Glue builds it from the order id and type in the signed body.
    body = await verified_body(request, "emag")
    try:
        notification = EmagNotification.model_validate_json(body)
    except ValidationError as exc:
        raise rejected(ctx, "-", "emag", first_error(exc)) from None
    event_id = f"emag-notify-{notification.order_id}-{notification.type}"
    accept(ctx, event_id, "emag", "emag.notification", notification.model_dump())
    return {"accepted": event_id}
