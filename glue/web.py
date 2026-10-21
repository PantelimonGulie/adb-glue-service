import logging
from pathlib import Path
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from glue import assistant, auth, review, views
from glue.context import Context

log = logging.getLogger(__name__)
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


def from_dashboard(request: Request) -> None:
    # HTMX adds HX-Request to its own calls; a cross-site form or script cannot.
    origin = request.headers.get("origin")
    if request.headers.get("hx-request") != "true" or (
        origin and urlsplit(origin).netloc != request.url.netloc
    ):
        raise HTTPException(403, "only the dashboard may do this")


router = APIRouter(dependencies=[Depends(auth.require("view"))])
actions = APIRouter(dependencies=[Depends(from_dashboard)])
public = APIRouter()


def ctx_of(request: Request) -> Context:
    return request.app.state.ctx


def fragment(request: Request, name: str, context: dict, status_code: int = 200) -> HTMLResponse:
    context["user"] = request.state.user
    return templates.TemplateResponse(request, name, context, status_code=status_code)


def page(request: Request, name: str, context: dict) -> HTMLResponse:
    context["open_reviews"] = len(ctx_of(request).db.list_review())
    return fragment(request, name, context)


@router.get("/")
async def overview(request: Request):
    return page(request, "overview.html", await views.overview(ctx_of(request), request))


@router.get("/overview/live")
async def overview_live(request: Request):
    return fragment(request, "_overview.html", await views.overview(ctx_of(request), request))


@router.get("/orders")
async def orders(request: Request):
    return page(request, "orders.html", {"orders": ctx_of(request).db.list_orders()})


@router.get("/orders/rows")
async def order_rows(request: Request):
    return fragment(request, "_order_rows.html", {"orders": ctx_of(request).db.list_orders()})


@router.get("/orders/{order_id}")
async def order_detail(request: Request, order_id: str):
    db = ctx_of(request).db
    order = db.get_order(order_id)
    if order is None:
        raise HTTPException(404, f"order {order_id} not found")
    return page(request, "order.html", {"order": order, "timeline": db.timeline(order_id)})


@router.get("/stock")
async def stock(request: Request):
    return page(request, "stock.html", views.stock(ctx_of(request)))


@router.get("/stock/rows")
async def stock_rows(request: Request):
    return fragment(request, "_stock_rows.html", views.stock(ctx_of(request)))


@router.get("/review")
async def review_queue(request: Request):
    return page(request, "review.html", views.review(ctx_of(request)))


@router.get("/review/items")
async def review_items(request: Request):
    return fragment(request, "_review_items.html", views.review(ctx_of(request)))


@router.get("/review/count")
async def review_count(request: Request) -> HTMLResponse:
    count = len(ctx_of(request).db.list_review())
    return HTMLResponse(str(count) if count else "")


@actions.post("/review/{item_id}/{action}")
async def decide(
    request: Request,
    item_id: int,
    action: str,
    user: Annotated[auth.User, Depends(auth.require("decide"))],
):
    ctx = ctx_of(request)
    status, error = 200, None
    try:
        await review.decide(ctx, item_id, action, user.name)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from None
    except review.Conflict as exc:
        status, error = 409, str(exc)
    except Exception as exc:
        # The operator needs to see why; review.decide has already re-queued the order.
        log.warning("review %s %s failed: %s", item_id, action, exc)
        error = str(exc)
    card = views.review_card(ctx, item_id, error)
    return fragment(request, "_review_card.html", {"card": card}, status)


@router.get("/audit")
async def audit(request: Request, entity: str = ""):
    return page(request, "audit.html", views.audit(ctx_of(request), entity.strip()))


@router.get("/audit/tail")
async def audit_tail(request: Request, entity: str = ""):
    return fragment(request, "_audit_rows.html", views.audit(ctx_of(request), entity.strip()))


@router.get("/assistant")
async def assistant_page(request: Request):
    offline = ctx_of(request).assistant is None
    return page(request, "assistant.html", {"offline": offline, "turns": []})


@actions.post("/assistant", dependencies=[Depends(auth.require("ask"))])
async def assistant_ask(request: Request, question: str = Form(""), history: str = Form("[]")):
    ctx = ctx_of(request)
    turns = assistant.parse_history(history)
    question = question.strip()[:1000]
    if ctx.assistant is not None and question:
        turns.append({"role": "user", "content": question})
        try:
            turns.append({"role": "assistant", "content": await assistant.ask(ctx, turns)})
        except Exception as exc:
            log.warning("assistant failed: %s: %s", type(exc).__name__, exc)
            answer = assistant.failure_message(exc)
            turns.append({"role": "assistant", "content": answer, "error": True})
    context = {"offline": ctx.assistant is None, "turns": turns}
    return fragment(request, "_assistant_chat.html", context)


@public.get("/metrics")
async def metrics(request: Request) -> dict:
    return views.metrics(ctx_of(request))
