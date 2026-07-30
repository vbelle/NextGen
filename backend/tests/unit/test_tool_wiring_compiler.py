"""Unit tests for how the compiler resolves Tool <-> LLM wiring (User Story
11): a Tool node's edge to an LLM node is a binding, not an execution edge —
see app/graph/compiler.py's _resolve_bound_tools() and its node/edge-loop
skips for node_type == "tool". Tested directly against compile_graph()'s
builder (no Input node / interrupt() involved, so this runs on any Python
3.10+, unlike the full graph-execution integration test)."""

from __future__ import annotations

import os

os.environ.setdefault("NEXTGEN_APP_PASSWORD", "test-password")
os.environ.setdefault("NEXTGEN_CREDENTIAL_KEY", "kQq4v2v7v3o5b1yqjq7c9m3n8p0r2s4t6u8w0x2y4z6=")

from app.graph.compiler import _resolve_bound_tools, compile_graph

GRAPH = {
    "nodes": [
        {
            "id": "tool1",
            "type": "tool",
            "name": "Add",
            "config": {
                "function_name": "add",
                "description": "Adds two numbers",
                "implementation_ref": "calculator",
            },
            "position": {"x": 0, "y": 0},
        },
        {
            "id": "llm1",
            "type": "llm",
            "name": "Answer",
            "config": {"model": "llama3.2", "prompt": "hi"},
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
            "config": {"content": "oops"},
            "position": {"x": 0, "y": 0},
        },
    ],
    "edges": [
        {"id": "e1", "source": "tool1", "source_port": "default", "target": "llm1"},
        {"id": "e2", "source": "llm1", "source_port": "success", "target": "resp1"},
        {"id": "e3", "source": "llm1", "source_port": "failure", "target": "resp2"},
    ],
}


def test_resolve_bound_tools_finds_tool_edges_into_llm_node():
    nodes = {n["id"]: n for n in GRAPH["nodes"]}
    bound = _resolve_bound_tools("llm1", nodes, GRAPH["edges"])
    assert len(bound) == 1
    assert bound[0]["node_id"] == "tool1"
    assert bound[0]["function_name"] == "add"
    assert bound[0]["implementation_ref"] == "calculator"


def test_resolve_bound_tools_ignores_non_tool_sources():
    nodes = {n["id"]: n for n in GRAPH["nodes"]}
    bound = _resolve_bound_tools("resp1", nodes, GRAPH["edges"])
    assert bound == []


def test_compile_graph_excludes_tool_node_from_state_graph():
    builder = compile_graph(GRAPH)
    assert "tool1" not in builder.nodes
    assert "llm1" in builder.nodes
