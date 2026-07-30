"""Loop node: iterates an inner sub-path once per item in a resolved collection,
aggregating each iteration's result (User Story 9).

2026-07-27 design decision (no research.md entry existed for this — asked the
user rather than guessing, since it's a real architectural fork): the loop body
is a genuine multi-node cycle wired on the canvas, the same shape as the Retry
node's cycle. This node's "body" output routes to `body_start_node_id` for the
next item; the body's own terminal node's ordinary edge loops back to THIS
node's id (no special port needed there, exactly like a Retry origin node's
failure edge targets the Retry node's id). Once every item is processed, the
"done" output fires with the aggregated list of per-item results.

Per-loop bookkeeping (items/index/results) lives in GraphState.loop_state,
keyed by this node's own id — not local Python state — so a pause/resume mid-
loop-body checkpoints correctly, same reasoning as retry_counts."""

from __future__ import annotations

from pydantic import BaseModel

from app.graph.schema import register_node_type
from app.graph.state import GraphState
from app.graph.templating import resolve_value_reference


class LoopConfig(BaseModel):
    collection_ref: str
    body_start_node_id: str


async def execute(node_id: str, config: dict, state: GraphState) -> dict:
    cfg = LoopConfig(**config)
    loop_state = state.get("loop_state", {}).get(node_id)

    if loop_state is None:
        # First entry — resolve the collection exactly once. Re-resolving on
        # every re-entry would be wrong: collection_ref often references
        # {{previous}}, which changes to the body's own output after the
        # first iteration runs.
        items = resolve_value_reference(cfg.collection_ref, state)
        if not isinstance(items, list):
            raise TypeError(
                "Loop node's collection_ref resolved to " f"{type(items).__name__}, not a list"
            )
        index = 0
        results: list = []
    else:
        items = loop_state["items"]
        results = list(loop_state["results"])
        # A prior iteration's body just completed and looped back here —
        # capture its result before moving on to the next item.
        results.append(state.get("node_outputs", {}).get("__latest__"))
        index = loop_state["index"] + 1

    if index < len(items):
        current_item = items[index]
        return {
            "loop_state": {node_id: {"items": items, "index": index, "results": results}},
            "node_outputs": {node_id: current_item, "__latest__": current_item},
            "last_output_port": {node_id: "body"},
        }

    return {
        "loop_state": {node_id: {"items": items, "index": index, "results": results}},
        "node_outputs": {node_id: results, "__latest__": results},
        "last_output_port": {node_id: "done"},
    }


register_node_type("loop", LoopConfig, execute)
