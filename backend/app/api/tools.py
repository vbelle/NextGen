"""Read-only endpoint listing the built-in tool implementations a Tool node's
`implementation_ref` can point at (see app/graph/tool_registry.py). Lets the
canvas offer a dropdown of valid refs instead of free text prone to typos —
same reasoning as vector_stores.py's list endpoint for Memory nodes."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.graph.tool_registry import list_tool_implementations

router = APIRouter(prefix="/api/tools", tags=["tools"])


class ToolImplementationOut(BaseModel):
    implementation_ref: str


@router.get("", response_model=list[ToolImplementationOut])
def list_tools() -> list[ToolImplementationOut]:
    return [ToolImplementationOut(implementation_ref=ref) for ref in list_tool_implementations()]
