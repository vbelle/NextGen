"""Workflow and WorkflowVersion tables. See specs/001-workflow-builder/data-model.md."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Workflow(SQLModel, table=True):
    """A named, versioned workflow. `name` is the chat-invocation name."""

    id: str = Field(default_factory=_uuid, primary_key=True)
    name: str = Field(unique=True, index=True)
    active_version_id: str | None = Field(default=None, foreign_key="workflowversion.id")
    created_at: datetime = Field(default_factory=_now)


class WorkflowVersion(SQLModel, table=True):
    """An immutable snapshot of a workflow's graph at save time."""

    id: str = Field(default_factory=_uuid, primary_key=True)
    workflow_id: str = Field(foreign_key="workflow.id", index=True)
    version_number: int
    graph_json: str  # JSON-encoded {"nodes": [...], "edges": [...]} — see contracts/graph-schema.md
    created_at: datetime = Field(default_factory=_now)
