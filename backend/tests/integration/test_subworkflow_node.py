"""Integration test for the Sub-workflow node (T077, User Story 12): Workflow
B embedded pinned inside Workflow A, run end to end over the real WebSocket,
including the "later update to B is ignored" check the task explicitly calls
for. The LLM call itself isn't exercised here (neither graph uses an LLM
node) — this is purely about the embedding/pinning/pause-auto-resume
mechanics, which don't depend on any provider. Requires Python 3.11 for
interrupt() (both graphs have an entry Input node)."""

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


def _workflow_b_graph(greeting_prefix: str) -> dict:
    return {
        "nodes": [
            {
                "id": "in1",
                "type": "input",
                "name": "Ask name",
                "config": {"prompt": "What's your name?"},
                "position": {"x": 0, "y": 0},
            },
            {
                "id": "resp1",
                "type": "response",
                "name": "Greet",
                "config": {"content": f"{greeting_prefix}, {{{{previous}}}}!"},
                "position": {"x": 0, "y": 0},
            },
        ],
        "edges": [{"id": "e1", "source": "in1", "source_port": "default", "target": "resp1"}],
    }


def _workflow_a_graph(pinned_version_id: str, workflow_b_id: str) -> dict:
    return {
        "nodes": [
            {
                "id": "in1",
                "type": "input",
                "name": "Ask name",
                "config": {"prompt": "What's your name?"},
                "position": {"x": 0, "y": 0},
            },
            {
                "id": "sub1",
                "type": "subworkflow",
                "name": "Greeter",
                "config": {"workflow_id": workflow_b_id, "pinned_version_id": pinned_version_id},
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
                "config": {"content": "Sub-workflow failed."},
                "position": {"x": 0, "y": 0},
            },
        ],
        "edges": [
            {"id": "e1", "source": "in1", "source_port": "default", "target": "sub1"},
            {"id": "e2", "source": "sub1", "source_port": "success", "target": "resp1"},
            {"id": "e3", "source": "sub1", "source_port": "failure", "target": "resp2"},
        ],
    }


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXTGEN_DB_PATH", str(tmp_path / "test.db"))
    init_db()
    with TestClient(app) as c:
        c.post("/api/auth/login", json={"password": "test-password"})
        yield c


def _run_workflow_a(client, workflow_name: str, answer: str) -> tuple[str, str]:
    """Invokes workflow_name via chat, answers its entry prompt, returns
    (run_id, final response content)."""
    with client.websocket_connect("/ws/chat") as ws:
        ws.receive_json()  # history
        ws.send_json({"type": "start_workflow", "payload": {"name": workflow_name}})
        ws.receive_json()  # status

        input_request = ws.receive_json()
        assert input_request["type"] == "input_request"
        run_id = input_request["payload"]["run_id"]

        ws.send_json({"type": "provide_input", "payload": {"run_id": run_id, "value": answer}})

        response_msg = ws.receive_json()
        assert response_msg["type"] == "response", response_msg
        return run_id, response_msg["payload"]["content"]


@requires_py311
def test_embedded_pinned_workflow_runs_end_to_end_and_ignores_later_updates(client):
    # Save Workflow B (v1) and activate it.
    b_res = client.post(
        "/api/workflows", json={"name": "greeter-b", "graph_json": _workflow_b_graph("Hello")}
    )
    assert b_res.status_code == 201, b_res.text
    workflow_b = b_res.json()
    b_v1_id = workflow_b["active_version_id"]

    # Save Workflow A, embedding B pinned to v1.
    a_res = client.post(
        "/api/workflows",
        json={
            "name": "caller-a",
            "graph_json": _workflow_a_graph(b_v1_id, workflow_b["id"]),
        },
    )
    assert a_res.status_code == 201, a_res.text

    run_id, content = _run_workflow_a(client, "caller-a", "Ada")
    assert content == "Hello, Ada!"

    # The Sub-workflow node's own execution is audited on A's run, same as
    # any other node.
    parent_executions = client.get(f"/api/runs/{run_id}/executions").json()
    sub_rows = [e for e in parent_executions if e["node_id"] == "sub1"]
    assert len(sub_rows) == 1
    assert sub_rows[0]["node_type"] == "subworkflow"
    assert sub_rows[0]["output_port"] == "success"
    assert sub_rows[0]["output"] == "Hello, Ada!"

    # The embedded run got its OWN Run row / audit trail (Q3's design
    # decision), not flattened into A's — find it via its distinct
    # workflow_version_id (B's v1) and confirm B's own in1/resp1 node
    # executions are tracked there, separately from A's own in1/resp1 nodes
    # (node ids are only unique within a single graph, not globally).
    all_runs = client.get("/api/runs").json()
    child_runs = [r for r in all_runs if r["workflow_version_id"] == b_v1_id]
    assert len(child_runs) == 1
    child_run_id = child_runs[0]["id"]
    assert child_run_id != run_id

    child_executions = client.get(f"/api/runs/{child_run_id}/executions").json()
    child_node_ids = {e["node_id"] for e in child_executions}
    assert child_node_ids == {"in1", "resp1"}
    child_resp_row = next(e for e in child_executions if e["node_id"] == "resp1")
    assert child_resp_row["output"] == "Hello, Ada!"

    # Now update Workflow B to a new version with different behavior — but do
    # NOT activate it (create_version() never auto-activates; irrelevant here
    # anyway, since the pin is by version id, not by "whatever's active").
    update_res = client.post(
        f"/api/workflows/{workflow_b['id']}/versions",
        json={"graph_json": _workflow_b_graph("Goodbye")},
    )
    assert update_res.status_code == 201, update_res.text

    # Re-running Workflow A must still reflect B's pinned v1 behavior.
    _, content_after_update = _run_workflow_a(client, "caller-a", "Ada")
    assert content_after_update == "Hello, Ada!"


@requires_py311
def test_pinned_version_no_longer_existing_routes_to_failure(client):
    b_res = client.post(
        "/api/workflows", json={"name": "greeter-b2", "graph_json": _workflow_b_graph("Hi")}
    )
    workflow_b = b_res.json()

    a_res = client.post(
        "/api/workflows",
        json={
            "name": "caller-a2",
            "graph_json": _workflow_a_graph("does-not-exist", workflow_b["id"]),
        },
    )
    assert a_res.status_code == 201, a_res.text

    _, content = _run_workflow_a(client, "caller-a2", "Ada")
    assert content == "Sub-workflow failed."
