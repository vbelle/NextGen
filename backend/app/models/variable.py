"""RunVariable table — write-through audit mirror of Variable-node writes. See data-model.md."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class RunVariable(SQLModel, table=True):
    id: str = Field(default_factory=_uuid, primary_key=True)
    run_id: str = Field(foreign_key="run.id", index=True)
    name: str
    value_json: str
    set_at: datetime = Field(default_factory=_now)
