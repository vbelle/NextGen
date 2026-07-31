"""Debug/introspection endpoint backing the canvas's "View code" panel's
LangGraph tab. Takes graph_json directly in the request body rather than a
saved workflow id, so it works on an unsaved/in-progress canvas too — same
reasoning as why validation in workflows.py runs against the posted body
rather than requiring a save first."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.graph.codegen import generate_langgraph_code

router = APIRouter(prefix="/api/codegen", tags=["codegen"])


class GraphJsonIn(BaseModel):
    graph_json: dict


class CodegenOut(BaseModel):
    code: str


@router.post("/langgraph", response_model=CodegenOut)
def codegen_langgraph(body: GraphJsonIn) -> CodegenOut:
    return CodegenOut(code=generate_langgraph_code(body.graph_json))
