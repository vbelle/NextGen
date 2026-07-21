"""Compiles a workflow's graph_json into a LangGraph StateGraph. See research.md §1.

This is the concrete expression of Constitution IV ("Visual Graph Is the Source of
Truth") — every execution path a Run can take is derived directly from the nodes/edges
the canvas saved, with no hand-written workflow code bypassing it.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from langgraph.graph import END, START, StateGraph
from sqlmodel import Session

import app.graph.nodes  # noqa: F401 — import side effect: registers every implemented node type
from app.db import get_engine
from app.graph.schema import ALLOWED_SOURCE_PORTS, get_node_type
from app.graph.state import GraphState
from app.runtime.audit import record_node_execution


def _make_node_fn(node_id: str, node_type: str, config: dict, executor):
    async def _node_fn(state: GraphState) -> dict:
        started_at = datetime.now(timezone.utc)
        input_data = state.get("node_outputs", {}).get("__latest__")
        result = await executor(node_id=node_id, config=config, state=state)

        # Constitution VII ("Every Run Is Audited", FR-029/SC-007): one row per
        # node execution, written immediately — not batched at run end, and not
        # skippable per node type, which is why this lives here rather than in
        # each node module (a node author forgetting to call it would silently
        # break the audit trail for just that type).
        run_id = state.get("run_id")
        if run_id:
            output_port = result.get("last_output_port", {}).get(node_id, "default")
            output_data = result.get("node_outputs", {}).get(node_id)
            attempt_count = (
                result.get("retry_counts", {}).get(node_id) if node_type == "retry" else None
            )
            with Session(get_engine()) as session:
                record_node_execution(
                    session,
                    run_id=run_id,
                    node_id=node_id,
                    node_type=node_type,
                    output_port=output_port,
                    input_data=input_data,
                    output_data=output_data,
                    started_at=started_at,
                    attempt_count=attempt_count,
                )
        return result

    _node_fn.__name__ = f"{node_type}__{node_id}"
    return _node_fn


def _make_router(node_id: str):
    def _router(state: GraphState) -> str:
        port = state.get("last_output_port", {}).get(node_id, "default")
        return port

    return _router


def compile_graph(graph_json: dict[str, Any]):
    """Returns an uncompiled StateGraph builder. Caller attaches a checkpointer and
    calls .compile() — kept separate so tests can compile without a checkpointer."""
    nodes = {n["id"]: n for n in graph_json.get("nodes", [])}
    edges = graph_json.get("edges", [])

    builder = StateGraph(GraphState)

    for node_id, node in nodes.items():
        node_type = node["type"]
        definition = get_node_type(node_type)  # raises ValueError on unregistered type
        config = definition.config_model(**node.get("config", {})).model_dump()
        builder.add_node(node_id, _make_node_fn(node_id, node_type, config, definition.executor))

    # Group outgoing edges per node/port to build routing tables.
    outgoing: dict[str, dict[str, list[str]]] = {}
    for edge in edges:
        outgoing.setdefault(edge["source"], {}).setdefault(
            edge.get("source_port", "default"), []
        ).append(edge["target"])

    for node_id, node in nodes.items():
        node_type = node["type"]
        ports = outgoing.get(node_id, {})
        allowed_ports = ALLOWED_SOURCE_PORTS.get(node_type, {"default"})

        if allowed_ports == {"default"}:
            # Single-output node type: plain edges, one per target (supports fan-out
            # for parallel branches feeding a later Merge node).
            for target in ports.get("default", []):
                builder.add_edge(node_id, target)
        elif not allowed_ports:
            # Terminal node type (response): route straight to END.
            builder.add_edge(node_id, END)
        else:
            # Multi-port node type (decision/dual-output/retry): conditional routing
            # keyed by whichever port the node function reported firing.
            port_to_target = {port: targets[0] for port, targets in ports.items() if targets}
            if port_to_target:
                builder.add_conditional_edges(node_id, _make_router(node_id), port_to_target)

    # Entry points: every Input node with no incoming edge starts the graph (FR-007).
    has_incoming = {edge["target"] for edge in edges}
    entry_nodes = [
        nid for nid, n in nodes.items() if n["type"] == "input" and nid not in has_incoming
    ]
    for entry_id in entry_nodes:
        builder.add_edge(START, entry_id)

    return builder
