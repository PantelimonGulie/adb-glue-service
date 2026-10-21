import json

from fastapi import APIRouter, FastAPI, Request

router = APIRouter()


async def log_request(request: Request) -> None:
    line = {
        "path": request.url.path,
        "headers": dict(request.headers),
        "body": await request.json(),
    }
    print(json.dumps(line))


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@router.post("/events", status_code=202)
async def events(request: Request) -> None:
    await log_request(request)


@router.post("/emag/notifications", status_code=202)
async def emag_notifications(request: Request) -> None:
    await log_request(request)


def create_app() -> FastAPI:
    app = FastAPI(title="Glue")
    app.include_router(router)
    return app


app = create_app()
