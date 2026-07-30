"""Integration test for cross-graph Variable resolution (T051, SC-009, User Story
5) — proves a value saved early is still readable via {{name}} from a LATER node
that is NOT directly wired to the Variable node, scripted against the real
WebSocket endpoint like test_core_loop.py. Requires Python 3.11 for the entry
Input node's interrupt(); see tests/unit/test_variable_node.py for coverage of
the node's own logic that runs on this sandbox's Python 3.10."""

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
from app.providers.ollama_provider import OllamaProvider  # noqa: E402

# in1 -> var1 (saves "username") -> llm1 -> resp1/resp2.
# resp1's direct upstream neighbor is llm1, NOT var1 — {{username}} is only
# reachable here because Variable writes are graph-wide, not edge-based.
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
            "id": "var1",
            "type": "variable",
            "name": "Remember name",
            "config": {"name": "username"},
            "position": {"x": 0, "y": 0},
        },
        {
            "id": "llm1",
            "type": "llm",
            "name": "Unrelated call",
            "config": {"model": "llama3.2", "prompt": "Say something unrelated to {{previous}}"},
            "position": {"x": 0, "y": 0},
        },
        {
            "id": "resp1",
            "type": "response",
            "name": "Show",
            "config": {"content": "Hello {{username}}, the model said: {{previous}}"},
            "position": {"x": 0, "y": 0},
        },
        {
            "id": "resp2",
            "type": "response",
            "name": "Error",
            "config": {"content": "Something went wrong."},
            "position": {"x": 0, "y": 0},
        },
    ],
    "edges": [
        {"id": "e1", "source": "in1", "source_port": "default", "target": "var1"},
        {"id": "e2", "source": "var1", "source_port": "default", "target": "llm1"},
        {"id": "e3", "source": "llm1", "source_port": "success", "target": "resp1"},
        {"id": "e4", "source": "llm1", "source_port": "failure", "target": "resp2"},
    ],
}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXTGEN_DB_PATH", str(tmp_path / "test.db"))

    async def fake_generate(self, *, model, prompt, tools=None):
        return "[stubbed unrelated response]"

    monkeypatch.setattr(OllamaProvider, "generate", fake_generate)
    init_db()
    with TestClient(app) as c:
        c.post("/api/auth/login", json={"password": "test-password"})
        yield c


@requires_py311
def test_variable_readable_from_non_adjacent_node(client):
    create_res = client.post("/api/workflows", json={"name": "scope-test", "graph_json": GRAPH})
    assert create_res.status_code == 201, create_res.text

    with client.websocket_connect("/ws/chat") as ws:
        ws.receive_json()  # history
        ws.send_json({"type": "start_workflow", "payload": {"name": "scope-test"}})
        ws.receive_json()  # status

        input_request = ws.receive_json()
        assert input_request["type"] == "input_request"
        run_id = input_request["payload"]["run_id"]

        ws.send_json({"type": "provide_input", "payload": {"run_id": run_id, "value": "Ada"}})

        response_msg = ws.receive_json()
        assert response_msg["type"] == "response"
        content = response_msg["payload"]["content"]
        assert "Hello Ada" in content
        assert "[stubbed unrelated response]" in content
