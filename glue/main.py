import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import APIRouter, FastAPI, Request

from glue import api, assistant, inbox, reconciler, views, worker
from glue.audit import configure_logging
from glue.clients import EmagClient, ShopClient, WarehouseClient
from glue.context import Context
from glue.db import Database
from glue.settings import Settings
from glue.spa import mount_spa

DIST = Path(__file__).parents[1] / "frontend" / "dist"
router = APIRouter()


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@router.get("/metrics")
async def metrics(request: Request) -> dict:
    return views.metrics(request.app.state.ctx)


def build_context(settings: Settings, http: httpx.AsyncClient) -> Context:
    return Context(
        settings=settings,
        db=Database(settings.db_path),
        http=http,
        shop=ShopClient(http, settings.shop_url),
        emag=EmagClient(http, settings.emag_url),
        warehouse=WarehouseClient(http, settings.warehouse_url),
        assistant=assistant.client(settings, http),
        worker_slots=asyncio.Semaphore(settings.worker_concurrency),
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings: Settings = app.state.settings
    async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as http:
        app.state.http = http
        app.state.ctx = build_context(settings, http)
        # Channels start at zero stock; fill them before any order can be processed.
        await reconciler.reconcile_all(app.state.ctx)
        tasks = [
            asyncio.create_task(worker.run_forever(app.state.ctx)),
            asyncio.create_task(reconciler.run_forever(app.state.ctx)),
        ]
        yield
        for task in tasks:
            task.cancel()
        app.state.ctx.db.close()


def create_app(settings: Settings | None = None) -> FastAPI:
    configure_logging()
    app = FastAPI(title="Glue", lifespan=lifespan)
    app.state.settings = settings or Settings.from_env()
    app.include_router(inbox.router)
    app.include_router(api.router)
    app.include_router(router)
    mount_spa(app, DIST)
    return app


app = create_app()
