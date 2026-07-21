"""FastAPI app entrypoint: mounts routers, the password gate, and (in the Docker
image) the built frontend as static files."""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api import auth_routes, credentials, runs, workflows
from app.auth import PasswordGateMiddleware
from app.chat import websocket as chat_websocket
from app.db import get_session, init_db
from app.runtime.executor import reconcile_stale_runs

app = FastAPI(title="NextGen")

app.add_middleware(PasswordGateMiddleware)

app.include_router(auth_routes.router)
app.include_router(workflows.router)
app.include_router(runs.router)
app.include_router(credentials.router)
app.include_router(chat_websocket.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    session_gen = get_session()
    session = next(session_gen)
    try:
        reconcile_stale_runs(session)
    finally:
        session.close()


static_dir = os.environ.get("NEXTGEN_STATIC_DIR")
if static_dir and os.path.isdir(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
