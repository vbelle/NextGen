"""CustomTool model: user-defined Python tools for function-calling."""

from __future__ import annotations

from datetime import datetime, timezone
import uuid
from sqlmodel import Field, SQLModel


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class CustomTool(SQLModel, table=True):
    __tablename__ = "customtool"

    id: str = Field(default_factory=_uuid, primary_key=True)
    name: str = Field(index=True, unique=True)
    description: str
    python_code: str
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)
