"""ChatSession and ChatMessage tables. See data-model.md."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlmodel import Field, SQLModel


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ChatSession(SQLModel, table=True):
    id: str = Field(default_factory=_uuid, primary_key=True)
    created_at: datetime = Field(default_factory=_now)


class ChatRole(str, Enum):
    user = "user"
    system = "system"


class ChatMessage(SQLModel, table=True):
    id: str = Field(default_factory=_uuid, primary_key=True)
    chat_session_id: str = Field(foreign_key="chatsession.id", index=True)
    role: ChatRole
    content: str
    run_id: str | None = Field(default=None, foreign_key="run.id")
    created_at: datetime = Field(default_factory=_now)
