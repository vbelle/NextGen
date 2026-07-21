"""Run and NodeExecution tables. See specs/001-workflow-builder/data-model.md."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlmodel import Field, SQLModel


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class RunStatus(str, Enum):
    running = "running"
    paused = "paused"
    completed = "completed"
    failed = "failed"


class Run(SQLModel, table=True):
    """One execution of a specific WorkflowVersion. id doubles as the LangGraph thread_id."""

    id: str = Field(default_factory=_uuid, primary_key=True)
    workflow_version_id: str = Field(foreign_key="workflowversion.id", index=True)
    status: RunStatus = Field(default=RunStatus.running, index=True)
    pending_prompt: str | None = Field(default=None)  # JSON: {"question": "...", "node_id": "..."}
    started_at: datetime = Field(default_factory=_now)
    ended_at: datetime | None = Field(default=None)
    chat_session_id: str = Field(foreign_key="chatsession.id", index=True)


class NodeExecution(SQLModel, table=True):
    """Audit record of one node's execution within a Run. Satisfies FR-029, SC-007."""

    id: str = Field(default_factory=_uuid, primary_key=True)
    run_id: str = Field(foreign_key="run.id", index=True)
    node_id: str
    node_type: str
    output_port: str  # "success"/"failure"/"true"/"false"/"retry"/"give-up"/"default"
    input_json: str
    output_json: str
    attempt_count: int | None = Field(default=None)  # only meaningful for retry nodes
    started_at: datetime = Field(default_factory=_now)
    ended_at: datetime | None = Field(default=None)
