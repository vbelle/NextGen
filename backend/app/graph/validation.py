"""Save-time graph_json validation. See contracts/graph-schema.md §Save-time validation, FR-003."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.graph.schema import ALLOWED_SOURCE_PORTS, DUAL_OUTPUT_TYPES


@dataclass
class ValidationIssue:
    node_id: str | None
    edge_id: str | None
    message: str


@dataclass
class ValidationResult:
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not self.issues

    def add(self, message: str, *, node_id: str | None = None, edge_id: str | None = None) -> None:
        self.issues.append(ValidationIssue(node_id=node_id, edge_id=edge_id, message=message))


def validate_graph(graph_json: dict) -> ValidationResult:
    result = ValidationResult()
    nodes = {n["id"]: n for n in graph_json.get("nodes", [])}
    edges = graph_json.get("edges", [])

    # Rule 1: no dangling edges.
    for edge in edges:
        if edge["source"] not in nodes:
            result.add(
                f"Edge references unknown source node '{edge['source']}'", edge_id=edge["id"]
            )
        if edge["target"] not in nodes:
            result.add(
                f"Edge references unknown target node '{edge['target']}'", edge_id=edge["id"]
            )

    # Used by Rule 4c below.
    incoming: dict[str, list[dict]] = {}
    for edge in edges:
        incoming.setdefault(edge.get("target"), []).append(edge)

    # Rule 7 (checked alongside outgoing-edge grouping below): valid source_port per node type.
    outgoing: dict[str, dict[str, list[dict]]] = {nid: {} for nid in nodes}
    for edge in edges:
        src = edge.get("source")
        if src not in nodes:
            continue
        node_type = nodes[src]["type"]
        port = edge.get("source_port", "default")
        allowed = ALLOWED_SOURCE_PORTS.get(node_type, {"default"})
        if port not in allowed:
            result.add(
                f"Edge uses source_port '{port}' which is invalid for node type '{node_type}' "
                f"(allowed: {sorted(allowed)})",
                edge_id=edge["id"],
                node_id=src,
            )
        outgoing[src].setdefault(port, []).append(edge)

    for node_id, node in nodes.items():
        ntype = node["type"]
        ports_present = set(outgoing.get(node_id, {}))

        # Rule 2: Decision nodes need exactly one true and one false edge.
        if ntype == "decision":
            for required in ("true", "false"):
                if required not in ports_present:
                    result.add(f"Decision node is missing its '{required}' edge", node_id=node_id)

        # Rule 3: API/LLM/Code/Sub-workflow need both success and failure connected.
        if ntype in DUAL_OUTPUT_TYPES:
            for required in ("success", "failure"):
                if required not in ports_present:
                    result.add(
                        f"{ntype} node's '{required}' output is not connected to anything",
                        node_id=node_id,
                    )

        # Rule 4: Retry nodes need both retry and give-up connected.
        if ntype == "retry":
            for required in ("retry", "give-up"):
                if required not in ports_present:
                    result.add(
                        f"Retry node's '{required}' output is not connected", node_id=node_id
                    )

        # Rule 4b: Loop nodes need both body and done connected, and the body
        # edge must actually target config.body_start_node_id — the two are
        # meant to always agree (contracts/graph-schema.md), and letting them
        # silently drift would route into the wrong node at runtime.
        if ntype == "loop":
            for required in ("body", "done"):
                if required not in ports_present:
                    result.add(f"Loop node's '{required}' output is not connected", node_id=node_id)
            body_start = node.get("config", {}).get("body_start_node_id")
            body_targets = [e["target"] for e in outgoing.get(node_id, {}).get("body", [])]
            if body_targets and body_start not in body_targets:
                result.add(
                    "Loop node's 'body' edge must target its own "
                    f"config.body_start_node_id ('{body_start}')",
                    node_id=node_id,
                )

        # Rule 4c: Tool nodes aren't part of execution flow (FR-016, User Story
        # 11) — an LLM node invokes them directly via function-calling, not by
        # graph traversal, so a Tool node must never receive an incoming edge,
        # and every outgoing edge it does have must target an `llm` node
        # (2026-07-30 design decision — see app/graph/nodes/tool_node.py).
        if ntype == "tool":
            if incoming.get(node_id):
                result.add(
                    "Tool node cannot have incoming edges — it's invoked directly "
                    "by an LLM node, not traversed like other nodes",
                    node_id=node_id,
                )
            tool_edges = outgoing.get(node_id, {}).get("default", [])
            if not tool_edges:
                result.add("Tool node is not wired to any LLM node", node_id=node_id)
            for edge in tool_edges:
                target_type = nodes.get(edge["target"], {}).get("type")
                if target_type != "llm":
                    result.add(
                        f"Tool node's output must target an LLM node, not '{target_type}'",
                        node_id=node_id,
                        edge_id=edge["id"],
                    )

    # Rule 5: Variable node names unique within this graph.
    seen_var_names: dict[str, str] = {}
    for node_id, node in nodes.items():
        if node["type"] != "variable":
            continue
        name = node.get("config", {}).get("name")
        if not name:
            result.add("Variable node has no name configured", node_id=node_id)
            continue
        if name in seen_var_names:
            result.add(
                f"Variable name '{name}' is used by both '{seen_var_names[name]}' and '{node_id}' "
                "— names must be unique within a workflow",
                node_id=node_id,
            )
        else:
            seen_var_names[name] = node_id

    # Rule 6: at least one Response node reachable from an Input start node.
    input_ids = [nid for nid, n in nodes.items() if n["type"] == "input"]
    response_ids = {nid for nid, n in nodes.items() if n["type"] == "response"}
    adjacency: dict[str, list[str]] = {}
    for edge in edges:
        adjacency.setdefault(edge["source"], []).append(edge["target"])

    reachable: set[str] = set()
    stack = list(input_ids)
    while stack:
        current = stack.pop()
        if current in reachable:
            continue
        reachable.add(current)
        stack.extend(adjacency.get(current, []))

    if input_ids and not (reachable & response_ids):
        result.add("No Response node is reachable from any Input (start) node")
    if not input_ids:
        result.add("Workflow has no Input node to start from")

    return result
