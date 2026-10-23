import asyncio
import weakref
from contextlib import nullcontext
from dataclasses import dataclass, field

import httpx
from openai import AsyncOpenAI

from glue.clients import EmagClient, ShopClient, WarehouseClient
from glue.db import Database
from glue.demo.traffic import Traffic
from glue.settings import Settings
from glue.tuning import Tuning


@dataclass
class Context:
    settings: Settings
    tuning: Tuning
    db: Database
    http: httpx.AsyncClient
    shop: ShopClient
    emag: EmagClient
    warehouse: WarehouseClient
    assistant: AsyncOpenAI
    # Reconcile runs read-then-push; serialising them keeps a slower run from
    # overwriting a newer stock figure on the channels.
    reconcile_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    worker_slots: asyncio.Semaphore = field(default_factory=lambda: asyncio.Semaphore(10))
    # One lock per order being worked on; it goes away once nothing holds it.
    order_locks: weakref.WeakValueDictionary[str, asyncio.Lock] = field(
        default_factory=weakref.WeakValueDictionary
    )
    warehouse_down: bool = False
    last_reconcile_ok_at: str | None = None
    traffic: Traffic = field(default_factory=Traffic)
    model_status: str = "offline"
    model_progress: float = 0.0

    def order_lock(self, order_id: str | None) -> asyncio.Lock | nullcontext:
        # Events and review decisions for one order run one at a time, so two of them never
        # act on the same state.
        if order_id is None:
            return nullcontext()
        return self.order_locks.setdefault(order_id, asyncio.Lock())
