import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Form, HTTPException, Request

from glue import assistant, auth, reconciler, rules, triage, views
from glue.web import ctx_of, fragment, from_dashboard, page

SKU_OR_BLANK = r"^([A-Z0-9-]{1,32})?$"

log = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(auth.require("view"))])
actions = APIRouter(dependencies=[Depends(from_dashboard)])


@router.get("/rules")
async def rules_page(request: Request):
    return page(request, "rules.html", {"rules": rules.all_rules(ctx_of(request))})


@actions.post("/rules/{name}")
async def save_rule(
    request: Request,
    name: Literal["stock-buffer", "auto-retry"],
    user: Annotated[auth.User, Depends(auth.require("rules"))],
    enabled: Annotated[bool, Form()] = False,
    channel: Annotated[Literal["shop", "emag"], Form()] = "emag",
    units: Annotated[int, Form(ge=0, le=99)] = 1,
    sku: Annotated[str, Form(pattern=SKU_OR_BLANK)] = "",
):
    ctx = ctx_of(request)
    config = {"channel": channel, "units": units, "sku": sku} if name == "stock-buffer" else {}
    rules.save(ctx, name, enabled, config, user.name)
    if name == "stock-buffer":
        # The channels should show the new figure now, not at the next periodic run.
        await reconciler.reconcile_all(ctx)
    return fragment(request, "_rules.html", {"rules": rules.all_rules(ctx)})


@router.get("/roles")
async def roles_page(request: Request):
    return page(request, "roles.html", {"roles": auth.ROLES})


@actions.post("/triage/{item_id}", dependencies=[Depends(auth.require("ask"))])
async def triage_item(request: Request, item_id: int):
    ctx = ctx_of(request)
    if ctx.db.get_review(item_id) is None:
        raise HTTPException(404, f"review item {item_id} not found")
    if ctx.assistant is None:
        raise HTTPException(409, "assistant offline")
    error = None
    try:
        await triage.suggest(ctx, item_id)
    except Exception as exc:
        log.warning("triage %s failed: %s: %s", item_id, type(exc).__name__, exc)
        error = assistant.failure_message(exc)
    card = views.review_card(ctx, item_id, error)
    return fragment(request, "_review_card.html", {"card": card})
