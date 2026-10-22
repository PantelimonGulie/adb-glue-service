from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

SERVER_PATHS = ("api", "events", "emag/notifications", "health")


def mount_spa(app: FastAPI, dist: Path) -> None:
    if not (dist / "index.html").is_file():
        return
    assets = StaticFiles(directory=dist / "assets", check_dir=False)
    app.mount("/assets", assets, name="assets")

    # The app does its own routing, so a reload on /orders/shop-1 must still get index.html.
    @app.get("/{path:path}", include_in_schema=False)
    async def index(path: str) -> FileResponse:
        if any(path == prefix or path.startswith(f"{prefix}/") for prefix in SERVER_PATHS):
            raise HTTPException(404)
        return FileResponse(dist / "index.html")
