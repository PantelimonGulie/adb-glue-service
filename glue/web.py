import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from glue import review, views
from glue.context import Context

SOON_PAGES = ("rules", "roles", "assistant")

log = logging.getLogger(__name__)
router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


def ctx_of(request: Request) -> Context:
    return request.app.state.ctx


def page(request: Request, name: str, context: dict) -> HTMLResponse:
    context["open_reviews"] = len(ctx_of(request).db.list_review())
    return templates.TemplateResponse(request, name, context)


def fragment(request: Request, name: str, context: dict) -> HTMLResponse:
    return templates.TemplateResponse(request, name, context)


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


@router.post("/review/{item_id}/{action}")
async def decide(request: Request, item_id: int, action: str):
    ctx = ctx_of(request)
    error = None
    try:
        await review.decide(ctx, item_id, action)
    except Exception as exc:
        # The operator needs to see why; review.decide has already re-queued the order.
        log.warning("review %s %s failed: %s", item_id, action, exc)
        error = str(exc)
    item = ctx.db.get_review(item_id)
    if item is None:
        raise HTTPException(404, f"review item {item_id} not found")
    context = {"item": item, "order": ctx.db.get_order(item["order_id"]), "error": error}
    return fragment(request, "_review_card.html", context)


@router.get("/audit")
async def audit(request: Request, entity: str = ""):
    return page(request, "audit.html", views.audit(ctx_of(request), entity.strip()))


@router.get("/audit/tail")
async def audit_tail(request: Request, entity: str = ""):
    return fragment(request, "_audit_rows.html", views.audit(ctx_of(request), entity.strip()))


@router.get("/soon/{name}")
async def soon(request: Request, name: str):
    if name not in SOON_PAGES:
        raise HTTPException(404, "no such page")
    return page(request, "soon.html", {"active": name})


@router.get("/metrics")
async def metrics(request: Request) -> dict:
    return views.metrics(ctx_of(request))
