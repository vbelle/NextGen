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
