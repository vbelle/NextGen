"""Integration test for Decision true/false branching, both directions (T045, User
Story 3) — scripted against the real WebSocket endpoint like test_core_loop.py.
Requires Python 3.11 for the entry Input node's interrupt(); see
tests/unit/test_decision_node.py for coverage of the branching logic itself (every
operator, the {{variable}}-not-set failure) that runs on this sandbox's Python 3.10."""

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
            "name": "Ask number",
            "config": {"prompt": "Enter a number"},
            "position": {"x": 0, "y": 0},
        },
        {
            "id": "dec1",
            "type": "decision",
            "name": "Is it big?",
            "config": {"left": "{{previous}}", "operator": "gt", "right": "10"},
            "position": {"x": 0, "y": 0},
        },
        {
            "id": "resp_true",
            "type": "response",
            "name": "Big",
            "config": {"content": "That's a big number."},
            "position": {"x": 0, "y": 0},
        },
        {
            "id": "resp_false",
            "type": "response",
            "name": "Small",
            "config": {"content": "That's a small number."},
            "position": {"x": 0, "y": 0},
        },
    ],
    "edges": [
        {"id": "e1", "source": "in1", "source_port": "default", "target": "dec1"},
        {"id": "e2", "source": "dec1", "source_port": "true", "target": "resp_true"},
        {"id": "e3", "source": "dec1", "source_port": "false", "target": "resp_false"},
    ],
}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXTGEN_DB_PATH", str(tmp_path / "test.db"))
    init_db()
    with TestClient(app) as c:
        c.post("/api/auth/login", json={"password": "test-password"})
        yield c


def _run_once(client, value: str) -> str:
    with client.websocket_connect("/ws/chat") as ws:
        ws.receive_json()  # history
        ws.send_json({"type": "start_workflow", "payload": {"name": "branch-test"}})
        ws.receive_json()  # status
        input_request = ws.receive_json()
        assert input_request["type"] == "input_request"
        run_id = input_request["payload"]["run_id"]
        ws.send_json({"type": "provide_input", "payload": {"run_id": run_id, "value": value}})
        response_msg = ws.receive_json()
        assert response_msg["type"] == "response"
        return response_msg["payload"]["content"]


@requires_py311
def test_decision_routes_true_branch(client):
    create_res = client.post("/api/workflows", json={"name": "branch-test", "graph_json": GRAPH})
    assert create_res.status_code == 201, create_res.text
    assert _run_once(client, "42") == "That's a big number."


@requires_py311
def test_decision_routes_false_branch(client):
    create_res = client.post("/api/workflows", json={"name": "branch-test", "graph_json": GRAPH})
    assert create_res.status_code == 201, create_res.text
    assert _run_once(client, "5") == "That's a small number."
