import asyncio
from contextlib import asynccontextmanager

import httpx
from fastapi import APIRouter, FastAPI, Request

from glue import inbox
from glue.audit import configure_logging
from glue.clients import EmagClient, ShopClient, WarehouseClient
from glue.context import Context
from glue.db import Database
from glue.settings import Settings
from glue.worker import run_forever

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@router.get("/debug/orders")
async def debug_orders(request: Request) -> list[dict]:
    return request.app.state.ctx.db.list_orders()


@router.get("/debug/audit")
async def debug_audit(request: Request, entity: str | None = None) -> list[dict]:
    db = request.app.state.ctx.db
    return db.audit_for(entity) if entity else db.audit_tail()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings: Settings = app.state.settings
    db = Database(settings.db_path)
    async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as http:
        app.state.http = http
        app.state.ctx = Context(
            settings=settings,
            db=db,
            http=http,
            shop=ShopClient(http, settings.shop_url),
            emag=EmagClient(http, settings.emag_url),
            warehouse=WarehouseClient(http, settings.warehouse_url),
        )
        worker = asyncio.create_task(run_forever(app.state.ctx))
        yield
        worker.cancel()
    db.close()


def create_app(settings: Settings | None = None) -> FastAPI:
    configure_logging()
    app = FastAPI(title="Glue", lifespan=lifespan)
    app.state.settings = settings or Settings.from_env()
    app.include_router(inbox.router)
    app.include_router(router)
    return app


app = create_app()
