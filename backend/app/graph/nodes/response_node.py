"""Response node: terminal node whose received value is shown back to the chat
user (FR-009). A workflow may have more than one (FR-010)."""

from __future__ import annotations

from pydantic import BaseModel

from app.graph.schema import register_node_type
from app.graph.state import GraphState
from app.graph.templating import render_template


class ResponseConfig(BaseModel):
    content: str


async def execute(node_id: str, config: dict, state: GraphState) -> dict:
    cfg = ResponseConfig(**config)
    rendered = render_template(cfg.content, state)
    return {
        # "__response__" is the well-known key app/runtime/executor.py reads to
        # decide what to relay back to chat once the graph reaches END.
        "node_outputs": {node_id: rendered, "__response__": rendered, "__latest__": rendered},
        "last_output_port": {node_id: "default"},
    }


register_node_type("response", ResponseConfig, execute)
