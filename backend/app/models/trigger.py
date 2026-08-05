"""WorkflowTrigger model: Webhook endpoints and Cron schedules for automated execution."""

from __future__ import annotations

from datetime import datetime, timezone
import uuid
from sqlmodel import Field, SQLModel


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class WorkflowTrigger(SQLModel, table=True):
    __tablename__ = "workflowtrigger"

    id: str = Field(default_factory=_uuid, primary_key=True)
    workflow_id: str = Field(index=True)
    trigger_type: str = Field(index=True)  # "webhook" or "cron"
    cron_expression: str | None = None  # e.g. "0 9 * * *" or "*/15 * * * *"
    webhook_secret: str | None = None  # Optional header verification token
    enabled: bool = Field(default=True)
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)
