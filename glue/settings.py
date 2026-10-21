import os
from dataclasses import dataclass, fields
from typing import Self


@dataclass(frozen=True)
class Settings:
    shop_url: str = "http://shop:8001"
    emag_url: str = "http://emag:8002"
    warehouse_url: str = "http://warehouse:8003"
    shop_webhook_secret: str = ""
    emag_webhook_secret: str = ""
    warehouse_webhook_secret: str = ""
    db_path: str = "/data/glue.db"
    http_timeout_seconds: float = 2
    retry_attempts: int = 5
    retry_base_seconds: float = 0.5
    worker_concurrency: int = 10
    reconcile_interval_seconds: float = 10
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.8-flash"
    session_secret: str = ""
    viewer_password: str = ""
    operator_password: str = ""
    admin_password: str = ""

    def webhook_secret(self, source: str) -> str:
        secrets = {
            "shop": self.shop_webhook_secret,
            "emag": self.emag_webhook_secret,
            "warehouse": self.warehouse_webhook_secret,
        }
        return secrets.get(source, "")

    def password(self, username: str) -> str:
        passwords = {
            "viewer": self.viewer_password,
            "operator": self.operator_password,
            "admin": self.admin_password,
        }
        return passwords.get(username, "")

    @classmethod
    def from_env(cls) -> Self:
        values = {}
        for field in fields(cls):
            raw = os.environ.get(field.name.upper())
            if raw is not None:
                values[field.name] = field.type(raw)
        return cls(**values)
