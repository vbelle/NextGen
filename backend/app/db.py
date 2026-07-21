"""SQLite engine/session setup. Same file LangGraph's AsyncSqliteSaver checkpoints against
(plan.md: "one place, one volume, one backup target").

Engine creation is lazy and cached per-path (rather than a single module-level
global) specifically so tests can override NEXTGEN_DB_PATH per test via
monkeypatch and get a genuinely isolated database — a plain module-level
`engine = create_engine(...)` would be fixed at import time and ignore later
env var changes within the same test process."""

from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path

from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

# Import models so SQLModel.metadata knows about every table before create_all().
from app.models import chat, credential, run, variable, workflow  # noqa: F401

_engine_cache: dict[str, Engine] = {}


def get_db_path() -> str:
    return os.environ.get("NEXTGEN_DB_PATH", "./nextgen.db")


def get_engine() -> Engine:
    path = get_db_path()
    if path not in _engine_cache:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        _engine_cache[path] = create_engine(
            f"sqlite:///{path}", connect_args={"check_same_thread": False}
        )
    return _engine_cache[path]


def init_db() -> None:
    SQLModel.metadata.create_all(get_engine())


def get_session() -> Generator[Session, None, None]:
    with Session(get_engine()) as session:
        yield session
