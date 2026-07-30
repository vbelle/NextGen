"""Tool node: a callable function an LLM node can invoke via function-calling
(FR-016).

Deliberately NOT part of normal graph execution flow — the model decides at
generation time whether to call it, not the graph traversal — so a Tool node
is never added to the compiled StateGraph (see app/graph/compiler.py's
handling of node_type == "tool"). Wiring is still expressed as a normal
canvas edge from the Tool node to the LLM node that can use it (the
`default` port, same as most other node types — see schema.py's
ALLOWED_SOURCE_PORTS) per Constitution IV ("the visual graph is the source
of truth"); the compiler resolves those edges into the LLM node's
`bound_tools` at compile time rather than treating them as execution edges.
validation.py enforces that a Tool node has no incoming edges and that all
its outgoing edges target `llm` nodes (2026-07-30 design decision — asked,
not guessed, since contracts/graph-schema.md didn't say how a Tool node
connects to the LLM node using it).

See app/graph/tool_registry.py for the second half of this design decision:
what `implementation_ref` actually resolves to."""

from __future__ import annotations

from pydantic import BaseModel

from app.graph.schema import register_node_type
from app.graph.state import GraphState


class ToolConfig(BaseModel):
    function_name: str
    description: str
    implementation_ref: str


async def execute(node_id: str, config: dict, state: GraphState) -> dict:
    raise NotImplementedError(
        "Tool nodes are invoked directly by an LLM node via function-calling "
        "(see app/graph/nodes/llm_node.py) and are excluded from normal graph "
        "traversal by the compiler — this executor should never be called."
    )


register_node_type("tool", ToolConfig, execute)
