import httpx
from fastapi import APIRouter, Depends, HTTPException, Request

from glue import auth
from glue.web import fragment, from_dashboard

router = APIRouter(dependencies=[Depends(from_dashboard), Depends(auth.require("demo"))])

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
        "The next 2 warehouse calls fail with 503.",
        [("warehouse", {"fail_next": 2})],
    ),
    "reset": ("All faults are off.", ALL_FAULTS_OFF),
}


@router.post("/demo/{action}")
async def run(request: Request, action: str):
    if action not in ACTIONS:
        raise HTTPException(404, f"unknown demo action {action!r}")
    message, calls = ACTIONS[action]
    ctx = request.app.state.ctx
    urls = {
        "shop": ctx.settings.shop_url,
        "emag": ctx.settings.emag_url,
        "warehouse": ctx.settings.warehouse_url,
    }
    for system, body in calls:
        try:
            # Flash sale and re-notify make the mock call back into this service first.
            response = await ctx.http.post(f"{urls[system]}/chaos", json=body, timeout=10)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            context = {"ok": False, "message": f"The {system} mock did not take the change: {exc}"}
            return fragment(request, "_demo_result.html", context)
    return fragment(request, "_demo_result.html", {"ok": True, "message": message})
