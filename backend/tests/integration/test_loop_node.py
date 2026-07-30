"""Integration test for a Loop node iterating a 3-item list (T067, User Story
9), scripted against the real WebSocket endpoint like test_core_loop.py.
Exercises the full multi-node-cycle design end to end: Input -> Code (splits
the user's reply into a list) -> Loop -> Code (uppercases one item) -> loops
back to Loop -> ... -> Response (shows the aggregated results), and also
verifies via GET /api/runs/{id}/executions that the loop body actually ran
once per item (not zero, not fewer, not more). Requires Python 3.11 for the
entry Input node's interrupt(); see tests/unit/test_loop_node.py for the Loop
node's own iteration logic, which doesn't need that."""

from __future__ import annotations

import json
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

from app.db import init_db
from app.main import app

GRAPH = {
    "nodes": [
        {
            "id": "in1",
            "type": "input",
            "name": "Ask items",
            "config": {"prompt": "Comma-separated items?"},
            "position": {"x": 0, "y": 0},
        },
        {
            "id": "split1",
            "type": "code",
            "name": "Split into list",
            "config": {"snippet": "result = [x.strip() for x in previous.split(',')]"},
            "position": {"x": 0, "y": 0},
        },
        {
            "id": "loop1",
            "type": "loop",
            "name": "For each item",
            "config": {"collection_ref": "{{previous}}", "body_start_node_id": "upper1"},
            "position": {"x": 0, "y": 0},
        },
        {
            "id": "upper1",
            "type": "code",
            "name": "Uppercase item",
            "config": {"snippet": "result = previous.upper()"},
            "position": {"x": 0, "y": 0},
        },
        {
            "id": "resp_done",
            "type": "response",
            "name": "Show",
            "config": {"content": "Processed: {{previous}}"},
            "position": {"x": 0, "y": 0},
        },
        {
            "id": "resp_err",
            "type": "response",
            "name": "Error",
            "config": {"content": "Something went wrong."},
            "position": {"x": 0, "y": 0},
        },
    ],
    "edges": [
        {"id": "e1", "source": "in1", "source_port": "default", "target": "split1"},
        {"id": "e2", "source": "split1", "source_port": "success", "target": "loop1"},
        {"id": "e3", "source": "split1", "source_port": "failure", "target": "resp_err"},
        {"id": "e4", "source": "loop1", "source_port": "body", "target": "upper1"},
        {"id": "e5", "source": "loop1", "source_port": "done", "target": "resp_done"},
        {"id": "e6", "source": "upper1", "source_port": "success", "target": "loop1"},
        {"id": "e7", "source": "upper1", "source_port": "failure", "target": "resp_err"},
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
def test_loop_iterates_three_items_and_aggregates(client):
    create_res = client.post("/api/workflows", json={"name": "loop-test", "graph_json": GRAPH})
    assert create_res.status_code == 201, create_res.text

    with client.websocket_connect("/ws/chat") as ws:
        ws.receive_json()  # history
        ws.send_json({"type": "start_workflow", "payload": {"name": "loop-test"}})
        ws.receive_json()  # status

        input_request = ws.receive_json()
        assert input_request["type"] == "input_request"
        run_id = input_request["payload"]["run_id"]

        ws.send_json({"type": "provide_input", "payload": {"run_id": run_id, "value": "a, b, c"}})

        response_msg = ws.receive_json()
        assert response_msg["type"] == "response"
        assert response_msg["payload"]["content"] == "Processed: " + json.dumps(["A", "B", "C"])

    executions = client.get(f"/api/runs/{run_id}/executions").json()

    body_rows = [e for e in executions if e["node_id"] == "upper1"]
    assert len(body_rows) == 3, "body must run exactly once per item, not more or fewer"
    assert [e["output"] for e in body_rows] == ["A", "B", "C"]

    loop_rows = [e for e in executions if e["node_id"] == "loop1"]
    assert [e["output_port"] for e in loop_rows] == ["body", "body", "body", "done"]
