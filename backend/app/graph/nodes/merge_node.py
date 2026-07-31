"""Merge node: combines the outputs of multiple parallel branches that all
feed into it into a single downstream value (User Story 13, FR-020).

Deliberately does NOT read state["node_outputs"]["__latest__"] the way most
node config resolution (render_template's {{previous}}) does. When two
branches fanned out from an earlier node run concurrently in the same
LangGraph superstep, both write to "__latest__" at once and
app/graph/state.py's _merge_dicts reducer (last-write-wins per key) doesn't
guarantee which branch's value survives. Instead, the compiler resolves
exactly which upstream node_ids feed this Merge node at compile time — same
pattern as the LLM node's bound_tools, app/graph/compiler.py's
_resolve_bound_tools — and injects them as `input_node_ids`, so this reads
each branch's own deterministic node_outputs[node_id] entry directly,
sidestepping the race entirely."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.graph.schema import register_node_type
from app.graph.state import GraphState


class MergeConfig(BaseModel):
    strategy: str = "combine-object"
    # Compiler-injected (see module docstring) — not part of the user-facing
    # config a builder edits on the canvas. contracts/graph-schema.md's merge
    # config is just `{"strategy": ...}`; this gets added the same way
    # LlmConfig.bound_tools does, never supplied directly in graph_json.
    input_node_ids: list[str] = Field(default_factory=list)


def _combine_object(contributions: list[tuple[str, object]]) -> dict:
    combined: dict = {}
    for source_id, value in contributions:
        if isinstance(value, dict):
            combined.update(value)
        elif value is not None:
            # A non-dict branch output would otherwise be silently dropped by
            # a plain dict.update — keep it, keyed by the node that produced
            # it, rather than lose it.
            combined[source_id] = value
    return combined


def _concat_list(values: list) -> list:
    combined: list = []
    for value in values:
        if isinstance(value, list):
            combined.extend(value)
        elif value is not None:
            combined.append(value)
    return combined


async def execute(node_id: str, config: dict, state: GraphState) -> dict:
    cfg = MergeConfig(**config)
    node_outputs = state.get("node_outputs", {})
    contributions = [(nid, node_outputs[nid]) for nid in cfg.input_node_ids if nid in node_outputs]

    if cfg.strategy == "concat-list":
        combined: object = _concat_list([value for _, value in contributions])
    else:
        combined = _combine_object(contributions)

    return {
        "node_outputs": {node_id: combined, "__latest__": combined},
        "last_output_port": {node_id: "default"},
    }


register_node_type("merge", MergeConfig, execute)
