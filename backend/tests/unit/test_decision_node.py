"""Unit tests for the Decision node's execution function (T045/T046 — User Story 3).

Deliberately calls decision_node.execute() directly rather than compiling/running a
full graph: a graph exercising Decision genuinely (Input -> Decision -> two Responses)
would need an Input node, and every Input node calls LangGraph's interrupt(), which
needs Python 3.11 in an async context (see integration/test_core_loop.py). This test
verifies the same branching logic — true/false in both directions, each operator, and
the {{variable}}-not-set failure case — without depending on interrupt(), so it runs
on this sandbox's Python 3.10 too."""

from __future__ import annotations

import os

os.environ.setdefault("NEXTGEN_APP_PASSWORD", "test-password")
os.environ.setdefault("NEXTGEN_CREDENTIAL_KEY", "kQq4v2v7v3o5b1yqjq7c9m3n8p0r2s4t6u8w0x2y4z6=")

import pytest

from app.graph.nodes import decision_node
from app.graph.templating import VariableNotSetError

BASE_STATE = {"variables": {}, "node_outputs": {}, "retry_counts": {}, "last_output_port": {}}


def _state(**overrides):
    state = {k: dict(v) if isinstance(v, dict) else v for k, v in BASE_STATE.items()}
    state.update(overrides)
    return state


@pytest.mark.asyncio
async def test_truthy_routes_true_on_nonempty_previous():
    state = _state(node_outputs={"__latest__": "yes"})
    result = await decision_node.execute(
        "dec1", {"left": "{{previous}}", "operator": "truthy"}, state
    )
    assert result["last_output_port"]["dec1"] == "true"


@pytest.mark.asyncio
async def test_truthy_routes_false_on_falsy_string():
    state = _state(node_outputs={"__latest__": "false"})
    result = await decision_node.execute(
        "dec1", {"left": "{{previous}}", "operator": "truthy"}, state
    )
    assert result["last_output_port"]["dec1"] == "false"


@pytest.mark.asyncio
async def test_equals_matches_variable_against_literal():
    state = _state(variables={"status": "approved"})
    result = await decision_node.execute(
        "dec1", {"left": "{{status}}", "operator": "equals", "right": "approved"}, state
    )
    assert result["last_output_port"]["dec1"] == "true"


@pytest.mark.asyncio
async def test_equals_mismatch_routes_false():
    state = _state(variables={"status": "pending"})
    result = await decision_node.execute(
        "dec1", {"left": "{{status}}", "operator": "equals", "right": "approved"}, state
    )
    assert result["last_output_port"]["dec1"] == "false"


@pytest.mark.asyncio
async def test_contains_checks_substring():
    state = _state(node_outputs={"__latest__": "the answer is yes indeed"})
    result = await decision_node.execute(
        "dec1", {"left": "{{previous}}", "operator": "contains", "right": "yes"}, state
    )
    assert result["last_output_port"]["dec1"] == "true"


@pytest.mark.asyncio
async def test_gt_numeric_comparison_true():
    state = _state(node_outputs={"__latest__": "42"})
    result = await decision_node.execute(
        "dec1", {"left": "{{previous}}", "operator": "gt", "right": "10"}, state
    )
    assert result["last_output_port"]["dec1"] == "true"


@pytest.mark.asyncio
async def test_lt_numeric_comparison_false():
    state = _state(node_outputs={"__latest__": "42"})
    result = await decision_node.execute(
        "dec1", {"left": "{{previous}}", "operator": "lt", "right": "10"}, state
    )
    assert result["last_output_port"]["dec1"] == "false"


@pytest.mark.asyncio
async def test_gt_on_non_numeric_value_raises():
    state = _state(node_outputs={"__latest__": "not-a-number"})
    with pytest.raises(ValueError, match="requires numeric values"):
        await decision_node.execute(
            "dec1", {"left": "{{previous}}", "operator": "gt", "right": "10"}, state
        )


@pytest.mark.asyncio
async def test_unset_variable_raises_not_a_silent_false():
    """FR-025's spirit applied to Decision: an unset {{variable}} must be a loud
    failure, never silently coerced to the 'false' branch."""
    state = _state()
    with pytest.raises(VariableNotSetError):
        await decision_node.execute("dec1", {"left": "{{missing}}", "operator": "truthy"}, state)
