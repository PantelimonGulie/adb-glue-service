import asyncio
from dataclasses import dataclass, field

import httpx
from openai import AsyncOpenAI

from glue.clients import EmagClient, ShopClient, WarehouseClient
from glue.db import Database
from glue.settings import Settings


@dataclass
class Context:
    settings: Settings
    db: Database
    http: httpx.AsyncClient
    shop: ShopClient
    emag: EmagClient
    warehouse: WarehouseClient
    # Reconcile runs read-then-push; serialising them keeps a slower run from
    # overwriting a newer stock figure on the channels.
    reconcile_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    warehouse_down: bool = False
    assistant: AsyncOpenAI | None = None
