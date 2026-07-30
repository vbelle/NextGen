"""Unit tests for the Variable node's execution function — calls execute() directly
(no compiled graph, no Input node), so these run on this sandbox's Python 3.10.
See tests/integration/test_variable_scope.py for the full-graph, non-adjacent-node
proof (T051), which needs Python 3.11 for its entry Input node's interrupt()."""

from __future__ import annotations

import json
import os

os.environ.setdefault("NEXTGEN_APP_PASSWORD", "test-password")
os.environ.setdefault("NEXTGEN_CREDENTIAL_KEY", "kQq4v2v7v3o5b1yqjq7c9m3n8p0r2s4t6u8w0x2y4z6=")

import pytest
from sqlmodel import Session, select

from app.db import get_engine, init_db
from app.graph.nodes import variable_node
from app.models.variable import RunVariable

BASE_STATE = {"variables": {}, "node_outputs": {}, "retry_counts": {}, "last_output_port": {}}


def _state(**overrides):
    state = {k: dict(v) if isinstance(v, dict) else v for k, v in BASE_STATE.items()}
    state.update(overrides)
    return state


@pytest.mark.asyncio
async def test_captures_previous_output_under_given_name():
    state = _state(node_outputs={"__latest__": "Ada"})
    result = await variable_node.execute("var1", {"name": "username"}, state)
    assert result["variables"] == {"username": "Ada"}
    assert result["node_outputs"]["var1"] == "Ada"
    assert result["node_outputs"]["__latest__"] == "Ada"
    assert result["last_output_port"]["var1"] == "default"


@pytest.mark.asyncio
async def test_no_run_id_skips_db_write_without_error():
    # No "run_id" key in state at all — must not crash trying to persist an
    # audit row for a run that (in this unit-test context) doesn't exist.
    state = _state(node_outputs={"__latest__": "value"})
    result = await variable_node.execute("var1", {"name": "x"}, state)
    assert result["variables"] == {"x": "value"}


@pytest.mark.asyncio
async def test_writes_run_variable_audit_row_when_run_id_present(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXTGEN_DB_PATH", str(tmp_path / "test.db"))
    init_db()

    state = _state(run_id="run-123", node_outputs={"__latest__": {"nested": True}})
    await variable_node.execute("var1", {"name": "payload"}, state)

    with Session(get_engine()) as session:
        rows = session.exec(select(RunVariable).where(RunVariable.run_id == "run-123")).all()
    assert len(rows) == 1
    assert rows[0].name == "payload"
    assert json.loads(rows[0].value_json) == {"nested": True}
