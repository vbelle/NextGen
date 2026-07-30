"""Shared-password session gate (research.md §8). No per-user accounts in v1 —
this is a deliberate tradeoff per Constitution "Access control (v1)"."""

from __future__ import annotations

import hmac
import os

from itsdangerous import BadSignature, URLSafeTimedSerializer
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

SESSION_COOKIE = "nextgen_session"
SESSION_MAX_AGE_SECONDS = 60 * 60 * 24 * 14  # 14 days
_PUBLIC_PATHS = {"/api/auth/login", "/health"}


def _serializer() -> URLSafeTimedSerializer:
    secret = os.environ.get("NEXTGEN_CREDENTIAL_KEY", "dev-only-insecure-secret")
    return URLSafeTimedSerializer(secret, salt="nextgen-session")


def check_password(submitted: str) -> bool:
    expected = os.environ.get("NEXTGEN_APP_PASSWORD", "")
    return bool(expected) and hmac.compare_digest(submitted, expected)


def issue_session_token() -> str:
    return _serializer().dumps({"authenticated": True})


def verify_session_token(token: str | None) -> bool:
    if not token:
        return False
    try:
        data = _serializer().loads(token, max_age=SESSION_MAX_AGE_SECONDS)
    except BadSignature:
        return False
    return bool(data.get("authenticated"))


class PasswordGateMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path in _PUBLIC_PATHS or not path.startswith("/api"):
            # Non-API paths (static frontend assets, the WebSocket handshake's own
            # cookie check happens inside websocket.py) pass through here; the SPA
            # itself blocks on an unauthenticated /api/workflows call and shows Login.
            return await call_next(request)
        token = request.cookies.get(SESSION_COOKIE)
        if not verify_session_token(token):
            return JSONResponse(status_code=401, content={"detail": "Not authenticated"})
        return await call_next(request)
