"""Contract test for POST /api/workflows — create + validate. See contracts/rest-api.md."""

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


VALID_GRAPH = {
    "nodes": [
        {
            "id": "in1",
            "type": "input",
            "name": "Ask name",
            "config": {"prompt": "Name?"},
            "position": {"x": 0, "y": 0},
        },
        {
            "id": "llm1",
            "type": "llm",
            "name": "Greet",
            "config": {"model": "llama3.2", "prompt": "Say hi to {{previous}}"},
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


def test_create_workflow_valid_graph_succeeds(client):
    res = client.post("/api/workflows", json={"name": "hello-test", "graph_json": VALID_GRAPH})
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["name"] == "hello-test"
    assert body["active_version_id"]


def test_create_workflow_duplicate_name_rejected(client):
    client.post("/api/workflows", json={"name": "dupe-test", "graph_json": VALID_GRAPH})
    res = client.post("/api/workflows", json={"name": "dupe-test", "graph_json": VALID_GRAPH})
    assert res.status_code == 409


def test_create_workflow_missing_failure_edge_rejected(client):
    bad_graph = {
        "nodes": VALID_GRAPH["nodes"][:3],
        "edges": [
            {"id": "e1", "source": "in1", "source_port": "default", "target": "llm1"},
            {"id": "e2", "source": "llm1", "source_port": "success", "target": "resp1"},
            # missing llm1's failure edge — FR-003
        ],
    }
    res = client.post("/api/workflows", json={"name": "bad-graph", "graph_json": bad_graph})
    assert res.status_code == 422
    assert "failure" in res.text
