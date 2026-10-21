import hmac
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from common import signing
from glue.audit import record
from glue.settings import Settings

COOKIE = "glue_session"
SESSION_SECONDS = 12 * 3600
ROLES = {
    "viewer": frozenset({"view"}),
    "operator": frozenset({"view", "decide", "ask"}),
    "admin": frozenset({"view", "decide", "ask", "rules", "demo"}),
}
# Demo users: one per role, named after it.
USERS = {name: name for name in ROLES}

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
router = APIRouter()


@dataclass(frozen=True)
class User:
    name: str
    role: str

    def can(self, permission: str) -> bool:
        return permission in ROLES[self.role]


def session_token(settings: Settings, username: str) -> str:
    payload = f"{username}:{int(time.time()) + SESSION_SECONDS}"
    return f"{payload}:{signing.sign(settings.session_secret, payload.encode())}"


def user_from_token(settings: Settings, token: str | None) -> User | None:
    if not token:
        return None
    payload, _, signature = token.rpartition(":")
    username, _, expires = payload.partition(":")
    if username not in USERS or not expires.isdigit() or int(expires) < time.time():
        return None
    if not signing.verify(settings.session_secret, payload.encode(), signature):
        return None
    return User(username, USERS[username])


def current_user(request: Request) -> User | None:
    return user_from_token(request.app.state.settings, request.cookies.get(COOKIE))


def require(permission: str) -> Callable[[Request], User]:
    def check(request: Request) -> User:
        user = current_user(request)
        if user is None:
            if request.headers.get("hx-request") == "true":
                raise HTTPException(401, "sign in first")
            location = f"/sign-in?next={quote(request.url.path)}"
            raise HTTPException(303, "sign in first", headers={"Location": location})
        if not user.can(permission):
            raise HTTPException(403, f"a {user.role} may not do this")
        request.state.user = user
        return user

    return check


def safe_next(path: str) -> str:
    return path if path.startswith("/") and not path.startswith("//") else "/"


@router.get("/sign-in")
async def sign_in_page(request: Request, next: str = "/"):
    context = {"next": safe_next(next), "error": None}
    return templates.TemplateResponse(request, "sign_in.html", context)


@router.post("/sign-in")
async def sign_in(
    request: Request,
    username: Annotated[str, Form(max_length=32)],
    password: Annotated[str, Form(max_length=128)],
    next: Annotated[str, Form()] = "/",
):
    settings: Settings = request.app.state.settings
    db = request.app.state.ctx.db
    expected = settings.password(username)
    if not expected or not hmac.compare_digest(expected.encode(), password.encode()):
        record(db, "-", "user", username, "sign_in_rejected")
        context = {"next": safe_next(next), "error": "Wrong user name or password."}
        return templates.TemplateResponse(request, "sign_in.html", context, status_code=401)
    record(db, "-", "user", username, "signed_in", role=USERS[username])
    response = RedirectResponse(safe_next(next), status_code=303)
    token = session_token(settings, username)
    response.set_cookie(COOKIE, token, max_age=SESSION_SECONDS, httponly=True, samesite="lax")
    return response


@router.post("/sign-out")
async def sign_out():
    response = RedirectResponse("/sign-in", status_code=303)
    response.delete_cookie(COOKIE)
    return response
