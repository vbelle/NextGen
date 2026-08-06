"""FastAPI app entrypoint: mounts routers, the password gate, and (in the Docker
image) the built frontend as static files."""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api import (
    auth_routes,
    codegen,
    credentials,
    custom_tools,
    interview_routes,
    obsidian_routes,
    runs,
    tools,
    triggers,
    vector_stores,
    workflows,
)
from app.auth import PasswordGateMiddleware
from app.chat import websocket as chat_websocket
from app.db import get_session, init_db
from app.runtime.executor import reconcile_stale_runs
from app.runtime.scheduler import start_scheduler

app = FastAPI(title="NextGen")

app.add_middleware(PasswordGateMiddleware)

app.include_router(auth_routes.router)
app.include_router(workflows.router)
app.include_router(runs.router)
app.include_router(credentials.router)
app.include_router(vector_stores.router)
app.include_router(tools.router)
app.include_router(custom_tools.router)
app.include_router(triggers.router)
app.include_router(obsidian_routes.router)
app.include_router(interview_routes.router)
app.include_router(codegen.router)
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
    start_scheduler()


static_dir = os.environ.get("NEXTGEN_STATIC_DIR")
if static_dir and os.path.isdir(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
