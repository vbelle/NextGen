"""Node-type registry and shared config base classes. See contracts/graph-schema.md.

Each node module (app/graph/nodes/*.py) defines its own Pydantic config class and
registers itself here via @register_node_type. Only node types implemented so far
are registered — this is intentional per tasks.md's phased build order, not an
oversight; compiling a graph_json referencing an unregistered type raises a clear
error rather than silently doing nothing.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import NamedTuple

from pydantic import BaseModel

# Output ports each node type is allowed to use as an edge `source_port`,
# per contracts/graph-schema.md's save-time validation rule 7.
ALLOWED_SOURCE_PORTS: dict[str, set[str]] = {
    "input": {"default"},
    "llm": {"success", "failure"},
    "decision": {"true", "false"},
    "api": {"success", "failure"},
    "code": {"success", "failure"},
    # "body" enters body_start_node_id for the next item; "done" fires once
    # every item has been processed (2026-07-27 design decision: the loop body
    # is a real multi-node cycle on the canvas, same shape as Retry's cycle —
    # see app/graph/nodes/loop_node.py).
    "loop": {"body", "done"},
    "memory": {"default"},
    "tool": {"default"},
    "subworkflow": {"success", "failure"},
    "merge": {"default"},
    "response": set(),  # terminal — no outgoing edges
    "retry": {"retry", "give-up"},
    "variable": {"default"},
    "export": {"success", "failure"},
}

DUAL_OUTPUT_TYPES = {"llm", "api", "code", "subworkflow", "export"}  # FR-017


class NodeTypeDefinition(NamedTuple):
    config_model: type[BaseModel]
    # (node_id, config, state) -> partial GraphState update. Defined per node module;
    # kept as Callable here to avoid a circular import with app.graph.compiler.
    executor: Callable


_REGISTRY: dict[str, NodeTypeDefinition] = {}


def register_node_type(type_name: str, config_model: type[BaseModel], executor: Callable) -> None:
    """Called once at import time by each app/graph/nodes/*.py module."""
    _REGISTRY[type_name] = NodeTypeDefinition(config_model=config_model, executor=executor)


def get_node_type(type_name: str) -> NodeTypeDefinition:
    if type_name not in _REGISTRY:
        raise ValueError(
            f"Unknown or not-yet-implemented node type '{type_name}'. "
            f"Registered types: {sorted(_REGISTRY)}"
        )
    return _REGISTRY[type_name]


def registered_types() -> set[str]:
    return set(_REGISTRY)
