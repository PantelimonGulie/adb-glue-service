import asyncio
import json
import logging

import httpx
from openai import APIError, APITimeoutError, AsyncOpenAI

from glue.context import Context
from glue.settings import Settings

LABEL = "Local model (Ollama, Qwen 2.5 3B)"
ANSWER_SECONDS = 120
RETRY_SECONDS = 10
# Progress lines arrive every few hundred ms; a long silence means the pull is stuck.
PULL_TIMEOUT = httpx.Timeout(5, read=120)

log = logging.getLogger(__name__)


def client(settings: Settings, http: httpx.AsyncClient) -> AsyncOpenAI:
    # A local answer that timed out would only time out again.
    return AsyncOpenAI(
        base_url=f"{settings.llm_base_url}/v1",
        api_key="ollama",
        http_client=http,
        timeout=ANSWER_SECONDS,
        max_retries=0,
    )


async def probe(ctx: Context) -> str:
    try:
        response = await ctx.http.get(f"{ctx.settings.llm_base_url}/api/tags")
        response.raise_for_status()
        names = [model.get("name") for model in response.json().get("models", [])]
    except (httpx.HTTPError, ValueError):
        return "offline"
    return "ready" if ctx.settings.llm_model in names else "missing"


async def status(ctx: Context) -> dict:
    state = ctx.model_status if ctx.model_status == "downloading" else await probe(ctx)
    progress = 1.0 if state == "ready" else ctx.model_progress
    return {"id": "local", "label": LABEL, "status": state, "progress": round(progress, 3)}


def not_ready(model: dict) -> str:
    if model["status"] == "downloading":
        return (
            f"The local model is still downloading ({model['progress']:.0%})."
            " It is a one-time download of about 2 GB."
        )
    if model["status"] == "missing":
        return f"The local model is not downloaded yet. Glue retries every {RETRY_SECONDS} s."
    return "The local model server (Ollama) is not answering. Start Ollama, or its Docker container."


def failure(exc: APIError) -> str:
    if isinstance(exc, APITimeoutError):
        return f"The local model took longer than {ANSWER_SECONDS} s. Try a lower effort."
    return f"The local model failed: {exc.message}"


async def ensure_model(ctx: Context) -> None:
    while True:
        try:
            state = await probe(ctx)
            if state == "ready" or (state == "missing" and await pull(ctx)):
                break
        except Exception:
            log.exception("local model check failed")
            state = "offline"
        ctx.model_status = state
        await asyncio.sleep(RETRY_SECONDS)
    ctx.model_status, ctx.model_progress = "ready", 1.0
    log.info("Local model %s is ready", ctx.settings.llm_model)


async def pull(ctx: Context) -> bool:
    model = ctx.settings.llm_model
    log.info("Downloading local model %s (about 2 GB, one time)", model)
    ctx.model_status, ctx.model_progress = "downloading", 0.0
    layers: dict[str, tuple[int, int]] = {}
    try:
        async with ctx.http.stream(
            "POST",
            f"{ctx.settings.llm_base_url}/api/pull",
            json={"model": model, "stream": True},
            timeout=PULL_TIMEOUT,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                update = json.loads(line) if line else {}
                if "error" in update:
                    raise ValueError(update["error"])
                if update.get("total"):
                    layers[update["digest"]] = (update.get("completed", 0), update["total"])
                    done = sum(completed for completed, _ in layers.values())
                    ctx.model_progress = done / sum(size for _, size in layers.values())
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        log.warning("Downloading local model %s stopped, will retry: %s", model, exc)
        return False
    return True
