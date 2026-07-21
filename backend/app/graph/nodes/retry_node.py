"""Retry node: re-attempts a failed node up to `max_attempts` times, then routes
to give-up (SC-008). See research.md §3 — state["retry_counts"] is keyed by the
Retry node's OWN id, incremented each time this node is reached. Routing back to
the node that actually failed isn't this function's job at all: the canvas wires
this node's "retry" output edge directly to the origin node's id
(contracts/graph-schema.md), and the same generic conditional-edge mechanism
every multi-port node type already uses (app/graph/compiler.py) sends execution
there — no special-casing needed for the loop itself.

Deliberately does NOT touch node_outputs["__latest__"]: overwriting it with
Retry's own bookkeeping would hide the real failure output ({{previous}}) from
whatever a give-up path's Response node wants to reference."""

from __future__ import annotations

from pydantic import BaseModel

from app.graph.schema import register_node_type
from app.graph.state import GraphState

DEFAULT_MAX_ATTEMPTS = 3


class RetryConfig(BaseModel):
    max_attempts: int = DEFAULT_MAX_ATTEMPTS


async def execute(node_id: str, config: dict, state: GraphState) -> dict:
    cfg = RetryConfig(**config)
    attempt = state.get("retry_counts", {}).get(node_id, 0) + 1
    port = "retry" if attempt < cfg.max_attempts else "give-up"
    return {
        "retry_counts": {node_id: attempt},
        "node_outputs": {node_id: {"attempt": attempt, "max_attempts": cfg.max_attempts}},
        "last_output_port": {node_id: port},
    }


register_node_type("retry", RetryConfig, execute)
