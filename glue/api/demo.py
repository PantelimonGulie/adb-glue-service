import asyncio
from dataclasses import replace

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from common.models import SKU
from glue import auth, sample, traffic
from glue.context import Context

router = APIRouter()
can_demo = [Depends(auth.require("demo"))]

ALL_FAULTS_OFF = [
    ("emag", {"rate_limit": False, "reject_sku": None, "freeze_stock": False, "down": False}),
    ("warehouse", {"down": False, "slow_seconds": 0, "fail_next": 0}),
]

ACTIONS: dict[str, tuple[str, list[tuple[str, dict]]]] = {
    "shop-duplicate": (
        "Electronic Market re-sent its last event with the same event id.",
        [("shop", {"duplicate_last": True})],
    ),
    "shop-flash-sale": (
        "Electronic Market placed 10 orders at once.",
        [("shop", {"flash_sale": 10})],
    ),
    "emag-freeze-on": (
        "eMAG now ignores stock updates and keeps showing its old numbers.",
        [("emag", {"freeze_stock": True})],
    ),
    "emag-freeze-off": ("eMAG accepts stock updates again.", [("emag", {"freeze_stock": False})]),
    "emag-rate-limit-on": (
        "eMAG answers every API call with 429 and Retry-After: 1.",
        [("emag", {"rate_limit": True})],
    ),
    "emag-rate-limit-off": ("eMAG stopped rate limiting.", [("emag", {"rate_limit": False})]),
    "emag-reject-on": (
        "eMAG rejects stock updates for MBA-M4 and accepts the rest.",
        [("emag", {"reject_sku": "MBA-M4"})],
    ),
    "emag-reject-off": ("eMAG accepts MBA-M4 again.", [("emag", {"reject_sku": None})]),
    "emag-renotify": (
        "eMAG re-sent the notification for every order not yet acknowledged.",
        [("emag", {"renotify_now": True})],
    ),
    "warehouse-down": ("The warehouse answers 503 to every call.", [("warehouse", {"down": True})]),
    "warehouse-up": ("The warehouse is answering again.", [("warehouse", {"down": False})]),
    "warehouse-slow-on": (
        "The warehouse waits 3 s before answering. Calls time out after 2 s.",
        [("warehouse", {"slow_seconds": 3})],
    ),
    "warehouse-slow-off": (
        "The warehouse answers at full speed.",
        [("warehouse", {"slow_seconds": 0})],
    ),
    "warehouse-fail-2": (
        "The next 2 order placements at the warehouse fail with 503.",
        [("warehouse", {"fail_next": 2})],
    ),
    "reset": ("All faults are off.", ALL_FAULTS_OFF),
}
TRAFFIC = {
    "traffic-start": {"running": True},
    "traffic-stop": {"running": False},
    "speed-slow": {"speed": "slow"},
    "speed-normal": {"speed": "normal"},
    "speed-fast": {"speed": "fast"},
}
OUTSIDE = {"ship-oldest": traffic.ship_oldest, "customer-cancel": traffic.customer_cancel}


class Recount(BaseModel):
    sku: str = Field(pattern=SKU)
    on_hand: int = Field(ge=0, le=100_000)


def pace(ctx: Context) -> str:
    seconds = traffic.INTERVALS[ctx.traffic.speed]
    if ctx.traffic.running:
        return f"New orders arrive every {seconds:g} seconds."
    return f"New orders are paused. Once resumed they arrive every {seconds:g} seconds."


async def faults_of(ctx: Context, system: str) -> dict | None:
    try:
        response = await ctx.http.get(f"{ctx.settings.channel_urls()[system]}/chaos")
        response.raise_for_status()
    except httpx.HTTPError:
        return None
    return response.json()


@router.get("/demo", dependencies=[Depends(auth.require("view"))])
async def state(request: Request) -> dict:
    ctx = request.app.state.ctx
    emag, warehouse = await asyncio.gather(faults_of(ctx, "emag"), faults_of(ctx, "warehouse"))
    return {
        "traffic": {"running": ctx.traffic.running, "speed": ctx.traffic.speed},
        "faults": {"emag": emag, "warehouse": warehouse},
        "sample_history": ctx.db.has_sample(),
    }


@router.post("/demo/recount", dependencies=can_demo)
async def recount(request: Request, body: Recount) -> dict:
    ok, message = await traffic.recount(request.app.state.ctx, body.sku, body.on_hand)
    return {"ok": ok, "message": message}


@router.post("/demo/fake-signature", dependencies=can_demo)
async def fake_signature(request: Request) -> dict:
    # Through the app itself, so the message takes the same path as a real webhook.
    transport = httpx.ASGITransport(app=request.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://glue") as client:
        body = {"type": "order.placed", "data": {}}
        response = await client.post("/events", json=body, headers={"x-source": "shop"})
    if response.status_code == 401:
        return {"ok": True, "message": "Glue refused an unsigned message (HTTP 401) and logged it."}
    message = f"Glue did not refuse the unsigned message: HTTP {response.status_code}."
    return {"ok": False, "message": message}


@router.post("/demo/{action}", dependencies=can_demo)
async def run(request: Request, action: str) -> dict:
    ctx = request.app.state.ctx
    if action in TRAFFIC:
        ctx.traffic = replace(ctx.traffic, **TRAFFIC[action])
        return {"ok": True, "message": pace(ctx)}
    if action in OUTSIDE:
        ok, message = await OUTSIDE[action](ctx)
        return {"ok": ok, "message": message}
    if action == "history-load":
        message = f"Loaded sample history for the last 30 days: {sample.load(ctx):,} orders."
        return {"ok": True, "message": message}
    if action == "history-clear":
        message = f"Removed the sample history ({sample.clear(ctx):,} orders). Real orders stay."
        return {"ok": True, "message": message}
    if action not in ACTIONS:
        raise HTTPException(404, f"unknown demo action {action!r}")
    message, calls = ACTIONS[action]
    urls = ctx.settings.channel_urls()
    for system, body in calls:
        try:
            # Flash sale and re-notify make the mock call back into this service first.
            response = await ctx.http.post(f"{urls[system]}/chaos", json=body, timeout=10)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            return {"ok": False, "message": f"The {system} mock did not take the change: {exc}"}
    return {"ok": True, "message": message}
