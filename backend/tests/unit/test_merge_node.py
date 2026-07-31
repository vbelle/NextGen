"""Unit tests for the Merge node (User Story 13): both its own execute()
combination logic and how the compiler resolves which upstream node_ids feed
it (app/graph/compiler.py's _resolve_merge_inputs — same pattern as
_resolve_bound_tools, tested the same way in test_tool_wiring_compiler.py).
No Input node / interrupt() involved, so this runs on any Python 3.10+."""

from __future__ import annotations

import os

os.environ.setdefault("NEXTGEN_APP_PASSWORD", "test-password")
os.environ.setdefault("NEXTGEN_CREDENTIAL_KEY", "kQq4v2v7v3o5b1yqjq7c9m3n8p0r2s4t6u8w0x2y4z6=")

import pytest

from app.graph.compiler import _resolve_merge_inputs, compile_graph
from app.graph.nodes import merge_node


def _state(node_outputs: dict) -> dict:
    return {"node_outputs": node_outputs}


@pytest.mark.asyncio
async def test_combine_object_merges_dict_contributions():
    state = _state({"a": {"x": 1}, "b": {"y": 2}})
    result = await merge_node.execute(
        "m1",
        {"strategy": "combine-object", "input_node_ids": ["a", "b"]},
        state,
    )
    assert result["node_outputs"]["m1"] == {"x": 1, "y": 2}
    assert result["last_output_port"]["m1"] == "default"


@pytest.mark.asyncio
async def test_combine_object_keys_non_dict_contribution_by_node_id():
    state = _state({"a": {"x": 1}, "b": "not a dict"})
    result = await merge_node.execute(
        "m1",
        {"strategy": "combine-object", "input_node_ids": ["a", "b"]},
        state,
    )
    assert result["node_outputs"]["m1"] == {"x": 1, "b": "not a dict"}


@pytest.mark.asyncio
async def test_concat_list_flattens_list_contributions():
    state = _state({"a": [1, 2], "b": [3]})
    result = await merge_node.execute(
        "m1",
        {"strategy": "concat-list", "input_node_ids": ["a", "b"]},
        state,
    )
    assert result["node_outputs"]["m1"] == [1, 2, 3]


@pytest.mark.asyncio
async def test_concat_list_appends_non_list_contribution_as_single_item():
    state = _state({"a": [1, 2], "b": 3})
    result = await merge_node.execute(
        "m1",
        {"strategy": "concat-list", "input_node_ids": ["a", "b"]},
        state,
    )
    assert result["node_outputs"]["m1"] == [1, 2, 3]


@pytest.mark.asyncio
async def test_missing_contribution_is_skipped_not_a_crash():
    # A branch that hasn't executed yet (or never will, e.g. its failure
    # output routed elsewhere per FR-020's acceptance scenario 2) simply
    # isn't in node_outputs — this must not KeyError.
    state = _state({"a": {"x": 1}})
    result = await merge_node.execute(
        "m1",
        {"strategy": "combine-object", "input_node_ids": ["a", "never_ran"]},
        state,
    )
    assert result["node_outputs"]["m1"] == {"x": 1}


GRAPH = {
    "nodes": [
        {
            "id": "a1",
            "type": "code",
            "name": "Branch A",
            "config": {"snippet": "result = {'x': 1}"},
            "position": {"x": 0, "y": 0},
        },
        {
            "id": "b1",
            "type": "code",
            "name": "Branch B",
            "config": {"snippet": "result = {'y': 2}"},
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
            "config": {"content": "oops"},
            "position": {"x": 0, "y": 0},
        },
    ],
    "edges": [
        {"id": "e1", "source": "a1", "source_port": "success", "target": "merge1"},
        {"id": "e2", "source": "a1", "source_port": "failure", "target": "resp_err"},
        {"id": "e3", "source": "b1", "source_port": "success", "target": "merge1"},
        {"id": "e4", "source": "b1", "source_port": "failure", "target": "resp_err"},
        {"id": "e5", "source": "merge1", "source_port": "default", "target": "resp1"},
    ],
}


def test_resolve_merge_inputs_finds_all_edges_into_merge_node():
    input_ids = _resolve_merge_inputs("merge1", GRAPH["edges"])
    assert input_ids == ["a1", "b1"]


def test_resolve_merge_inputs_ignores_edges_into_other_nodes():
    input_ids = _resolve_merge_inputs("resp1", GRAPH["edges"])
    assert input_ids == ["merge1"]


def test_compile_graph_includes_merge_node_with_resolved_input_ids():
    builder = compile_graph(GRAPH)
    assert "merge1" in builder.nodes
