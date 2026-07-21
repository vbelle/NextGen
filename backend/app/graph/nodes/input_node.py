"""Input node: collects a value from the chat user, either as a starting parameter
(FR-007) or as a mid-flow human-in-the-loop pause (FR-008, User Story 2). Both cases
use LangGraph's interrupt() — see research.md §2."""

from __future__ import annotations

from pydantic import BaseModel

from app.graph.schema import register_node_type
from app.graph.state import GraphState


class InputConfig(BaseModel):
    prompt: str
    required: bool = True


async def execute(node_id: str, config: dict, state: GraphState) -> dict:
    from langgraph.types import interrupt  # imported lazily: keeps node modules import-light

    cfg = InputConfig(**config)
    value = interrupt({"prompt": cfg.prompt, "node_id": node_id})
    return {
        "node_outputs": {node_id: value, "__latest__": value},
        "last_output_port": {node_id: "default"},
    }


register_node_type("input", InputConfig, execute)
