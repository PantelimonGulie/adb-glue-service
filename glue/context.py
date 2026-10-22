import asyncio
import weakref
from dataclasses import dataclass, field

import httpx
from openai import AsyncOpenAI

from glue.clients import EmagClient, ShopClient, WarehouseClient
from glue.db import Database
from glue.settings import Settings
from glue.traffic import Traffic
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
    # One lock per order with events in flight; it goes away once no event holds it.
    order_locks: weakref.WeakValueDictionary[str, asyncio.Lock] = field(
        default_factory=weakref.WeakValueDictionary
    )
    sending: set[str] = field(default_factory=set)
    warehouse_down: bool = False
    traffic: Traffic = field(default_factory=Traffic)
    model_status: str = "offline"
    model_progress: float = 0.0
