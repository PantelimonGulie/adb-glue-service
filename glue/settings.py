import os
from dataclasses import dataclass, fields
from typing import Self


@dataclass(frozen=True)
class Settings:
    shop_url: str = "http://shop:8001"
    emag_url: str = "http://emag:8002"
    warehouse_url: str = "http://warehouse:8003"
    db_path: str = "/data/glue.db"
    http_timeout_seconds: float = 2
    retry_attempts: int = 5
    retry_base_seconds: float = 0.5
    worker_concurrency: int = 10
    reconcile_interval_seconds: float = 10
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.8-flash"

    @classmethod
    def from_env(cls) -> Self:
        values = {}
        for field in fields(cls):
            raw = os.environ.get(field.name.upper())
            if raw is not None:
                values[field.name] = field.type(raw)
        return cls(**values)
