"""Integration test scripting quickstart.md Scenario 2 (human-in-the-loop pause
survives a closed/reopened chat, FR-011). Uses Input(start) -> Input(mid-flow) ->
Response rather than the spec's full Input->LLM->Input->Decision->Response example
— Decision is User Story 3, not yet built, and User Story 2 should be independently
testable without depending on a later story (spec-kit's own principle)."""

from __future__ import annotations

import os
import sys

os.environ.setdefault("NEXTGEN_APP_PASSWORD", "test-password")
os.environ.setdefault("NEXTGEN_CREDENTIAL_KEY", "kQq4v2v7v3o5b1yqjq7c9m3n8p0r2s4t6u8w0x2y4z6=")

import pytest
from fastapi.testclient import TestClient

requires_py311 = pytest.mark.skipif(
    sys.version_info < (3, 11),
    reason="LangGraph interrupt() requires Python 3.11+ in async contexts",
)

from app.db import init_db  # noqa: E402
from app.main import app  # noqa: E402

GRAPH = {
    "nodes": [
        {
            "id": "in1",
            "type": "input",
            "name": "Ask name",
            "config": {"prompt": "What's your name?"},
            "position": {"x": 0, "y": 0},
        },
        {
            "id": "in2",
            "type": "input",
            "name": "Ask confirm",
            "config": {"prompt": "Confirm? yes/no"},
            "position": {"x": 0, "y": 0},
        },
        {
            "id": "resp1",
            "type": "response",
            "name": "Show",
            "config": {"content": "Got: {{previous}}"},
            "position": {"x": 0, "y": 0},
        },
    ],
    "edges": [
        {"id": "e1", "source": "in1", "source_port": "default", "target": "in2"},
        {"id": "e2", "source": "in2", "source_port": "default", "target": "resp1"},
    ],
}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXTGEN_DB_PATH", str(tmp_path / "test.db"))
    init_db()
    with TestClient(app) as c:
        c.post("/api/auth/login", json={"password": "test-password"})
        yield c


@requires_py311
def test_mid_flow_pause_survives_reconnect(client):
    create_res = client.post("/api/workflows", json={"name": "two-step", "graph_json": GRAPH})
    assert create_res.status_code == 201, create_res.text

    session_id = None
    run_id = None

    # --- First connection: start the flow, answer the first prompt, then
    # disconnect BEFORE answering the second (mid-flow) prompt — simulating
    # closing the browser tab mid-conversation. ---
    with client.websocket_connect("/ws/chat") as ws:
        history = ws.receive_json()
        session_id = history["payload"]["session_id"]

        ws.send_json({"type": "start_workflow", "payload": {"name": "two-step"}})
        ws.receive_json()  # status

        first_prompt = ws.receive_json()
        assert first_prompt["type"] == "input_request"
        assert first_prompt["payload"]["prompt"] == "What's your name?"
        run_id = first_prompt["payload"]["run_id"]

        ws.send_json({"type": "provide_input", "payload": {"run_id": run_id, "value": "Ada"}})

        second_prompt = ws.receive_json()
        assert second_prompt["type"] == "input_request"
        assert second_prompt["payload"]["prompt"] == "Confirm? yes/no"
        # Tab "closes" here — `with` block exit disconnects the socket without
        # ever answering the second prompt.

    # Confirm the Run is durably paused in the DB, not just in-memory.
    run_status = client.get(f"/api/runs/{run_id}").json()
    assert run_status["status"] == "paused"
    assert run_status["pending_prompt"]["prompt"] == "Confirm? yes/no"

    # --- Second connection, same session_id ("reopening chat") — the pending
    # prompt must be re-delivered without the user re-typing anything. ---
    with client.websocket_connect(f"/ws/chat?session_id={session_id}") as ws:
        history = ws.receive_json()
        assert history["type"] == "history"
        # Prior transcript (both messages so far) must be replayed too.
        assert any(m["content"] == "Ada" for m in history["payload"]["messages"])

        resumed_prompt = ws.receive_json()
        assert resumed_prompt["type"] == "input_request"
        assert resumed_prompt["payload"]["run_id"] == run_id
        assert resumed_prompt["payload"]["prompt"] == "Confirm? yes/no"

        ws.send_json({"type": "provide_input", "payload": {"run_id": run_id, "value": "yes"}})

        response_msg = ws.receive_json()
        assert response_msg["type"] == "response"
        assert response_msg["payload"]["content"] == "Got: yes"

    final_status = client.get(f"/api/runs/{run_id}").json()
    assert final_status["status"] == "completed"
