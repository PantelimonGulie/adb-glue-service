import hmac
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from glue import auth
from glue.audit import record

router = APIRouter()


class Credentials(BaseModel):
    username: str = Field(max_length=32)
    password: str = Field(max_length=128)


@router.post("/session")
async def sign_in(request: Request, response: Response, credentials: Credentials) -> dict:
    settings = request.app.state.settings
    db = request.app.state.ctx.db
    username = credentials.username
    expected = settings.password(username)
    if not expected or not hmac.compare_digest(expected.encode(), credentials.password.encode()):
        record(db, "-", "user", username, "sign_in_rejected")
        raise HTTPException(401, "Wrong user name or password.")
    user = auth.User(username, auth.USERS[username])
    record(db, "-", "user", username, "signed_in", role=user.role)
    token = auth.session_token(settings, username)
    response.set_cookie(
        auth.COOKIE, token, max_age=auth.SESSION_SECONDS, httponly=True, samesite="lax"
    )
    return user.as_json() | {"timezone": settings.business_timezone}


@router.delete("/session", status_code=204)
async def sign_out(response: Response) -> None:
    response.delete_cookie(auth.COOKIE)


@router.get("/me")
async def me(request: Request, user: Annotated[auth.User, Depends(auth.require("view"))]) -> dict:
    # The dashboard shows every time and day in the zone the API cuts days in.
    return user.as_json() | {"timezone": request.app.state.settings.business_timezone}
