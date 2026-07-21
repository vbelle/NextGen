"""Unit test for the generic per-node audit-logging wrapper in
app/graph/compiler.py's _make_node_fn.

This closes a gap discovered while building the Retry node (User Story 7):
quickstart.md Scenario 3 needs GET /runs/{id}/executions to show real
NodeExecution rows with attempt_count, but app/runtime/audit.py's
record_node_execution() — written during the Foundational phase (T023) — was
never actually called from anywhere. Fixed once, generically, in the node
function wrapper every compiled node goes through (consistent with how
conditional-edge routing is also handled once for every multi-port node type,
rather than duplicated per node module) instead of scoped to Retry specifically.

Tests _make_node_fn() directly rather than a full compiled graph, since a graph
needs at least one Input node to have any entry point at all, and Input nodes
need Python 3.11's interrupt() support — this test verifies the wrapper's own
logic without that dependency."""

from __future__ import annotations

import os

os.environ.setdefault("NEXTGEN_APP_PASSWORD", "test-password")
os.environ.setdefault("NEXTGEN_CREDENTIAL_KEY", "kQq4v2v7v3o5b1yqjq7c9m3n8p0r2s4t6u8w0x2y4z6=")

import pytest
from sqlmodel import Session, select

from app.db import get_engine, init_db
from app.graph.compiler import _make_node_fn
from app.models.run import NodeExecution

BASE_STATE = {"variables": {}, "node_outputs": {}, "retry_counts": {}, "last_output_port": {}}


def _state(**overrides):
    state = {k: dict(v) if isinstance(v, dict) else v for k, v in BASE_STATE.items()}
    state.update(overrides)
    return state


async def _fake_executor(*, node_id, config, state):
    return {
        "node_outputs": {node_id: "the-output", "__latest__": "the-output"},
        "last_output_port": {node_id: "success"},
    }


@pytest.mark.asyncio
async def test_writes_node_execution_row_when_run_id_present(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXTGEN_DB_PATH", str(tmp_path / "test.db"))
    init_db()

    node_fn = _make_node_fn("n1", "response", {}, _fake_executor)
    state = _state(run_id="run-abc", node_outputs={"__latest__": "the-input"})
    result = await node_fn(state)

    assert result["node_outputs"]["n1"] == "the-output"

    with Session(get_engine()) as session:
        rows = session.exec(select(NodeExecution).where(NodeExecution.run_id == "run-abc")).all()
    assert len(rows) == 1
    row = rows[0]
    assert row.node_id == "n1"
    assert row.node_type == "response"
    assert row.output_port == "success"
    assert row.attempt_count is None


@pytest.mark.asyncio
async def test_records_attempt_count_only_for_retry_node_type(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXTGEN_DB_PATH", str(tmp_path / "test.db"))
    init_db()

    async def fake_retry_executor(*, node_id, config, state):
        return {
            "retry_counts": {node_id: 2},
            "last_output_port": {node_id: "retry"},
        }

    node_fn = _make_node_fn("retry1", "retry", {}, fake_retry_executor)
    await node_fn(_state(run_id="run-xyz"))

    with Session(get_engine()) as session:
        row = session.exec(select(NodeExecution).where(NodeExecution.run_id == "run-xyz")).one()
    assert row.node_type == "retry"
    assert row.attempt_count == 2
    assert row.output_port == "retry"


@pytest.mark.asyncio
async def test_no_run_id_skips_audit_write_without_error():
    node_fn = _make_node_fn("n1", "response", {}, _fake_executor)
    # No NEXTGEN_DB_PATH/init_db() at all — if this tried to write, it would
    # blow up trying to open a DB that was never initialized for this test.
    result = await node_fn(_state())
    assert result["node_outputs"]["n1"] == "the-output"
