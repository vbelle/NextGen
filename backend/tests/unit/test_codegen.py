"""Unit tests for app/graph/codegen.py — the "View code" panel's LangGraph
tab. These check the generated text mirrors what compiler.py would actually
build for the same graph_json (node registration, edge routing, tool
bindings, entry points), not that it's valid/executable Python by itself."""

from __future__ import annotations

import os

os.environ.setdefault("NEXTGEN_APP_PASSWORD", "test-password")
os.environ.setdefault("NEXTGEN_CREDENTIAL_KEY", "kQq4v2v7v3o5b1yqjq7c9m3n8p0r2s4t6u8w0x2y4z6=")

from app.graph.codegen import generate_langgraph_code


def _graph(nodes, edges):
    return {"nodes": nodes, "edges": edges}


def test_linear_graph_adds_nodes_and_edges_with_entry_point():
    graph = _graph(
        nodes=[
            {"id": "in1", "type": "input", "name": "Ask", "config": {}},
            {"id": "res1", "type": "response", "name": "Say", "config": {}},
        ],
        edges=[
            {"id": "e1", "source": "in1", "target": "res1", "source_port": "default"},
        ],
    )
    code = generate_langgraph_code(graph)
    assert 'builder.add_node("in1", run_input)' in code
    assert 'builder.add_node("res1", run_response)' in code
    assert 'builder.add_edge("in1", "res1")' in code
    assert 'builder.add_edge("res1", END)' in code  # terminal node type
    assert 'builder.add_edge(START, "in1")' in code


def test_multi_port_node_uses_conditional_edges():
    graph = _graph(
        nodes=[
            {"id": "llm1", "type": "llm", "name": "Ask model", "config": {}},
            {"id": "ok", "type": "response", "name": "OK", "config": {}},
            {"id": "fail", "type": "response", "name": "Fail", "config": {}},
        ],
        edges=[
            {"id": "e1", "source": "llm1", "target": "ok", "source_port": "success"},
            {"id": "e2", "source": "llm1", "target": "fail", "source_port": "failure"},
        ],
    )
    code = generate_langgraph_code(graph)
    assert 'builder.add_conditional_edges("llm1", route_llm1,' in code
    assert '"success": "ok"' in code
    assert '"failure": "fail"' in code


def test_tool_node_is_not_added_but_shows_as_binding_comment():
    graph = _graph(
        nodes=[
            {"id": "llm1", "type": "llm", "name": "Ask model", "config": {}},
            {
                "id": "tool1",
                "type": "tool",
                "name": "Weather",
                "config": {"function_name": "get_weather"},
            },
        ],
        edges=[
            {"id": "e1", "source": "tool1", "target": "llm1", "source_port": "default"},
        ],
    )
    code = generate_langgraph_code(graph)
    assert 'builder.add_node("tool1"' not in code
    assert "tools this node can call: get_weather" in code


def test_no_entry_point_notes_it_instead_of_crashing():
    graph = _graph(
        nodes=[{"id": "res1", "type": "response", "name": "Say", "config": {}}],
        edges=[],
    )
    code = generate_langgraph_code(graph)
    assert "no entry point yet" in code


def test_empty_graph_does_not_raise():
    code = generate_langgraph_code({"nodes": [], "edges": []})
    assert "builder = StateGraph(GraphState)" in code


def test_empty_graph_has_no_node_source_section():
    # Nothing to render source for — this must not append an empty/broken
    # "used_types" section.
    code = generate_langgraph_code({"nodes": [], "edges": []})
    assert "node type used above" not in code


def test_includes_real_source_of_every_node_type_used():
    graph = _graph(
        nodes=[
            {"id": "in1", "type": "input", "name": "Ask", "config": {}},
            {"id": "res1", "type": "response", "name": "Say", "config": {}},
        ],
        edges=[
            {"id": "e1", "source": "in1", "target": "res1", "source_port": "default"},
        ],
    )
    code = generate_langgraph_code(graph)
    # Real, distinctive lines from the actual files — not a summary/rewrite.
    assert 'register_node_type("input"' in code
    assert 'register_node_type("response"' in code
    # A node type NOT used in this graph shouldn't have its source pulled in.
    assert 'register_node_type("llm"' not in code


def test_tool_node_pulls_in_tool_registry_source_too():
    graph = _graph(
        nodes=[
            {"id": "llm1", "type": "llm", "name": "Ask model", "config": {}},
            {
                "id": "tool1",
                "type": "tool",
                "name": "Weather",
                "config": {"function_name": "get_weather"},
            },
        ],
        edges=[
            {"id": "e1", "source": "tool1", "target": "llm1", "source_port": "default"},
        ],
    )
    code = generate_langgraph_code(graph)
    assert 'register_node_type("llm"' in code
    assert 'register_node_type("tool"' in code
    # tool_registry.py itself — where implementation_ref actually resolves.
    assert "_REGISTRY: dict[str, ToolImplementation]" in code


def test_unknown_node_type_source_section_is_lenient_not_a_crash():
    graph = _graph(
        nodes=[{"id": "x1", "type": "not_a_real_type", "name": "Mystery", "config": {}}],
        edges=[],
    )
    code = generate_langgraph_code(graph)
    assert "could not read source" in code
