import json
import uuid
from collections.abc import Sequence
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


class Ollama:
    # Answers like Ollama: /api/tags lists `models`, and a pull adds the model in two steps.
    def __init__(self, models: list[str]):
        self.models = models
        self.up = True
        self.total: object = 4

    def handle(self, request: httpx.Request) -> httpx.Response:
        if not self.up:
            raise httpx.ConnectError("ollama is down", request=request)
        if request.url.path == "/api/pull":
            self.models.append(json.loads(request.content)["model"])
            steps = [{"digest": "d1", "total": self.total, "completed": n} for n in (1, 4)]
            lines = [*steps, {"status": "success"}]
            return httpx.Response(200, text="\n".join(json.dumps(line) for line in lines))
        return httpx.Response(200, json={"models": [{"name": name} for name in self.models]})


class StubModel:
    # Stands in for AsyncOpenAI: makes each tool call in `calls`, one per round, then answers.
    def __init__(self, answer: str, calls: Sequence[tuple[str, dict]], tokens: int):
        self.answer = answer
        self.calls = calls
        self.tokens = tokens
        self.requests: list[dict] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    async def create(self, **request: object) -> SimpleNamespace:
        self.requests.append(request)
        message = SimpleNamespace(content=self.answer, tool_calls=None)
        if len(self.requests) <= len(self.calls):
            name, arguments = self.calls[len(self.requests) - 1]
            function = SimpleNamespace(name=name, arguments=json.dumps(arguments))
            call = SimpleNamespace(id=f"call-{len(self.requests)}", function=function)
            message = SimpleNamespace(content=None, tool_calls=[call])
        usage = SimpleNamespace(total_tokens=self.tokens)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=usage)


@dataclass
class Systems:
    shop: FastAPI
    emag: FastAPI
    warehouse: FastAPI
    ctx: Context
    http: httpx.AsyncClient
    ollama: Ollama

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

    async def sign_in(self, username: str, password: str | None = None) -> httpx.Response:
        return await self.act("/api/session", username=username, password=password or username)

    async def act(self, path: str, **body: object) -> httpx.Response:
        return await self.http.post(
            f"http://glue{path}", json=body, headers={"X-Glue-Request": "1"}
        )

    async def put(self, path: str, **body: object) -> httpx.Response:
        return await self.http.put(f"http://glue{path}", json=body, headers={"X-Glue-Request": "1"})

    async def decide(self, item_id: int, action: str) -> httpx.Response:
        return await self.act(f"/api/review/{item_id}/{action}")

    def open_reviews(self) -> list[dict]:
        return self.ctx.db.list_review()

    def use_model(
        self, answer: str, calls: Sequence[tuple[str, dict]] = (), tokens: int = 60
    ) -> StubModel:
        model = StubModel(answer, calls, tokens)
        self.ctx.assistant = model
        return model


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
        session_secret="test-session",
        viewer_password="viewer",
        operator_password="operator",
        admin_password="admin",
    )
    apps = {
        "shop": shop.main.create_app(),
        "emag": emag.main.create_app(),
        "warehouse": warehouse.main.create_app(),
        "glue": glue.main.create_app(settings),
    }
    ollama = Ollama([settings.llm_model])
    mounts = {f"all://{name}": httpx.ASGITransport(app) for name, app in apps.items()}
    mounts["all://ollama"] = httpx.MockTransport(ollama.handle)
    async with httpx.AsyncClient(mounts=mounts) as http:
        for name in ("shop", "emag", "warehouse"):
            apps[name].state.http = http
        # Built here instead of in the lifespan so the worker and reconcile loops never start:
        # each test drives them one step at a time.
        ctx = glue.main.build_context(settings, http)
        apps["glue"].state.ctx = ctx
        await reconciler.reconcile_all(ctx)
        systems = Systems(apps["shop"], apps["emag"], apps["warehouse"], ctx, http, ollama)
        # Most tests act as the operator; role tests sign in again as someone else.
        await systems.sign_in("operator")
        yield systems
        ctx.db.close()


@pytest.fixture
def sleeps(monkeypatch) -> list[float]:
    # The mocks send Retry-After of 1 or 2 s; recording the delays keeps the suite fast.
    delays: list[float] = []

    async def sleep(seconds: float) -> None:
        delays.append(seconds)

    monkeypatch.setattr(retry, "asyncio", SimpleNamespace(sleep=sleep))
    return delays
