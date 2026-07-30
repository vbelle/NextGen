"""Memory/Retrieval node: queries a configured vector store and returns the
top-k matches, meant to ground a downstream LLM node's prompt (FR-015, User
Story 10). See app/vectorstore.py for the underlying Chroma + Ollama-embeddings
infrastructure — a design gap this story had to fill from scratch (no research.md
entry existed).

Single output port ("default", ALLOWED_SOURCE_PORTS["memory"]) — no
success/failure split. A missing store or an embeddings-call failure is a
genuine run failure here, same class of behavior as Decision/Variable's
config errors, not something this node type is designed to route around."""

from __future__ import annotations

from pydantic import BaseModel

from app import vectorstore
from app.graph.schema import register_node_type
from app.graph.state import GraphState
from app.graph.templating import render_template

DEFAULT_TOP_K = 5


class MemoryConfig(BaseModel):
    vector_store_ref: str
    query: str
    top_k: int = DEFAULT_TOP_K


async def execute(node_id: str, config: dict, state: GraphState) -> dict:
    cfg = MemoryConfig(**config)
    rendered_query = render_template(cfg.query, state)
    matches = await vectorstore.query_store(cfg.vector_store_ref, rendered_query, cfg.top_k)
    return {
        "node_outputs": {node_id: matches, "__latest__": matches},
        "last_output_port": {node_id: "default"},
    }


register_node_type("memory", MemoryConfig, execute)
