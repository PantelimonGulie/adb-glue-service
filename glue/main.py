import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import APIRouter, FastAPI, Request

from glue import api, inbox, llm, queries, reconciler, settle, traffic, tuning, worker
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
    return queries.metrics(request.app.state.ctx)


def build_context(settings: Settings, http: httpx.AsyncClient) -> Context:
    db = Database(settings.db_path)
    ctx = Context(
        settings=settings,
        tuning=tuning.load(db, settings),
        db=db,
        http=http,
        shop=ShopClient(http, settings.shop_url),
        emag=EmagClient(http, settings.emag_url),
        warehouse=WarehouseClient(http, settings.warehouse_url),
        assistant=llm.client(settings, http),
        worker_slots=asyncio.Semaphore(settings.worker_concurrency),
        traffic=traffic.initial(settings.demo_traffic),
    )
    settle.interrupted_decisions(ctx)
    return ctx


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
            asyncio.create_task(llm.ensure_model(app.state.ctx)),
            asyncio.create_task(traffic.run_forever(app.state.ctx)),
        ]
        yield
        for task in tasks:
            task.cancel()
        # A loop stopped mid-step may still write while it unwinds.
        await asyncio.gather(*tasks, return_exceptions=True)
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
