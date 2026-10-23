import time
from collections.abc import Callable
from dataclasses import dataclass

from fastapi import HTTPException, Request

from common import signing
from glue.settings import Settings

COOKIE = "glue_session"
SESSION_SECONDS = 12 * 3600
ROLES = {
    "viewer": frozenset({"view"}),
    "operator": frozenset({"view", "decide", "ask"}),
    "admin": frozenset({"view", "decide", "ask", "rules", "settings", "demo"}),
}
# Demo users: one per role, named after it.
USERS = {name: name for name in ROLES}


@dataclass(frozen=True)
class User:
    name: str
    role: str

    def can(self, permission: str) -> bool:
        return permission in ROLES[self.role]

    def as_json(self) -> dict:
        return {"name": self.name, "role": self.role, "permissions": sorted(ROLES[self.role])}


def session_token(settings: Settings, username: str) -> str:
    payload = f"{username}:{int(time.time()) + SESSION_SECONDS}"
    return f"{payload}:{signing.sign(settings.session_secret, payload.encode())}"


def user_from_token(settings: Settings, token: str | None) -> User | None:
    if not token:
        return None
    payload, _, signature = token.rpartition(":")
    username, _, expires = payload.partition(":")
    if username not in USERS or not expires.isdecimal() or int(expires) < time.time():
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
            raise HTTPException(401, "sign in first")
        if not user.can(permission):
            raise HTTPException(403, f"a {user.role} may not do this")
        return user

    return check
