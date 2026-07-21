"""Credential table — encrypted secret referenced by name/id from node configs. See data-model.md."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Credential(SQLModel, table=True):
    id: str = Field(default_factory=_uuid, primary_key=True)
    name: str = Field(unique=True, index=True)
    encrypted_value: bytes  # Fernet ciphertext — never serialized back out (see app/crypto.py)
    created_at: datetime = Field(default_factory=_now)
