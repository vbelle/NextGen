"""Renders a workflow's graph_json as (1) an illustrative LangGraph builder
script — the same add_node/add_edge/add_conditional_edges calls
app/graph/compiler.py actually makes for this graph — followed by (2) the
real, unmodified source of every node type actually used, read straight off
disk via inspect.getsourcefile() rather than re-typed/summarized (Constitution
IV, "Visual Graph Is the Source of Truth" — this is a view onto that same
source of truth, not a second implementation of it; part (1) reuses
ALLOWED_SOURCE_PORTS from app/graph/schema.py rather than re-deriving which
node types are multi-port/terminal/single-output, and part (2) is a byte-for-
byte read of whatever's actually running, not hand-maintained). Together
these are literally the two things that get combined at runtime — compile_graph
does the exact same wiring, and each node type's own execute() is the exact
code that runs — so this is "what runs while the flow executes", not an
approximation of it.

Deliberately lenient rather than strictly validating (unlike
compile_graph): this is meant to work on a canvas mid-edit, before it's
necessarily save-able, so an unknown node type or a dangling edge renders
as best-effort text instead of raising."""

from __future__ import annotations

import inspect
from typing import Any

import app.graph.nodes  # noqa: F401 — import side effect: registers every implemented node type
from app.graph import tool_registry as tool_registry_module
from app.graph.schema import ALLOWED_SOURCE_PORTS, get_node_type


def generate_langgraph_code(graph_json: dict[str, Any]) -> str:
    nodes = {n["id"]: n for n in graph_json.get("nodes", []) if n.get("id")}
    edges = [e for e in graph_json.get("edges", []) if e.get("source") and e.get("target")]

    lines: list[str] = [
        "from langgraph.graph import StateGraph, START, END",
        "from app.graph.state import GraphState",
        "",
        "builder = StateGraph(GraphState)",
        "",
    ]

    # Tool nodes aren't graph steps — they're resolved into the LLM node's
    # bound_tools instead (see compiler.py's _resolve_bound_tools).
    tool_bindings: dict[str, list[str]] = {}
    for edge in edges:
        source = nodes.get(edge["source"])
        if source and source.get("type") == "tool":
            fn_name = source.get("config", {}).get("function_name") or source["id"]
            tool_bindings.setdefault(edge["target"], []).append(fn_name)

    for node_id, node in nodes.items():
        node_type = node.get("type", "unknown")
        if node_type == "tool":
            continue
        label = node.get("name") or node_id
        lines.append(f'# "{label}" ({node_type} node)')
        if node_id in tool_bindings:
            tools = ", ".join(tool_bindings[node_id])
            lines.append(f"# tools this node can call: {tools}")
        lines.append(f'builder.add_node("{node_id}", run_{node_type})')
        lines.append("")

    outgoing: dict[str, dict[str, list[str]]] = {}
    for edge in edges:
        outgoing.setdefault(edge["source"], {}).setdefault(
            edge.get("source_port", "default"), []
        ).append(edge["target"])

    for node_id, node in nodes.items():
        node_type = node.get("type", "unknown")
        if node_type == "tool":
            continue
        allowed_ports = ALLOWED_SOURCE_PORTS.get(node_type, {"default"})
        ports = outgoing.get(node_id, {})

        if allowed_ports == {"default"}:
            for target in ports.get("default", []):
                lines.append(f'builder.add_edge("{node_id}", "{target}")')
        elif not allowed_ports:
            lines.append(f'builder.add_edge("{node_id}", END)  # terminal node type')
        else:
            port_to_target = {port: targets[0] for port, targets in ports.items() if targets}
            if port_to_target:
                mapping = ", ".join(f'"{p}": "{t}"' for p, t in port_to_target.items())
                lines.append(
                    f'builder.add_conditional_edges("{node_id}", route_{node_id}, '
                    f"{{{mapping}}})"
                )
            else:
                lines.append(f"# {node_id}: no outgoing edges wired yet")

    lines.append("")
    has_incoming = {e["target"] for e in edges}
    entry_nodes = [
        nid for nid, n in nodes.items() if n.get("type") == "input" and nid not in has_incoming
    ]
    if entry_nodes:
        for entry_id in entry_nodes:
            lines.append(f'builder.add_edge(START, "{entry_id}")')
    else:
        lines.append("# no entry point yet — add an Input node with no incoming edge")

    lines.append("")
    lines.append("graph = builder.compile(checkpointer=checkpointer)")

    used_types = sorted({n.get("type", "unknown") for n in nodes.values()})
    if used_types:
        lines.append("")
        lines.append("# " + "=" * 70)
        lines.append("# Below: the real source of every node type used above, exactly as it")
        lines.append("# runs — not a summary. Each node type has one shared execute() function")
        lines.append("# (config-driven, not generated per node), read straight off disk.")
        lines.append("# " + "=" * 70)
        for node_type in used_types:
            lines.append("")
            lines.append(_render_node_type_source(node_type))
            if node_type == "tool":
                lines.append("")
                lines.append(_render_module_source(tool_registry_module))

    return "\n".join(lines)


def _render_node_type_source(node_type: str) -> str:
    try:
        definition = get_node_type(node_type)
        source_file = inspect.getsourcefile(definition.executor)
        with open(source_file, encoding="utf-8") as f:
            source = f.read()
    except Exception as exc:  # noqa: BLE001 — lenient by design, see module docstring
        return f"# ---- {node_type} node: could not read source ({exc}) ----"
    return f"# ---- {node_type} node — {source_file} ----\n{source}"


def _render_module_source(module: Any) -> str:
    try:
        source_file = inspect.getsourcefile(module)
        with open(source_file, encoding="utf-8") as f:
            source = f.read()
    except Exception as exc:  # noqa: BLE001 — lenient by design, see module docstring
        return f"# ---- {module.__name__}: could not read source ({exc}) ----"
    return f"# ---- {module.__name__} — {source_file} ----\n{source}"
