import json
import uuid
from dataclasses import dataclass
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI

import emag.main
import glue.main
import shop.main
import warehouse.main
from common import signing
from glue import reconciler, retry, worker
from glue.context import Context
from glue.settings import Settings

SECRETS = {"shop": "test-shop", "emag": "test-emag", "warehouse": "test-warehouse"}


@dataclass
class Systems:
    shop: FastAPI
    emag: FastAPI
    warehouse: FastAPI
    ctx: Context
    http: httpx.AsyncClient

    async def buy_on_shop(self, sku: str, qty: int = 1) -> str:
        response = await self.http.post("http://shop/orders", data={"sku": sku, "qty": qty})
        assert response.status_code == 303
        return list(self.shop.state.orders)[-1]

    async def buy_on_emag(self, sku: str, qty: int = 1) -> str:
        response = await self.http.post("http://emag/buy", data={"sku": sku, "qty": qty})
        assert response.status_code == 303
        return f"emag-{list(self.emag.state.orders)[-1]}"

    def emag_order(self, order_id: str) -> dict:
        return self.emag.state.orders[int(order_id.removeprefix("emag-"))]

    async def recount(self, sku: str, on_hand: int) -> None:
        response = await self.http.post(
            f"http://warehouse/stock/{sku}/recount", data={"on_hand": on_hand}
        )
        assert response.status_code == 303

    async def chaos(self, system: str, **faults: object) -> None:
        response = await self.http.post(f"http://{system}/chaos", json=faults)
        response.raise_for_status()

    async def run_worker(self) -> None:
        while await worker.process_pending(self.ctx):
            pass

    async def reconcile(self) -> None:
        await reconciler.reconcile_all(self.ctx)

    async def send_event(
        self, source: str, event_type: str, data: dict, secret: str | None = None
    ) -> httpx.Response:
        body = json.dumps({"type": event_type, "data": data}).encode()
        headers = {
            "x-adobe-event-id": str(uuid.uuid4()),
            "x-source": source,
            **signing.headers(secret or SECRETS[source], body),
        }
        return await self.http.post("http://glue/events", content=body, headers=headers)

    async def decide(self, item_id: int, action: str) -> httpx.Response:
        return await self.http.post(
            f"http://glue/review/{item_id}/{action}", headers={"HX-Request": "true"}
        )

    def open_reviews(self) -> list[dict]:
        return self.ctx.db.list_review()


@pytest.fixture
async def systems(tmp_path, monkeypatch):
    monkeypatch.setenv("GLUE_URL", "http://glue")
    for source, secret in SECRETS.items():
        monkeypatch.setenv(f"{source.upper()}_WEBHOOK_SECRET", secret)
    settings = Settings(
        shop_url="http://shop",
        emag_url="http://emag",
        warehouse_url="http://warehouse",
        shop_webhook_secret=SECRETS["shop"],
        emag_webhook_secret=SECRETS["emag"],
        warehouse_webhook_secret=SECRETS["warehouse"],
        db_path=str(tmp_path / "glue.db"),
        retry_base_seconds=0,
    )
    apps = {
        "shop": shop.main.create_app(),
        "emag": emag.main.create_app(),
        "warehouse": warehouse.main.create_app(),
        "glue": glue.main.create_app(settings),
    }
    mounts = {f"all://{name}": httpx.ASGITransport(app) for name, app in apps.items()}
    async with httpx.AsyncClient(mounts=mounts) as http:
        for name in ("shop", "emag", "warehouse"):
            apps[name].state.http = http
        # Built here instead of in the lifespan so the worker and reconcile loops never start:
        # each test drives them one step at a time.
        ctx = glue.main.build_context(settings, http)
        apps["glue"].state.ctx = ctx
        await reconciler.reconcile_all(ctx)
        yield Systems(apps["shop"], apps["emag"], apps["warehouse"], ctx, http)
        ctx.db.close()


@pytest.fixture
def sleeps(monkeypatch) -> list[float]:
    # The mocks send Retry-After of 1 or 2 s; recording the delays keeps the suite fast.
    delays: list[float] = []

    async def sleep(seconds: float) -> None:
        delays.append(seconds)

    monkeypatch.setattr(retry, "asyncio", SimpleNamespace(sleep=sleep))
    return delays
