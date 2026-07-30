"""Integration test scripting quickstart.md Scenario 1 (core loop) against the real
WebSocket endpoint. The LLM call itself is stubbed (monkeypatched) so this test runs
without a live Ollama — the full-stack smoke test against real Ollama is
tests/integration/test_quickstart_scenarios.py (tasks.md T085, Polish phase)."""

from __future__ import annotations

import os
import sys

os.environ.setdefault("NEXTGEN_APP_PASSWORD", "test-password")
os.environ.setdefault("NEXTGEN_CREDENTIAL_KEY", "kQq4v2v7v3o5b1yqjq7c9m3n8p0r2s4t6u8w0x2y4z6=")

import pytest
from fastapi.testclient import TestClient

# LangGraph's interrupt() explicitly raises "Called get_config outside of a
# runnable context" when used from an async node on Python < 3.11 (verified
# against the installed langgraph package's source, app/config.py). This is the
# exact reason plan.md pins python:3.11-slim for the Docker image — this isn't
# a workaround, it's a hard requirement of the chosen human-in-the-loop
# mechanism. Skip locally on older interpreters rather than fail misleadingly;
# this test runs for real in CI on 3.11+.
requires_py311 = pytest.mark.skipif(
    sys.version_info < (3, 11),
    reason="LangGraph interrupt() requires Python 3.11+ in async contexts",
)

from app.db import init_db  # noqa: E402 — must follow the env var defaults above
from app.main import app  # noqa: E402
from app.providers.ollama_provider import OllamaProvider  # noqa: E402

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
            "id": "llm1",
            "type": "llm",
            "name": "Greet",
            "config": {"model": "llama3.2", "prompt": "Say hello to {{previous}}"},
            "position": {"x": 0, "y": 0},
        },
        {
            "id": "resp1",
            "type": "response",
            "name": "Show",
            "config": {"content": "{{previous}}"},
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
        {"id": "e1", "source": "in1", "source_port": "default", "target": "llm1"},
        {"id": "e2", "source": "llm1", "source_port": "success", "target": "resp1"},
        {"id": "e3", "source": "llm1", "source_port": "failure", "target": "resp2"},
    ],
}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXTGEN_DB_PATH", str(tmp_path / "test.db"))

    async def fake_generate(self, *, model, prompt, tools=None):
        return f"[stubbed llm response to: {prompt}]"

    monkeypatch.setattr(OllamaProvider, "generate", fake_generate)
    init_db()
    with TestClient(app) as c:
        c.post("/api/auth/login", json={"password": "test-password"})
        yield c


@requires_py311
def test_core_loop_end_to_end(client):
    create_res = client.post("/api/workflows", json={"name": "hello-test", "graph_json": GRAPH})
    assert create_res.status_code == 201, create_res.text

    with client.websocket_connect("/ws/chat") as ws:
        history = ws.receive_json()
        assert history["type"] == "history"

        ws.send_json({"type": "start_workflow", "payload": {"name": "hello-test"}})

        status_msg = ws.receive_json()
        assert status_msg["type"] == "status"

        input_request = ws.receive_json()
        assert input_request["type"] == "input_request"
        assert input_request["payload"]["prompt"] == "What's your name?"
        run_id = input_request["payload"]["run_id"]

        ws.send_json({"type": "provide_input", "payload": {"run_id": run_id, "value": "Ada"}})

        response_msg = ws.receive_json()
        assert response_msg["type"] == "response"
        assert "Ada" in response_msg["payload"]["content"]


def test_unknown_workflow_name_reports_not_found(client):
    with client.websocket_connect("/ws/chat") as ws:
        ws.receive_json()  # history
        ws.send_json({"type": "start_workflow", "payload": {"name": "does-not-exist"}})
        msg = ws.receive_json()
        assert msg["type"] == "workflow_not_found"
