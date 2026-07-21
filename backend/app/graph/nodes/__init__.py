"""Importing this package registers every implemented node type (see each
module's register_node_type(...) call at import time). Node modules not yet
built (per tasks.md's phased story order) are simply absent from this list —
compiling a graph_json referencing one raises a clear error (schema.py)."""

from app.graph.nodes import (  # noqa: F401
    api_node,
    code_node,
    decision_node,
    input_node,
    llm_node,
    response_node,
    retry_node,
    variable_node,
)
