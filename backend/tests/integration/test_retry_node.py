"""Integration test scripting quickstart.md Scenario 3 (T060, SC-008, User Story
7) — an always-failing API node retried exactly 3 times, never more, then gives
up cleanly. Scripted against the real WebSocket endpoint like test_core_loop.py,
and also verifies GET /api/runs/{id}/executions shows the exact audit trail
quickstart.md describes (3 API failure rows, Retry rows with attempt_count
1/2/3) — this doubles as the first genuine end-to-end proof that the audit
logging wired into app/graph/compiler.py actually works, not just
tests/unit/test_audit_logging.py's direct-call version. Requires Python 3.11 for
the entry Input node's interrupt(); see tests/unit/test_retry_node.py for the
Retry node's own attempt-counting logic, which doesn't need that."""

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

# in1 -> api1 --failure--> retry1 --retry--> api1 (loop) / --give-up--> resp_giveup
# api1's success output must also be connected (FR-003) even though this
# intentionally-invalid URL never succeeds.
GRAPH = {
    "nodes": [
        {
            "id": "in1",
            "type": "input",
            "name": "Start",
            "config": {"prompt": "Type anything to start"},
            "position": {"x": 0, "y": 0},
        },
        {
            "id": "api1",
            "type": "api",
            "name": "Always fails",
            "config": {"method": "GET", "url": "http://localhost:1/does-not-exist"},
            "position": {"x": 0, "y": 0},
        },
        {
            "id": "retry1",
            "type": "retry",
            "name": "Retry up to 3",
            "config": {"max_attempts": 3},
            "position": {"x": 0, "y": 0},
        },
        {
            "id": "resp_success",
            "type": "response",
            "name": "Unreachable",
            "config": {"content": "Should never get here."},
            "position": {"x": 0, "y": 0},
        },
        {
            "id": "resp_giveup",
            "type": "response",
            "name": "Give up",
            "config": {"content": "Failed after 3 attempts."},
            "position": {"x": 0, "y": 0},
        },
    ],
    "edges": [
        {"id": "e1", "source": "in1", "source_port": "default", "target": "api1"},
        {"id": "e2", "source": "api1", "source_port": "success", "target": "resp_success"},
        {"id": "e3", "source": "api1", "source_port": "failure", "target": "retry1"},
        {"id": "e4", "source": "retry1", "source_port": "retry", "target": "api1"},
        {"id": "e5", "source": "retry1", "source_port": "give-up", "target": "resp_giveup"},
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
def test_retries_exactly_three_times_then_gives_up(client):
    create_res = client.post("/api/workflows", json={"name": "retry-test", "graph_json": GRAPH})
    assert create_res.status_code == 201, create_res.text

    with client.websocket_connect("/ws/chat") as ws:
        ws.receive_json()  # history
        ws.send_json({"type": "start_workflow", "payload": {"name": "retry-test"}})
        ws.receive_json()  # status

        input_request = ws.receive_json()
        assert input_request["type"] == "input_request"
        run_id = input_request["payload"]["run_id"]

        ws.send_json({"type": "provide_input", "payload": {"run_id": run_id, "value": "go"}})

        response_msg = ws.receive_json()
        assert response_msg["type"] == "response"
        assert response_msg["payload"]["content"] == "Failed after 3 attempts."

    executions = client.get(f"/api/runs/{run_id}/executions").json()

    api_rows = [e for e in executions if e["node_id"] == "api1"]
    assert len(api_rows) == 3
    assert all(e["output_port"] == "failure" for e in api_rows)

    retry_rows = [e for e in executions if e["node_id"] == "retry1"]
    assert len(retry_rows) == 3
    assert [e["attempt_count"] for e in retry_rows] == [1, 2, 3]
    assert [e["output_port"] for e in retry_rows] == ["retry", "retry", "give-up"]
