import asyncio
from dataclasses import dataclass, field

import httpx
from openai import AsyncOpenAI

from glue.clients import EmagClient, ShopClient, WarehouseClient
from glue.db import Database
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
    # Reconcile runs read-then-push; serialising them keeps a slower run from
    # overwriting a newer stock figure on the channels.
    reconcile_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    worker_slots: asyncio.Semaphore = field(default_factory=lambda: asyncio.Semaphore(10))
    sending: set[str] = field(default_factory=set)
    warehouse_down: bool = False
    assistant: AsyncOpenAI | None = None
