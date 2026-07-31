"""Integration test for a Merge node combining two parallel success branches
(T080, User Story 13), scripted against the real WebSocket endpoint like
test_loop_node.py. Input -> fans out to two Code nodes (Branch A, Branch B)
running as true LangGraph-parallel siblings -> both success outputs feed one
Merge node -> Response shows the combined result. Requires Python 3.11 for
the entry Input node's interrupt(); see tests/unit/test_merge_node.py for the
Merge node's own combination logic and compiler wiring, which doesn't need
that."""

from __future__ import annotations

import json
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

GRAPH = {
    "nodes": [
        {
            "id": "in1",
            "type": "input",
            "name": "Kick off",
            "config": {"prompt": "Go?"},
            "position": {"x": 0, "y": 0},
        },
        {
            "id": "a1",
            "type": "code",
            "name": "Branch A",
            "config": {"snippet": "result = {'a': 1}"},
            "position": {"x": 0, "y": 0},
        },
        {
            "id": "b1",
            "type": "code",
            "name": "Branch B",
            "config": {"snippet": "result = {'b': 2}"},
            "position": {"x": 0, "y": 0},
        },
        {
            "id": "merge1",
            "type": "merge",
            "name": "Combine",
            "config": {"strategy": "combine-object"},
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
            "id": "resp_err",
            "type": "response",
            "name": "Error",
            "config": {"content": "Something went wrong."},
            "position": {"x": 0, "y": 0},
        },
    ],
    "edges": [
        {"id": "e1", "source": "in1", "source_port": "default", "target": "a1"},
        {"id": "e2", "source": "in1", "source_port": "default", "target": "b1"},
        {"id": "e3", "source": "a1", "source_port": "success", "target": "merge1"},
        {"id": "e4", "source": "a1", "source_port": "failure", "target": "resp_err"},
        {"id": "e5", "source": "b1", "source_port": "success", "target": "merge1"},
        {"id": "e6", "source": "b1", "source_port": "failure", "target": "resp_err"},
        {"id": "e7", "source": "merge1", "source_port": "default", "target": "resp1"},
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
def test_merge_waits_for_both_branches_and_combines(client):
    create_res = client.post("/api/workflows", json={"name": "merge-test", "graph_json": GRAPH})
    assert create_res.status_code == 201, create_res.text

    with client.websocket_connect("/ws/chat") as ws:
        ws.receive_json()  # history
        ws.send_json({"type": "start_workflow", "payload": {"name": "merge-test"}})
        ws.receive_json()  # status

        input_request = ws.receive_json()
        assert input_request["type"] == "input_request"
        run_id = input_request["payload"]["run_id"]

        ws.send_json({"type": "provide_input", "payload": {"run_id": run_id, "value": "go"}})

        response_msg = ws.receive_json()
        assert response_msg["type"] == "response"
        assert response_msg["payload"]["content"] == json.dumps({"a": 1, "b": 2})

    executions = client.get(f"/api/runs/{run_id}/executions").json()
    merge_rows = [e for e in executions if e["node_id"] == "merge1"]
    assert len(merge_rows) == 1, "Merge node must run exactly once, after both branches complete"
    assert merge_rows[0]["output"] == {"a": 1, "b": 2}

    # Both branches actually ran (not skipped, not run more than once each).
    for branch_id in ("a1", "b1"):
        branch_rows = [e for e in executions if e["node_id"] == branch_id]
        assert len(branch_rows) == 1


def test_merge_node_with_no_incoming_edges_fails_validation(client):
    bad_graph = {
        "nodes": [
            {
                "id": "in1",
                "type": "input",
                "name": "Ask",
                "config": {"prompt": "hi"},
                "position": {"x": 0, "y": 0},
            },
            {
                "id": "merge1",
                "type": "merge",
                "name": "Combine",
                "config": {"strategy": "combine-object"},
                "position": {"x": 0, "y": 0},
            },
            {
                "id": "resp1",
                "type": "response",
                "name": "Show",
                "config": {"content": "{{previous}}"},
                "position": {"x": 0, "y": 0},
            },
        ],
        "edges": [
            {"id": "e1", "source": "in1", "source_port": "default", "target": "resp1"},
        ],
    }
    res = client.post("/api/workflows", json={"name": "bad-merge", "graph_json": bad_graph})
    assert res.status_code == 422
    errors = res.json()["detail"]["errors"]
    assert any("Merge node has no incoming edges" in e["issue"] for e in errors)
