"""Integration test for an LLM node invoking a wired Tool node mid-generation
(T073, User Story 11), scripted against the real WebSocket endpoint like
test_core_loop.py.

Unlike test_core_loop.py (which stubs OllamaProvider.generate() wholesale),
this stubs one level lower — ChatOllama.bind_tools()/ainvoke() — so the real
function-calling loop in app/providers/ollama_provider.py actually runs: the
fake model's first turn requests a tool call, the real calculator
implementation (app/graph/tool_registry.py) executes it, the real audit
write happens (app/graph/nodes/llm_node.py's _make_tool), and the result is
fed back for a fake second turn. This is what proves the Tool node's result
reaches the model and its execution is audited — not just that the graph
compiles. Requires Python 3.11 for the entry Input node's interrupt()."""

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

from langchain_core.messages import AIMessage
from langchain_ollama import ChatOllama

from app.db import init_db
from app.main import app

GRAPH = {
    "nodes": [
        {
            "id": "in1",
            "type": "input",
            "name": "Ask",
            "config": {"prompt": "What's 2 + 3?"},
            "position": {"x": 0, "y": 0},
        },
        {
            "id": "tool1",
            "type": "tool",
            "name": "Add",
            "config": {
                "function_name": "add",
                "description": "Evaluates an arithmetic expression",
                "implementation_ref": "calculator",
            },
            "position": {"x": 0, "y": 0},
        },
        {
            "id": "llm1",
            "type": "llm",
            "name": "Answer",
            "config": {"model": "llama3.2", "prompt": "{{previous}}"},
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
        {"id": "e2", "source": "tool1", "source_port": "default", "target": "llm1"},
        {"id": "e3", "source": "llm1", "source_port": "success", "target": "resp1"},
        {"id": "e4", "source": "llm1", "source_port": "failure", "target": "resp2"},
    ],
}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXTGEN_DB_PATH", str(tmp_path / "test.db"))

    call_count = {"n": 0}

    async def fake_ainvoke(self, messages, *args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            # First turn: the "model" decides it needs the calculator tool.
            return AIMessage(
                content="",
                tool_calls=[{"name": "add", "args": {"expression": "2 + 3"}, "id": "call_1"}],
            )
        # Second turn: the tool's result (fed back as a ToolMessage) is in
        # `messages` by now — the fake model "incorporates" it into its answer.
        tool_messages = [m for m in messages if getattr(m, "type", None) == "tool"]
        assert tool_messages, "expected the tool's result to be in the conversation by turn 2"
        return AIMessage(content=f"The answer is {tool_messages[-1].content}.", tool_calls=[])

    monkeypatch.setattr(ChatOllama, "bind_tools", lambda self, tools: self)
    monkeypatch.setattr(ChatOllama, "ainvoke", fake_ainvoke)

    init_db()
    with TestClient(app) as c:
        c.post("/api/auth/login", json={"password": "test-password"})
        c.call_count = call_count  # type: ignore[attr-defined]
        yield c


@requires_py311
def test_llm_node_invokes_wired_tool_node_mid_generation(client):
    create_res = client.post("/api/workflows", json={"name": "calc-test", "graph_json": GRAPH})
    assert create_res.status_code == 201, create_res.text

    with client.websocket_connect("/ws/chat") as ws:
        ws.receive_json()  # history
        ws.send_json({"type": "start_workflow", "payload": {"name": "calc-test"}})
        ws.receive_json()  # status

        input_request = ws.receive_json()
        assert input_request["type"] == "input_request"
        run_id = input_request["payload"]["run_id"]

        ws.send_json(
            {"type": "provide_input", "payload": {"run_id": run_id, "value": "what's 2 + 3?"}}
        )

        response_msg = ws.receive_json()
        assert response_msg["type"] == "response"
        assert response_msg["payload"]["content"] == "The answer is 5."

    # Two model turns: the tool-requesting turn and the final-answer turn.
    assert client.call_count["n"] == 2

    # The tool's own execution is independently audited (Constitution VII),
    # not just folded silently into the LLM node's own execution row.
    executions = client.get(f"/api/runs/{run_id}/executions").json()
    tool_rows = [e for e in executions if e["node_id"] == "tool1"]
    assert len(tool_rows) == 1
    assert tool_rows[0]["node_type"] == "tool"
    assert tool_rows[0]["output"] == "5"
