"""Unit tests for app/db.py's SQLite pragma setup — regression coverage for the
"database is locked" bug seen under concurrent node-execution writes (parallel
Merge branches each committing a NodeExecution row) plus the LogsSidecar's
concurrent polling reads. WAL mode + a generous busy_timeout is what fixes
that class of error; these tests confirm both are actually applied to every
connection the engine hands out, and that genuinely concurrent writers no
longer raise 'database is locked' against a real file-backed database."""

from __future__ import annotations

import os
import threading

os.environ.setdefault("NEXTGEN_APP_PASSWORD", "test-password")
os.environ.setdefault("NEXTGEN_CREDENTIAL_KEY", "kQq4v2v7v3o5b1yqjq7c9m3n8p0r2s4t6u8w0x2y4z6=")

from sqlmodel import Session, text

from app.db import get_engine, init_db


def test_new_connections_get_wal_and_busy_timeout(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXTGEN_DB_PATH", str(tmp_path / "pragma_test.db"))
    engine = get_engine()
    init_db()

    with Session(engine) as session:
        journal_mode = session.exec(text("PRAGMA journal_mode")).scalar()
        busy_timeout = session.exec(text("PRAGMA busy_timeout")).scalar()

    assert journal_mode.lower() == "wal"
    assert busy_timeout == 30_000


def test_concurrent_writers_do_not_raise_database_is_locked(tmp_path, monkeypatch):
    """Regression test for the exact failure mode reported in manual testing:
    several near-simultaneous commits against the same SQLite file (standing
    in for parallel Merge-branch node executions each writing their own
    NodeExecution row) must not raise 'database is locked' now that WAL mode
    and a real busy_timeout are configured."""
    monkeypatch.setenv("NEXTGEN_DB_PATH", str(tmp_path / "concurrency_test.db"))
    engine = get_engine()
    init_db()

    errors: list[Exception] = []

    def _writer(n: int) -> None:
        try:
            with Session(engine) as session:
                session.exec(
                    text("CREATE TABLE IF NOT EXISTS scratch (id INTEGER PRIMARY KEY, val TEXT)")
                )
                session.exec(
                    text("INSERT INTO scratch (val) VALUES (:v)"), params={"v": f"row-{n}"}
                )
                session.commit()
        except Exception as exc:  # noqa: BLE001 — collected below, not swallowed
            errors.append(exc)

    threads = [threading.Thread(target=_writer, args=(n,)) for n in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Concurrent writers raised: {errors}"

    with Session(engine) as session:
        count = session.exec(text("SELECT COUNT(*) FROM scratch")).scalar()
    assert count == 20
