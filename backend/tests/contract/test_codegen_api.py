"""Contract test for POST /api/codegen/langgraph — backs the canvas's "View
code" panel's LangGraph tab. Takes graph_json in the body directly (not a
saved workflow id) so it works on an unsaved canvas too."""

from __future__ import annotations

import os

os.environ.setdefault("NEXTGEN_APP_PASSWORD", "test-password")
os.environ.setdefault("NEXTGEN_CREDENTIAL_KEY", "kQq4v2v7v3o5b1yqjq7c9m3n8p0r2s4t6u8w0x2y4z6=")

import pytest
from fastapi.testclient import TestClient

from app.db import init_db
from app.main import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXTGEN_DB_PATH", str(tmp_path / "test.db"))
    init_db()
    with TestClient(app) as c:
        c.post("/api/auth/login", json={"password": "test-password"})
        yield c


def test_codegen_langgraph_returns_generated_code(client):
    graph_json = {
        "nodes": [
            {"id": "in1", "type": "input", "name": "Ask", "config": {}},
            {"id": "res1", "type": "response", "name": "Say", "config": {}},
        ],
        "edges": [
            {"id": "e1", "source": "in1", "target": "res1", "source_port": "default"},
        ],
    }
    res = client.post("/api/codegen/langgraph", json={"graph_json": graph_json})
    assert res.status_code == 200, res.text
    code = res.json()["code"]
    assert "StateGraph(GraphState)" in code
    assert 'builder.add_node("in1", run_input)' in code


def test_codegen_langgraph_requires_auth():
    with TestClient(app) as c:
        res = c.post(
            "/api/codegen/langgraph",
            json={"graph_json": {"nodes": [], "edges": []}},
        )
    assert res.status_code in (401, 403)
