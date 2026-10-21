from typing import Annotated, Literal

from fastapi import APIRouter, Header, Request
from pydantic import BaseModel

from common.models import Event
from glue.audit import record
from glue.context import Context

router = APIRouter()


class EmagNotification(BaseModel):
    order_id: int
    type: Literal["new", "cancelled"]


def accept(ctx: Context, event_id: str, source: str, event_type: str, payload: dict) -> None:
    if ctx.db.insert_event_if_new(event_id, source, event_type, payload):
        action = "event_received"
    else:
        action = "duplicate_dropped"
    record(ctx.db, event_id, "event", event_id, action, source=source, type=event_type)


@router.post("/events", status_code=202)
async def events(
    request: Request,
    event: Event,
    x_adobe_event_id: Annotated[str, Header()],
    x_source: Annotated[str, Header()] = "unknown",
) -> dict:
    accept(request.app.state.ctx, x_adobe_event_id, x_source, event.type, event.data)
    return {"accepted": x_adobe_event_id}


@router.post("/emag/notifications", status_code=202)
async def emag_notifications(request: Request, notification: EmagNotification) -> dict:
    event_id = f"emag-notify-{notification.order_id}-{notification.type}"
    accept(request.app.state.ctx, event_id, "emag", "emag.notification", notification.model_dump())
    return {"accepted": event_id}
