import asyncio
from dataclasses import asdict
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field

from glue import auth, reconciler, rules, tuning, views
from glue.context import Context

SKU_OR_BLANK = r"^([A-Z0-9-]{1,32})?$"

router = APIRouter()
can_view = Depends(auth.require("view"))


def bounded(key: str) -> Any:
    low, high = tuning.LIMITS[key]
    return Field(None, ge=low, le=high)


class TuningChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    retry_attempts: int | None = bounded("retry_attempts")
    retry_base_seconds: float | None = bounded("retry_base_seconds")
    reconcile_interval_seconds: float | None = bounded("reconcile_interval_seconds")


class StockBuffer(BaseModel):
    channel: Literal["shop", "emag"] = "emag"
    units: int = Field(1, ge=0, le=99)
    sku: str = Field("", pattern=SKU_OR_BLANK)


class RuleChange(BaseModel):
    enabled: bool
    config: StockBuffer = Field(default_factory=StockBuffer)


async def settings_view(ctx: Context) -> dict:
    urls = {
        "shop": ctx.settings.shop_url,
        "emag": ctx.settings.emag_url,
        "warehouse": ctx.settings.warehouse_url,
    }
    checks = await asyncio.gather(*(views.check_health(ctx.http, url) for url in urls.values()))
    return {
        **asdict(ctx.tuning),
        "http_timeout_seconds": ctx.settings.http_timeout_seconds,
        "connections": [
            {"name": name, "url": url, **check}
            for (name, url), check in zip(urls.items(), checks, strict=True)
        ],
    }


@router.get("/settings", dependencies=[can_view])
async def get_settings(request: Request) -> dict:
    return await settings_view(request.app.state.ctx)


@router.put("/settings")
async def save_settings(
    request: Request,
    change: TuningChange,
    user: Annotated[auth.User, Depends(auth.require("settings"))],
) -> dict:
    ctx = request.app.state.ctx
    tuning.save(ctx, change.model_dump(exclude_none=True), user.name)
    return await settings_view(ctx)


@router.get("/users", dependencies=[can_view])
async def users() -> list[dict]:
    return [auth.User(name, role).as_json() for name, role in auth.USERS.items()]


@router.get("/rules", dependencies=[can_view])
async def list_rules(request: Request) -> list[dict]:
    return list(rules.all_rules(request.app.state.ctx).values())


@router.put("/rules/{name}")
async def save_rule(
    request: Request,
    name: Literal["stock-buffer", "auto-retry"],
    change: RuleChange,
    user: Annotated[auth.User, Depends(auth.require("rules"))],
) -> dict:
    ctx = request.app.state.ctx
    config = change.config.model_dump() if name == "stock-buffer" else {}
    rules.save(ctx, name, change.enabled, config, user.name)
    if name == "stock-buffer":
        # The channels should show the new figure now, not at the next periodic run.
        await reconciler.reconcile_all(ctx)
    return rules.get(ctx, name)
