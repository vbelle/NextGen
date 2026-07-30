"""Contract test for POST /api/workflows/{id}/versions and
/activate/{version_id} (T063, User Story 8). See contracts/rest-api.md.

This mostly confirms endpoints that were already built during the Foundational
phase (app/api/workflows.py) work as the contract describes, rather than
introducing new behavior — T065 in tasks.md explicitly frames US8's
implementation work as "confirm/extend... this task closes any gaps found by
T063/T064." No gaps were found: every endpoint below already existed."""

from __future__ import annotations

import os

os.environ.setdefault("NEXTGEN_APP_PASSWORD", "test-password")
os.environ.setdefault("NEXTGEN_CREDENTIAL_KEY", "kQq4v2v7v3o5b1yqjq7c9m3n8p0r2s4t6u8w0x2y4z6=")

import pytest
from fastapi.testclient import TestClient

from app.db import init_db
from app.main import app

GRAPH_V1 = {
    "nodes": [
        {
            "id": "in1",
            "type": "input",
            "name": "Ask",
            "config": {"prompt": "go?"},
            "position": {"x": 0, "y": 0},
        },
        {
            "id": "resp1",
            "type": "response",
            "name": "Show",
            "config": {"content": "v1 response"},
            "position": {"x": 0, "y": 0},
        },
    ],
    "edges": [{"id": "e1", "source": "in1", "source_port": "default", "target": "resp1"}],
}

GRAPH_V2 = {
    "nodes": [
        {
            "id": "in1",
            "type": "input",
            "name": "Ask",
            "config": {"prompt": "go?"},
            "position": {"x": 0, "y": 0},
        },
        {
            "id": "resp1",
            "type": "response",
            "name": "Show",
            "config": {"content": "v2 response"},
            "position": {"x": 0, "y": 0},
        },
    ],
    "edges": [{"id": "e1", "source": "in1", "source_port": "default", "target": "resp1"}],
}

INVALID_GRAPH = {"nodes": [], "edges": []}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXTGEN_DB_PATH", str(tmp_path / "test.db"))
    init_db()
    with TestClient(app) as c:
        c.post("/api/auth/login", json={"password": "test-password"})
        yield c


def test_create_version_adds_new_version_without_activating(client):
    create_res = client.post("/api/workflows", json={"name": "ver-test", "graph_json": GRAPH_V1})
    workflow_id = create_res.json()["id"]
    v1_id = create_res.json()["active_version_id"]

    version_res = client.post(
        f"/api/workflows/{workflow_id}/versions", json={"graph_json": GRAPH_V2}
    )
    assert version_res.status_code == 201, version_res.text
    assert version_res.json()["version_number"] == 2

    # Saving a new version must NOT change what's active for chat invocation.
    workflow = client.get(f"/api/workflows/{workflow_id}").json()
    assert workflow["active_version_id"] == v1_id

    versions = client.get(f"/api/workflows/{workflow_id}/versions").json()
    assert [v["version_number"] for v in versions] == [1, 2]


def test_activate_switches_active_version(client):
    create_res = client.post("/api/workflows", json={"name": "ver-test-2", "graph_json": GRAPH_V1})
    workflow_id = create_res.json()["id"]

    version_res = client.post(
        f"/api/workflows/{workflow_id}/versions", json={"graph_json": GRAPH_V2}
    )
    v2_id = version_res.json()["id"]

    activate_res = client.post(f"/api/workflows/{workflow_id}/activate/{v2_id}")
    assert activate_res.status_code == 200, activate_res.text
    assert activate_res.json()["active_version_id"] == v2_id

    workflow = client.get(f"/api/workflows/{workflow_id}").json()
    assert workflow["active_version_id"] == v2_id
    assert workflow["graph_json"]["nodes"][1]["config"]["content"] == "v2 response"


def test_activate_nonexistent_version_404s(client):
    create_res = client.post("/api/workflows", json={"name": "ver-test-3", "graph_json": GRAPH_V1})
    workflow_id = create_res.json()["id"]
    res = client.post(f"/api/workflows/{workflow_id}/activate/does-not-exist")
    assert res.status_code == 404


def test_activate_on_nonexistent_workflow_404s(client):
    res = client.post("/api/workflows/does-not-exist/activate/also-does-not-exist")
    assert res.status_code == 404


def test_create_version_with_invalid_graph_rejected(client):
    create_res = client.post("/api/workflows", json={"name": "ver-test-4", "graph_json": GRAPH_V1})
    workflow_id = create_res.json()["id"]
    res = client.post(f"/api/workflows/{workflow_id}/versions", json={"graph_json": INVALID_GRAPH})
    assert res.status_code == 422
