"""Tests the WebSocket reconnection-replay logic (contracts/chat-websocket.md
§Reconnection behavior) in isolation from graph execution — a paused Run is
seeded directly in the DB rather than produced by actually running a graph, so
this verifies T043's new logic without depending on LangGraph's interrupt(),
which needs Python 3.11 (see test_pause_resume.py). This is the surgical test
for exactly the part of User Story 2 that isn't just "the Foundational plumbing
happened to already support it" — the SQL query and JSON round-trip that finds
and re-sends a paused run's pending prompt."""

from __future__ import annotations

import json
import os

os.environ.setdefault("NEXTGEN_APP_PASSWORD", "test-password")
os.environ.setdefault("NEXTGEN_CREDENTIAL_KEY", "kQq4v2v7v3o5b1yqjq7c9m3n8p0r2s4t6u8w0x2y4z6=")

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.db import get_engine, init_db
from app.main import app
from app.models.chat import ChatMessage, ChatRole
from app.models.run import Run, RunStatus
from app.models.workflow import Workflow, WorkflowVersion


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXTGEN_DB_PATH", str(tmp_path / "test.db"))
    init_db()
    with TestClient(app) as c:
        c.post("/api/auth/login", json={"password": "test-password"})
        yield c


def _seed_paused_run(session_id: str) -> str:
    """Directly inserts a paused Run + its history, bypassing graph execution."""
    with Session(get_engine()) as session:
        workflow = Workflow(name="seeded-flow")
        session.add(workflow)
        session.flush()
        version = WorkflowVersion(workflow_id=workflow.id, version_number=1, graph_json="{}")
        session.add(version)
        session.flush()
        workflow.active_version_id = version.id
        session.add(workflow)

        run = Run(
            workflow_version_id=version.id,
            chat_session_id=session_id,
            status=RunStatus.paused,
            pending_prompt=json.dumps({"prompt": "Confirm? yes/no", "node_id": "in2"}),
        )
        session.add(run)
        session.commit()
        session.refresh(run)

        session.add(
            ChatMessage(
                chat_session_id=session_id, role=ChatRole.user, content="Ada", run_id=run.id
            )
        )
        session.commit()
        return run.id


def test_reconnect_replays_history_and_pending_prompt(client):
    # First connection just to obtain a real ChatSession id from the server.
    with client.websocket_connect("/ws/chat") as ws:
        history = ws.receive_json()
        session_id = history["payload"]["session_id"]

    run_id = _seed_paused_run(session_id)

    with client.websocket_connect(f"/ws/chat?session_id={session_id}") as ws:
        history = ws.receive_json()
        assert history["type"] == "history"
        assert history["payload"]["session_id"] == session_id
        assert any(m["content"] == "Ada" for m in history["payload"]["messages"])

        pending = ws.receive_json()
        assert pending["type"] == "input_request"
        assert pending["payload"]["run_id"] == run_id
        assert pending["payload"]["prompt"] == "Confirm? yes/no"


def test_reconnect_with_no_paused_run_sends_no_input_request(client):
    with client.websocket_connect("/ws/chat") as ws:
        history = ws.receive_json()
        session_id = history["payload"]["session_id"]

    with client.websocket_connect(f"/ws/chat?session_id={session_id}") as ws:
        history = ws.receive_json()
        assert history["type"] == "history"
        assert history["payload"]["messages"] == []
        # Nothing else should arrive unsolicited — send a ping-style message
        # and confirm the only thing we get back is a response to it, not a
        # stray input_request from some phantom paused run.
        ws.send_json({"type": "start_workflow", "payload": {"name": "does-not-exist"}})
        msg = ws.receive_json()
        assert msg["type"] == "workflow_not_found"
