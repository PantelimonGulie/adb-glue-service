from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

COMMON = Path(__file__).parent
BUCHAREST = ZoneInfo("Europe/Bucharest")


def dashboard_link(request: Request) -> dict:
    return {"dashboard_url": str(request.url.replace(port=8000, path="/", query=""))}


def templates(app_dir: Path) -> Jinja2Templates:
    directories = [app_dir / "templates", COMMON / "templates"]
    return Jinja2Templates(directory=directories, context_processors=[dashboard_link])


def mount_static(app: FastAPI, app_dir: Path) -> None:
    app.mount("/static/common", StaticFiles(directory=COMMON / "static"), name="common")
    app.mount("/static", StaticFiles(directory=app_dir / "static"), name="static")


def clock(moment: datetime) -> str:
    return moment.astimezone(BUCHAREST).strftime("%H:%M:%S")


def price(amount: int) -> str:
    return f"{amount:,}".replace(",", ".")
