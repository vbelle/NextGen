"""Unit tests for the Retry node's execution function — calls execute() directly,
no compiled graph needed (Retry itself has no dependency on interrupt()/Input
nodes at all). See tests/integration/test_retry_node.py for the full end-to-end
proof (T060, quickstart Scenario 3) that requires Python 3.11 only because ITS
graph happens to need an entry Input node."""

from __future__ import annotations

import os

os.environ.setdefault("NEXTGEN_APP_PASSWORD", "test-password")
os.environ.setdefault("NEXTGEN_CREDENTIAL_KEY", "kQq4v2v7v3o5b1yqjq7c9m3n8p0r2s4t6u8w0x2y4z6=")

import pytest

from app.graph.nodes import retry_node

BASE_STATE = {"variables": {}, "node_outputs": {}, "retry_counts": {}, "last_output_port": {}}


def _state(**overrides):
    state = {k: dict(v) if isinstance(v, dict) else v for k, v in BASE_STATE.items()}
    state.update(overrides)
    return state


@pytest.mark.asyncio
async def test_first_failure_routes_to_retry_when_under_max():
    state = _state()
    result = await retry_node.execute("retry1", {"max_attempts": 3}, state)
    assert result["last_output_port"]["retry1"] == "retry"
    assert result["retry_counts"]["retry1"] == 1


@pytest.mark.asyncio
async def test_exactly_max_attempts_then_gives_up():
    """SC-008: with max_attempts=3, the 1st and 2nd calls say 'retry' (leading to
    attempts 2 and 3), and the 3rd call — after the 3rd failure — gives up.
    Never a 4th attempt."""
    state = _state()
    ports = []
    counts = {}
    for _ in range(3):
        state = _state(retry_counts=counts)
        result = await retry_node.execute("retry1", {"max_attempts": 3}, state)
        ports.append(result["last_output_port"]["retry1"])
        counts = result["retry_counts"]

    assert ports == ["retry", "retry", "give-up"]
    assert counts["retry1"] == 3


@pytest.mark.asyncio
async def test_max_attempts_one_gives_up_immediately():
    state = _state()
    result = await retry_node.execute("retry1", {"max_attempts": 1}, state)
    assert result["last_output_port"]["retry1"] == "give-up"
    assert result["retry_counts"]["retry1"] == 1


@pytest.mark.asyncio
async def test_default_max_attempts_is_three():
    state = _state()
    result = await retry_node.execute("retry1", {}, state)
    assert result["last_output_port"]["retry1"] == "retry"


@pytest.mark.asyncio
async def test_does_not_clobber_latest_output():
    """The failed node's actual output (e.g. an API error) must stay visible as
    {{previous}} for a give-up path's Response node to reference — Retry only
    adds its own node_outputs[own_id], never touches __latest__."""
    state = _state(node_outputs={"__latest__": {"error": "connection refused"}})
    result = await retry_node.execute("retry1", {"max_attempts": 1}, state)
    assert "__latest__" not in result.get("node_outputs", {})


@pytest.mark.asyncio
async def test_retry_counts_keyed_by_own_id_not_shared_across_retry_nodes():
    state = _state(retry_counts={"other_retry": 5})
    result = await retry_node.execute("retry1", {"max_attempts": 3}, state)
    assert result["retry_counts"] == {"retry1": 1}
