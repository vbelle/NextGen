"""POST /api/auth/login and /logout. See contracts/rest-api.md §Auth."""

from __future__ import annotations

from fastapi import APIRouter, Response
from pydantic import BaseModel

from app.auth import SESSION_COOKIE, SESSION_MAX_AGE_SECONDS, check_password, issue_session_token

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    password: str


@router.post("/login")
def login(body: LoginRequest, response: Response):
    if not check_password(body.password):
        response.status_code = 401
        return {"detail": "Incorrect password"}
    token = issue_session_token()
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
    )
    return {"authenticated": True}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(SESSION_COOKIE)
    return {"authenticated": False}
