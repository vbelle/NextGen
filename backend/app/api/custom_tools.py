"""REST API router for Custom Tools CRUD operations."""

from __future__ import annotations

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.db import get_session
from app.graph.tool_registry import build_custom_tool_schema_and_fn
from app.models.custom_tool import CustomTool

router = APIRouter(prefix="/api/custom-tools", tags=["custom-tools"])


class CustomToolCreate(BaseModel):
    name: str
    description: str
    python_code: str


class CustomToolUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    python_code: str | None = None


class CustomToolOut(BaseModel):
    id: str
    name: str
    description: str
    python_code: str
    created_at: str
    updated_at: str


@router.get("", response_model=list[CustomToolOut])
def list_custom_tools(session: Session = Depends(get_session)) -> list[CustomToolOut]:
    rows = session.exec(select(CustomTool).order_by(CustomTool.name)).all()
    return [
        CustomToolOut(
            id=t.id,
            name=t.name,
            description=t.description,
            python_code=t.python_code,
            created_at=t.created_at.isoformat(),
            updated_at=t.updated_at.isoformat(),
        )
        for t in rows
    ]


@router.post("", response_model=CustomToolOut, status_code=201)
def create_custom_tool(
    body: CustomToolCreate, session: Session = Depends(get_session)
) -> CustomToolOut:
    name = body.name.strip().lower().replace("-", "_").replace(" ", "_")
    existing = session.exec(select(CustomTool).where(CustomTool.name == name)).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Custom tool name '{name}' already exists")

    # Validate Python code syntax & schema construction
    try:
        build_custom_tool_schema_and_fn(name, body.python_code)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Invalid Python tool snippet: {exc}")

    tool = CustomTool(
        name=name,
        description=body.description.strip(),
        python_code=body.python_code,
    )
    session.add(tool)
    session.commit()
    session.refresh(tool)
    return CustomToolOut(
        id=tool.id,
        name=tool.name,
        description=tool.description,
        python_code=tool.python_code,
        created_at=tool.created_at.isoformat(),
        updated_at=tool.updated_at.isoformat(),
    )


@router.put("/{tool_id}", response_model=CustomToolOut)
def update_custom_tool(
    tool_id: str, body: CustomToolUpdate, session: Session = Depends(get_session)
) -> CustomToolOut:
    tool = session.get(CustomTool, tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail="Custom tool not found")

    if body.name:
        new_name = body.name.strip().lower().replace("-", "_").replace(" ", "_")
        existing = session.exec(
            select(CustomTool).where(CustomTool.name == new_name, CustomTool.id != tool_id)
        ).first()
        if existing:
            raise HTTPException(
                status_code=409, detail=f"Custom tool name '{new_name}' already exists"
            )
        tool.name = new_name

    if body.description is not None:
        tool.description = body.description.strip()

    if body.python_code is not None:
        try:
            build_custom_tool_schema_and_fn(tool.name, body.python_code)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"Invalid Python tool snippet: {exc}")
        tool.python_code = body.python_code

    tool.updated_at = datetime.now(timezone.utc)
    session.add(tool)
    session.commit()
    session.refresh(tool)
    return CustomToolOut(
        id=tool.id,
        name=tool.name,
        description=tool.description,
        python_code=tool.python_code,
        created_at=tool.created_at.isoformat(),
        updated_at=tool.updated_at.isoformat(),
    )


@router.delete("/{tool_id}", status_code=204)
def delete_custom_tool(tool_id: str, session: Session = Depends(get_session)) -> None:
    tool = session.get(CustomTool, tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail="Custom tool not found")
    session.delete(tool)
    session.commit()
