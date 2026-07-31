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

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

# Import models so SQLModel.metadata knows about every table before create_all().
from app.models import chat, credential, run, variable, workflow  # noqa: F401

_engine_cache: dict[str, Engine] = {}

# Every node execution opens its own Session and commits a NodeExecution row
# (app/graph/compiler.py, Constitution VII) — under LangGraph's native
# parallel-branch execution (the Merge node's whole point) several of those
# commits can land at the same instant, and the LogsSidecar's polling GET
# /api/runs/{id}/executions adds concurrent reads on top. SQLite's default
# rollback-journal mode takes an exclusive lock for the duration of a write,
# and Python's sqlite3 default busy wait is short, so "database is locked"
# under exactly this kind of concurrency is expected, not exotic. WAL mode
# lets readers proceed without blocking on a writer, and a generous
# busy_timeout makes a genuinely-contended writer retry instead of failing
# immediately. PRAGMAs are per-connection (except journal_mode, which is
# persisted in the database file itself once set) — applied via a "connect"
# event listener so every connection the pool opens gets them, not just the
# first one.
_BUSY_TIMEOUT_MS = 30_000


def _set_sqlite_pragmas(dbapi_connection, connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute(f"PRAGMA busy_timeout={_BUSY_TIMEOUT_MS}")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()


def get_db_path() -> str:
    return os.environ.get("NEXTGEN_DB_PATH", "./nextgen.db")


def get_engine() -> Engine:
    path = get_db_path()
    if path not in _engine_cache:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
        event.listen(engine, "connect", _set_sqlite_pragmas)
        _engine_cache[path] = engine
    return _engine_cache[path]


def init_db() -> None:
    SQLModel.metadata.create_all(get_engine())


def get_session() -> Generator[Session, None, None]:
    with Session(get_engine()) as session:
        yield session
