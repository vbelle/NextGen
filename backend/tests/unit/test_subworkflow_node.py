"""Unit tests for subworkflow_node.py's guards that don't require a full
compiled child graph + checkpointer (see tests/integration/test_subworkflow_node.py
for the full end-to-end proof, T077). Covers the MAX_SUBWORKFLOW_DEPTH safety
cap and the "no parent run context" failure path, both of which fail fast
before ever touching the DB/checkpointer."""

from __future__ import annotations

import os

os.environ.setdefault("NEXTGEN_APP_PASSWORD", "test-password")
os.environ.setdefault("NEXTGEN_CREDENTIAL_KEY", "kQq4v2v7v3o5b1yqjq7c9m3n8p0r2s4t6u8w0x2y4z6=")

import pytest

from app.graph.nodes import subworkflow_node

BASE_STATE = {"variables": {}, "node_outputs": {}, "retry_counts": {}, "last_output_port": {}}


def _state(**overrides):
    state = {k: dict(v) if isinstance(v, dict) else v for k, v in BASE_STATE.items()}
    state.update(overrides)
    return state


@pytest.mark.asyncio
async def test_depth_limit_routes_to_failure_without_touching_db():
    state = _state(subworkflow_depth=subworkflow_node.MAX_SUBWORKFLOW_DEPTH)
    result = await subworkflow_node.execute(
        "sub1", {"workflow_id": "wf-x", "pinned_version_id": "ver-x"}, state
    )
    assert result["last_output_port"]["sub1"] == "failure"
    assert "nesting exceeded" in str(result["node_outputs"]["sub1"])


@pytest.mark.asyncio
async def test_missing_run_id_routes_to_failure():
    # No run_id in state at all — there's no parent Run row to attach a child
    # Run's chat_session_id to.
    state = _state()
    result = await subworkflow_node.execute(
        "sub1", {"workflow_id": "wf-x", "pinned_version_id": "ver-x"}, state
    )
    assert result["last_output_port"]["sub1"] == "failure"
    assert "parent run context" in str(result["node_outputs"]["sub1"])


def test_paused_helper():
    assert subworkflow_node._paused({"__interrupt__": [object()]}) is True
    assert subworkflow_node._paused({}) is False
    assert subworkflow_node._paused({"__interrupt__": []}) is False
