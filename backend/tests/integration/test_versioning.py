"""Integration test for T064 (SC-004, User Story 8): save v2, revert to v1, run,
confirm v1's exact original behavior is reproduced — not just that the DB row
points at v1's id, but that invoking the workflow via chat actually produces
v1's response again. Scripted against the real WebSocket endpoint like
test_core_loop.py. Requires Python 3.11 for the entry Input node's interrupt()."""

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

from app.db import init_db
from app.main import app


def _graph(response_text: str) -> dict:
    return {
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
                "config": {"content": response_text},
                "position": {"x": 0, "y": 0},
            },
        ],
        "edges": [{"id": "e1", "source": "in1", "source_port": "default", "target": "resp1"}],
    }


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXTGEN_DB_PATH", str(tmp_path / "test.db"))
    init_db()
    with TestClient(app) as c:
        c.post("/api/auth/login", json={"password": "test-password"})
        yield c


def _invoke_and_get_response(client, workflow_name: str) -> str:
    with client.websocket_connect("/ws/chat") as ws:
        ws.receive_json()  # history
        ws.send_json({"type": "start_workflow", "payload": {"name": workflow_name}})
        ws.receive_json()  # status
        input_request = ws.receive_json()
        run_id = input_request["payload"]["run_id"]
        ws.send_json({"type": "provide_input", "payload": {"run_id": run_id, "value": "go"}})
        response_msg = ws.receive_json()
        assert response_msg["type"] == "response"
        return response_msg["payload"]["content"]


@requires_py311
def test_revert_reproduces_original_versions_exact_behavior(client):
    create_res = client.post(
        "/api/workflows", json={"name": "revert-test", "graph_json": _graph("v1 response")}
    )
    workflow_id = create_res.json()["id"]
    v1_id = create_res.json()["active_version_id"]

    # v1 is active — confirm its behavior before ever touching v2.
    assert _invoke_and_get_response(client, "revert-test") == "v1 response"

    # Save and activate v2 — behavior changes.
    v2_res = client.post(
        f"/api/workflows/{workflow_id}/versions", json={"graph_json": _graph("v2 response")}
    )
    v2_id = v2_res.json()["id"]
    client.post(f"/api/workflows/{workflow_id}/activate/{v2_id}")
    assert _invoke_and_get_response(client, "revert-test") == "v2 response"

    # Revert to v1 — SC-004: original behavior must be reproduced exactly, not
    # just "some old-looking graph."
    client.post(f"/api/workflows/{workflow_id}/activate/{v1_id}")
    assert _invoke_and_get_response(client, "revert-test") == "v1 response"

    versions = client.get(f"/api/workflows/{workflow_id}/versions").json()
    assert [v["version_number"] for v in versions] == [1, 2]
