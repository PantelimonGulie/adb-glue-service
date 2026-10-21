import asyncio
from contextlib import asynccontextmanager

import httpx
from fastapi import APIRouter, FastAPI

from common import ui
from glue import assistant, auth, demo, extras, inbox, reconciler, web, worker
from glue.audit import configure_logging
from glue.clients import EmagClient, ShopClient, WarehouseClient
from glue.context import Context
from glue.db import Database
from glue.settings import Settings

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


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
    app.mount("/static", ui.static, name="static")
    app.include_router(inbox.router)
    app.include_router(auth.router)
    app.include_router(web.router)
    app.include_router(web.actions)
    app.include_router(web.public)
    app.include_router(extras.router)
    app.include_router(extras.actions)
    app.include_router(demo.router)
    app.include_router(router)
    return app


app = create_app()
