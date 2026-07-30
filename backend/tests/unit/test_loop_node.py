"""Unit tests for the Loop node's execution function — calls execute() directly,
simulating the sequence of calls LangGraph's cycle would produce (init, then one
re-entry per completed body iteration, then the final "done" call) without
needing a compiled graph or interrupt(). See tests/integration/test_loop_node.py
for the full end-to-end proof (T067) through a real compiled graph, which does
need Python 3.11 because its entry point is an Input node."""

from __future__ import annotations

import os

os.environ.setdefault("NEXTGEN_APP_PASSWORD", "test-password")
os.environ.setdefault("NEXTGEN_CREDENTIAL_KEY", "kQq4v2v7v3o5b1yqjq7c9m3n8p0r2s4t6u8w0x2y4z6=")

import pytest

from app.graph.nodes import loop_node
from app.graph.templating import VariableNotSetError

BASE_STATE = {
    "variables": {},
    "node_outputs": {},
    "retry_counts": {},
    "loop_state": {},
    "last_output_port": {},
}


def _state(**overrides):
    state = {k: dict(v) if isinstance(v, dict) else v for k, v in BASE_STATE.items()}
    state.update(overrides)
    return state


async def _run_full_loop(items: list, body_double=lambda x: x * 2):
    """Simulates the real call sequence: Loop entry -> (body runs) -> Loop
    re-entry -> ... -> Loop "done". Returns the final result dict."""
    state = _state(variables={"items": items})
    config = {"collection_ref": "{{items}}", "body_start_node_id": "body1"}

    result = await loop_node.execute("loop1", config, state)
    while result["last_output_port"]["loop1"] == "body":
        # Simulate the body node running on the current item.
        current_item = result["node_outputs"]["loop1"]
        body_output = body_double(current_item)
        state = _state(
            variables={"items": items},
            loop_state=result["loop_state"],
            node_outputs={"__latest__": body_output},
        )
        result = await loop_node.execute("loop1", config, state)
    return result


@pytest.mark.asyncio
async def test_iterates_every_item_and_aggregates_results():
    result = await _run_full_loop([1, 2, 3])
    assert result["last_output_port"]["loop1"] == "done"
    assert result["node_outputs"]["loop1"] == [2, 4, 6]


@pytest.mark.asyncio
async def test_empty_collection_goes_straight_to_done():
    result = await _run_full_loop([])
    assert result["last_output_port"]["loop1"] == "done"
    assert result["node_outputs"]["loop1"] == []


@pytest.mark.asyncio
async def test_single_item_collection():
    result = await _run_full_loop(["only"], body_double=lambda x: x.upper())
    assert result["last_output_port"]["loop1"] == "done"
    assert result["node_outputs"]["loop1"] == ["ONLY"]


@pytest.mark.asyncio
async def test_first_entry_exposes_current_item_as_previous():
    state = _state(variables={"items": ["a", "b"]})
    config = {"collection_ref": "{{items}}", "body_start_node_id": "body1"}
    result = await loop_node.execute("loop1", config, state)
    assert result["last_output_port"]["loop1"] == "body"
    assert result["node_outputs"]["loop1"] == "a"
    assert result["node_outputs"]["__latest__"] == "a"
    assert result["loop_state"]["loop1"] == {"items": ["a", "b"], "index": 0, "results": []}


@pytest.mark.asyncio
async def test_collection_ref_resolves_from_previous_not_just_variables():
    state = _state(node_outputs={"__latest__": [10, 20]})
    config = {"collection_ref": "{{previous}}", "body_start_node_id": "body1"}
    result = await loop_node.execute("loop1", config, state)
    assert result["node_outputs"]["loop1"] == 10


@pytest.mark.asyncio
async def test_non_list_collection_raises_type_error():
    state = _state(variables={"items": "not-a-list"})
    config = {"collection_ref": "{{items}}", "body_start_node_id": "body1"}
    with pytest.raises(TypeError, match="not a list"):
        await loop_node.execute("loop1", config, state)


@pytest.mark.asyncio
async def test_unset_variable_collection_ref_raises():
    state = _state()
    config = {"collection_ref": "{{missing}}", "body_start_node_id": "body1"}
    with pytest.raises(VariableNotSetError):
        await loop_node.execute("loop1", config, state)


@pytest.mark.asyncio
async def test_collection_ref_embedded_in_text_is_rejected():
    """resolve_value_reference requires a WHOLE {{name}} placeholder — Loop
    needs the actual list object, not a rendered string."""
    state = _state(variables={"items": [1, 2]})
    config = {"collection_ref": "items: {{items}}", "body_start_node_id": "body1"}
    with pytest.raises(ValueError, match="exactly"):
        await loop_node.execute("loop1", config, state)


@pytest.mark.asyncio
async def test_does_not_reresolve_collection_on_reentry():
    """collection_ref often references {{previous}}, which changes after the
    first body iteration runs — the resolved list must be captured once, not
    re-read from a now-different {{previous}} on every re-entry."""
    state = _state(node_outputs={"__latest__": [1, 2]})
    config = {"collection_ref": "{{previous}}", "body_start_node_id": "body1"}
    first = await loop_node.execute("loop1", config, state)
    assert first["node_outputs"]["loop1"] == 1

    # Body "runs" and produces something unrelated to the original list.
    state2 = _state(
        loop_state=first["loop_state"], node_outputs={"__latest__": "body ran on item 1"}
    )
    second = await loop_node.execute("loop1", config, state2)
    # Still iterating the ORIGINAL [1, 2], not re-resolving from the changed
    # {{previous}} ("body ran on item 1").
    assert second["node_outputs"]["loop1"] == 2
