from dataclasses import dataclass

import httpx

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
