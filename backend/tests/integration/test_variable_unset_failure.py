"""Integration test for referencing an unset {{variable}} (T052, FR-025, User
Story 5) — proves it fails the run with a clear message rather than silently
rendering an empty string, end-to-end through the real WebSocket endpoint.
Requires Python 3.11 for the entry Input node's interrupt()."""

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

# resp1 references {{never_set}} — no Variable node in this graph ever sets it.
# Response has no failure output port (it isn't a DUAL_OUTPUT_TYPES member), so
# this must fail the whole run rather than route anywhere.
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
            "id": "resp1",
            "type": "response",
            "name": "Show",
            "config": {"content": "{{never_set}}"},
            "position": {"x": 0, "y": 0},
        },
    ],
    "edges": [
        {"id": "e1", "source": "in1", "source_port": "default", "target": "resp1"},
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
def test_unset_variable_fails_run_not_silent_empty_string(client):
    create_res = client.post("/api/workflows", json={"name": "unset-var-test", "graph_json": GRAPH})
    assert create_res.status_code == 201, create_res.text

    with client.websocket_connect("/ws/chat") as ws:
        ws.receive_json()  # history
        ws.send_json({"type": "start_workflow", "payload": {"name": "unset-var-test"}})
        ws.receive_json()  # status

        input_request = ws.receive_json()
        assert input_request["type"] == "input_request"
        run_id = input_request["payload"]["run_id"]

        ws.send_json({"type": "provide_input", "payload": {"run_id": run_id, "value": "Ada"}})

        failure_msg = ws.receive_json()
        assert failure_msg["type"] == "run_failed"
        assert "never_set" in failure_msg["payload"]["message"]

    run_status = client.get(f"/api/runs/{run_id}").json()
    assert run_status["status"] == "failed"
