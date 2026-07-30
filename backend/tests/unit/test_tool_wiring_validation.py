"""Unit tests for validate_graph()'s Rule 4c (User Story 11): Tool nodes must
never have an incoming edge and every outgoing edge must target an `llm`
node. See app/graph/validation.py and app/graph/nodes/tool_node.py's module
docstring for why."""

from __future__ import annotations

import os

os.environ.setdefault("NEXTGEN_APP_PASSWORD", "test-password")
os.environ.setdefault("NEXTGEN_CREDENTIAL_KEY", "kQq4v2v7v3o5b1yqjq7c9m3n8p0r2s4t6u8w0x2y4z6=")

from app.graph.validation import validate_graph

BASE_NODES = [
    {
        "id": "in1",
        "type": "input",
        "name": "Ask",
        "config": {"prompt": "hi?"},
        "position": {"x": 0, "y": 0},
    },
    {
        "id": "tool1",
        "type": "tool",
        "name": "Add",
        "config": {
            "function_name": "add",
            "description": "Adds",
            "implementation_ref": "calculator",
        },
        "position": {"x": 0, "y": 0},
    },
    {
        "id": "llm1",
        "type": "llm",
        "name": "Answer",
        "config": {"model": "llama3.2", "prompt": "{{previous}}"},
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
]

BASE_EDGES = [
    {"id": "e1", "source": "in1", "source_port": "default", "target": "llm1"},
    {"id": "e2", "source": "tool1", "source_port": "default", "target": "llm1"},
    {"id": "e3", "source": "llm1", "source_port": "success", "target": "resp1"},
    {"id": "e4", "source": "llm1", "source_port": "failure", "target": "resp2"},
]


def test_valid_tool_wiring_passes():
    result = validate_graph({"nodes": BASE_NODES, "edges": BASE_EDGES})
    tool_issues = [i for i in result.issues if i.node_id == "tool1"]
    assert tool_issues == []


def test_tool_node_with_incoming_edge_rejected():
    edges = BASE_EDGES + [
        {"id": "e5", "source": "in1", "source_port": "default", "target": "tool1"}
    ]
    result = validate_graph({"nodes": BASE_NODES, "edges": edges})
    messages = [i.message for i in result.issues if i.node_id == "tool1"]
    assert any("incoming edges" in m for m in messages)


def test_tool_node_with_no_outgoing_edge_rejected():
    edges = [e for e in BASE_EDGES if e["id"] != "e2"]
    result = validate_graph({"nodes": BASE_NODES, "edges": edges})
    messages = [i.message for i in result.issues if i.node_id == "tool1"]
    assert any("not wired to any LLM node" in m for m in messages)


def test_tool_node_targeting_non_llm_node_rejected():
    nodes = BASE_NODES
    edges = [e for e in BASE_EDGES if e["id"] != "e2"] + [
        {"id": "e2", "source": "tool1", "source_port": "default", "target": "resp1"}
    ]
    result = validate_graph({"nodes": nodes, "edges": edges})
    messages = [i.message for i in result.issues if i.node_id == "tool1"]
    assert any("must target an LLM node" in m for m in messages)
