"""Integration test for a Memory node returning top-k results and feeding a
downstream LLM node's prompt (T070, User Story 10), scripted against the real
WebSocket endpoint like test_core_loop.py. Sets the vector store up through the
app's own REST endpoints (not by poking app.vectorstore directly), so this
covers the store-management API and the Memory node together. The LLM call is
stubbed (like test_core_loop.py) so this runs without live Ollama for
generation; embeddings use a deterministic offline fake (see
tests/unit/test_memory_node.py) since live Ollama isn't available here either.
Requires Python 3.11 for the entry Input node's interrupt()."""

from __future__ import annotations

import hashlib
import os
import sys

os.environ.setdefault("NEXTGEN_APP_PASSWORD", "test-password")
os.environ.setdefault("NEXTGEN_CREDENTIAL_KEY", "kQq4v2v7v3o5b1yqjq7c9m3n8p0r2s4t6u8w0x2y4z6=")

import pytest
from chromadb import EmbeddingFunction
from fastapi.testclient import TestClient

requires_py311 = pytest.mark.skipif(
    sys.version_info < (3, 11),
    reason="LangGraph interrupt() requires Python 3.11+ in async contexts",
)

from app import vectorstore
from app.db import init_db
from app.main import app
from app.providers.ollama_provider import OllamaProvider


class FakeEmbeddingFunction(EmbeddingFunction):
    def __init__(self):
        pass

    @staticmethod
    def name():
        return "fake"

    def get_config(self):
        return {}

    @staticmethod
    def build_from_config(config):
        return FakeEmbeddingFunction()

    def __call__(self, input):
        return [[b / 255.0 for b in hashlib.sha256(text.encode()).digest()[:8]] for text in input]


GRAPH = {
    "nodes": [
        {
            "id": "in1",
            "type": "input",
            "name": "Ask",
            "config": {"prompt": "What's your question?"},
            "position": {"x": 0, "y": 0},
        },
        {
            "id": "mem1",
            "type": "memory",
            "name": "Look up context",
            "config": {"vector_store_ref": "kb-store", "query": "{{previous}}", "top_k": 2},
            "position": {"x": 0, "y": 0},
        },
        {
            "id": "llm1",
            "type": "llm",
            "name": "Answer",
            "config": {"model": "llama3.2", "prompt": "Context: {{previous}}"},
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
        {"id": "e1", "source": "in1", "source_port": "default", "target": "mem1"},
        {"id": "e2", "source": "mem1", "source_port": "default", "target": "llm1"},
        {"id": "e3", "source": "llm1", "source_port": "success", "target": "resp1"},
        {"id": "e4", "source": "llm1", "source_port": "failure", "target": "resp2"},
    ],
}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXTGEN_DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("NEXTGEN_VECTOR_STORE_PATH", str(tmp_path / "vector_stores"))
    monkeypatch.setattr(vectorstore, "_embedding_fn_override", FakeEmbeddingFunction())
    monkeypatch.setattr(vectorstore, "_client_cache", {})

    captured_prompts = []

    async def fake_generate(self, *, model, prompt, tools=None):
        captured_prompts.append(prompt)
        return "[stubbed answer]"

    monkeypatch.setattr(OllamaProvider, "generate", fake_generate)
    init_db()
    with TestClient(app) as c:
        c.post("/api/auth/login", json={"password": "test-password"})
        c.captured_prompts = captured_prompts  # type: ignore[attr-defined]
        yield c


@requires_py311
def test_memory_node_grounds_llm_prompt_with_top_k_results(client):
    store_res = client.post("/api/vector-stores", json={"name": "kb-store"})
    assert store_res.status_code == 201, store_res.text
    docs_res = client.post(
        "/api/vector-stores/kb-store/documents",
        json={"documents": ["The sky is blue.", "Water boils at 100C.", "Unrelated fact."]},
    )
    assert docs_res.status_code == 201, docs_res.text

    create_res = client.post("/api/workflows", json={"name": "memory-test", "graph_json": GRAPH})
    assert create_res.status_code == 201, create_res.text

    with client.websocket_connect("/ws/chat") as ws:
        ws.receive_json()  # history
        ws.send_json({"type": "start_workflow", "payload": {"name": "memory-test"}})
        ws.receive_json()  # status

        input_request = ws.receive_json()
        assert input_request["type"] == "input_request"
        run_id = input_request["payload"]["run_id"]

        ws.send_json(
            {"type": "provide_input", "payload": {"run_id": run_id, "value": "why is the sky blue"}}
        )

        response_msg = ws.receive_json()
        assert response_msg["type"] == "response"
        assert response_msg["payload"]["content"] == "[stubbed answer]"

    # The LLM's actual received prompt must have been grounded with 2 (top_k)
    # retrieved documents, not the raw query text or nothing at all.
    assert len(client.captured_prompts) == 1
    prompt = client.captured_prompts[0]
    assert "content" in prompt and "distance" in prompt

    executions = client.get(f"/api/runs/{run_id}/executions").json()
    mem_rows = [e for e in executions if e["node_id"] == "mem1"]
    assert len(mem_rows) == 1
    assert len(mem_rows[0]["output"]) == 2
