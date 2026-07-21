"""Code node: runs a sandboxed Python snippet (app/sandbox/run_snippet.py),
success/failure routing (FR-017). SC-005: a malicious/runaway snippet must route
to failure, never crash the run or the app."""

from __future__ import annotations

from pydantic import BaseModel

from app.graph.schema import register_node_type
from app.graph.state import GraphState
from app.sandbox.run_snippet import run_snippet

DEFAULT_TIMEOUT_SECONDS = 60


class CodeConfig(BaseModel):
    snippet: str
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS


async def execute(node_id: str, config: dict, state: GraphState) -> dict:
    cfg = CodeConfig(**config)
    try:
        previous = state.get("node_outputs", {}).get("__latest__")
        variables = state.get("variables", {})
        outcome = await run_snippet(
            snippet=cfg.snippet,
            previous=previous,
            variables=variables,
            timeout_seconds=cfg.timeout_seconds,
        )
        if outcome.get("ok"):
            result = outcome.get("result")
            return {
                "node_outputs": {node_id: result, "__latest__": result},
                "last_output_port": {node_id: "success"},
            }
        error = {"error": outcome.get("error", "Unknown sandbox error")}
        return {
            "node_outputs": {node_id: error, "__latest__": error},
            "last_output_port": {node_id: "failure"},
        }
    except (
        Exception
    ) as exc:  # noqa: BLE001 — timeout / worker crash / unresolved-variable-in-config
        # all route to failure too, matching the DUAL_OUTPUT_TYPES convention.
        error = {"error": str(exc)}
        return {
            "node_outputs": {node_id: error, "__latest__": error},
            "last_output_port": {node_id: "failure"},
        }


register_node_type("code", CodeConfig, execute)
