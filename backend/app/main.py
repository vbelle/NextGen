"""FastAPI app entrypoint: mounts routers, the password gate, and (in the Docker
image) the built frontend as static files."""

from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session

from app.api import (
    auth_routes,
    codegen,
    credentials,
    custom_tools,
    github_routes,
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
app.include_router(github_routes.router)
app.include_router(codegen.router)
app.include_router(chat_websocket.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


def seed_default_workflows(session: Session) -> None:
    from app.models.workflow import Workflow, WorkflowVersion
    from sqlmodel import select

    workflow_files = [
        "interview_knowledge_search.json",
        "obsidian_vault_search.json",
        "multi_agent_command_center.json",
    ]
    for fname in workflow_files:
        fpath = Path(fname)
        if not fpath.exists():
            continue
        try:
            with open(fpath) as f:
                data = json.load(f)
            wf_name = data.get("name")
            graph_json = data.get("graph_json")
            if not wf_name or not graph_json:
                continue

            graph_str = json.dumps(graph_json)
            existing = session.exec(select(Workflow).where(Workflow.name == wf_name)).first()
            if not existing:
                wf = Workflow(name=wf_name)
                session.add(wf)
                session.flush()
                ver = WorkflowVersion(workflow_id=wf.id, version_number=1, graph_json=graph_str)
                session.add(ver)
                session.flush()
                wf.active_version_id = ver.id
                session.add(wf)
                session.commit()
            else:
                active_ver = session.exec(
                    select(WorkflowVersion).where(WorkflowVersion.id == existing.active_version_id)
                ).first()
                if not active_ver or active_ver.graph_json != graph_str:
                    max_ver = session.exec(
                        select(WorkflowVersion)
                        .where(WorkflowVersion.workflow_id == existing.id)
                        .order_by(WorkflowVersion.version_number.desc())
                    ).first()
                    next_ver_num = (max_ver.version_number + 1) if max_ver else 1

                    new_ver = WorkflowVersion(
                        workflow_id=existing.id,
                        version_number=next_ver_num,
                        graph_json=graph_str,
                    )
                    session.add(new_ver)
                    session.flush()
                    existing.active_version_id = new_ver.id
                    session.add(existing)
                    session.commit()
        except Exception:
            pass


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    session_gen = get_session()
    session = next(session_gen)
    try:
        reconcile_stale_runs(session)
        seed_default_workflows(session)
    finally:
        session.close()
    start_scheduler()


static_dir = os.environ.get("NEXTGEN_STATIC_DIR")
if static_dir and os.path.isdir(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
