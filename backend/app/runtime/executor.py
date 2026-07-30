"""Run orchestration: each Run executes as a background asyncio task, never inline
in an HTTP/WebSocket request handler (Constitution III — no synchronous blocking
run path). LangGraph's AsyncSqliteSaver checkpointer is the durable source of truth
for anything paused; this module's in-memory task registry is just for fast status
lookups on a live process. See research.md §2, §7.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.types import Command

from app.db import get_db_path
from app.graph.compiler import compile_graph
from app.models.run import Run, RunStatus

# Tracks in-flight asyncio tasks for fast cancellation/lookup while the process is
# alive. Not the source of truth for run state — SQLite (Run.status, the
# checkpointer) is. See restart-reconciliation in reconcile_stale_runs() below.
_LIVE_TASKS: dict[str, asyncio.Task] = {}

_checkpointer_cms: dict[str, object] = {}
_checkpointers: dict[str, AsyncSqliteSaver] = {}


async def get_checkpointer() -> AsyncSqliteSaver:
    """Lazily opens one shared AsyncSqliteSaver against the same SQLite file the
    rest of the app uses (plan.md: one file, one volume). Cached per db path
    (not a single global) for the same test-isolation reason as app/db.py."""
    path = get_db_path()
    if path not in _checkpointers:
        cm = AsyncSqliteSaver.from_conn_string(path)
        _checkpointer_cms[path] = cm
        _checkpointers[path] = await cm.__aenter__()
    return _checkpointers[path]


def _extract_interrupt(result: dict) -> dict | None:
    """LangGraph surfaces a paused run as an '__interrupt__' key in the invoke
    result containing Interrupt objects; each Interrupt's .value is whatever the
    node passed to interrupt(...)."""
    interrupts = result.get("__interrupt__")
    if not interrupts:
        return None
    first = interrupts[0]
    return first.value if hasattr(first, "value") else first


async def start_run(*, session_factory, run_id: str, graph_json: dict, initial_state: dict) -> None:
    """Kicks off a new Run as a background task. `session_factory` is a zero-arg
    callable returning a fresh SQLModel Session (background tasks must not share
    a Session with the request that started them). Takes a plain `run_id` string
    rather than an ORM Run object deliberately — the object would be detached from
    its originating Session by the time this task actually runs."""
    task = asyncio.create_task(_execute(session_factory, run_id, graph_json, initial_state))
    _LIVE_TASKS[run_id] = task


async def resume_run(*, session_factory, run_id: str, graph_json: dict, resume_value: str) -> None:
    task = asyncio.create_task(
        _execute(session_factory, run_id, graph_json, Command(resume=resume_value))
    )
    _LIVE_TASKS[run_id] = task


async def _execute(session_factory, run_id: str, graph_json: dict, run_input) -> None:
    from app.runtime import notify  # local import: avoids a circular import with chat/websocket.py

    checkpointer = await get_checkpointer()
    builder = compile_graph(graph_json)
    compiled = builder.compile(checkpointer=checkpointer)
    config = {"configurable": {"thread_id": run_id}}

    with session_factory() as session:
        db_run = session.get(Run, run_id)
        try:
            result = await compiled.ainvoke(run_input, config=config)
        except Exception as exc:  # noqa: BLE001 — any node/compiler error fails the run cleanly
            db_run.status = RunStatus.failed
            db_run.ended_at = datetime.now(timezone.utc)
            session.add(db_run)
            session.commit()
            await notify.run_failed(run_id, str(exc))
            return

        pending = _extract_interrupt(result)
        if pending is not None:
            db_run.status = RunStatus.paused
            db_run.pending_prompt = json.dumps(pending)
            session.add(db_run)
            session.commit()
            await notify.input_requested(run_id, pending)
            return

        response_text = result.get("node_outputs", {}).get("__response__")
        db_run.status = RunStatus.completed
        db_run.ended_at = datetime.now(timezone.utc)
        db_run.pending_prompt = None
        session.add(db_run)
        session.commit()
        await notify.run_completed(run_id, response_text)


def reconcile_stale_runs(session) -> None:
    """Startup reconciliation (research.md §7): a Run whose last known status was
    'running' when the process died wasn't at a checkpoint boundary, so it can't be
    safely resumed — mark it failed rather than silently losing it. 'paused' Runs
    are untouched; their state was already durably checkpointed.

    Deliberately synchronous: this runs once at process startup, before any
    request is served, using plain SQLModel calls with no actual awaits."""
    from sqlmodel import select

    stale = session.exec(select(Run).where(Run.status == RunStatus.running)).all()
    for run in stale:
        run.status = RunStatus.failed
        run.ended_at = datetime.now(timezone.utc)
        session.add(run)
    if stale:
        session.commit()
