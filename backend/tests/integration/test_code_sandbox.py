"""Integration test scripting quickstart.md Scenario 4 (T056, SC-005, User Story
6) — a Code node attempting `import socket; socket.socket()` must route to
failure, not hang the run or crash the app. Scripted against the real WebSocket
endpoint like test_core_loop.py. Requires Python 3.11 for the entry Input node's
interrupt(); see tests/unit/test_code_node.py for direct coverage of the sandbox
itself (real subprocess, not mocked) that runs on this sandbox's Python 3.10."""

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
            "name": "Ask trigger",
            "config": {"prompt": "Type anything to run the snippet"},
            "position": {"x": 0, "y": 0},
        },
        {
            "id": "code1",
            "type": "code",
            "name": "Malicious snippet",
            "config": {"snippet": "import socket\nresult = socket.socket()"},
            "position": {"x": 0, "y": 0},
        },
        {
            "id": "resp1",
            "type": "response",
            "name": "Success",
            "config": {"content": "Should never get here: {{previous}}"},
            "position": {"x": 0, "y": 0},
        },
        {
            "id": "resp2",
            "type": "response",
            "name": "Blocked",
            "config": {"content": "Sandbox blocked it: {{previous}}"},
            "position": {"x": 0, "y": 0},
        },
    ],
    "edges": [
        {"id": "e1", "source": "in1", "source_port": "default", "target": "code1"},
        {"id": "e2", "source": "code1", "source_port": "success", "target": "resp1"},
        {"id": "e3", "source": "code1", "source_port": "failure", "target": "resp2"},
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
def test_malicious_snippet_routes_to_failure_response(client):
    create_res = client.post("/api/workflows", json={"name": "sandbox-test", "graph_json": GRAPH})
    assert create_res.status_code == 201, create_res.text

    with client.websocket_connect("/ws/chat") as ws:
        ws.receive_json()  # history
        ws.send_json({"type": "start_workflow", "payload": {"name": "sandbox-test"}})
        ws.receive_json()  # status

        input_request = ws.receive_json()
        assert input_request["type"] == "input_request"
        run_id = input_request["payload"]["run_id"]

        ws.send_json({"type": "provide_input", "payload": {"run_id": run_id, "value": "go"}})

        response_msg = ws.receive_json()
        assert response_msg["type"] == "response"
        content = response_msg["payload"]["content"]
        assert "Sandbox blocked it" in content
        assert "socket" in content.lower()
