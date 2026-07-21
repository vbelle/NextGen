"""Run/audit REST endpoints. See contracts/rest-api.md §Runs & Audit."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.db import get_session
from app.models.run import NodeExecution, Run
from app.models.variable import RunVariable

router = APIRouter(prefix="/api/runs", tags=["runs"])


@router.get("/{run_id}")
def get_run(run_id: str, session: Session = Depends(get_session)) -> dict:
    run = session.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return {
        "id": run.id,
        "status": run.status,
        "workflow_version_id": run.workflow_version_id,
        "pending_prompt": json.loads(run.pending_prompt) if run.pending_prompt else None,
        "started_at": run.started_at.isoformat(),
        "ended_at": run.ended_at.isoformat() if run.ended_at else None,
    }


@router.get("/{run_id}/executions")
def get_run_executions(run_id: str, session: Session = Depends(get_session)) -> list[dict]:
    rows = session.exec(
        select(NodeExecution)
        .where(NodeExecution.run_id == run_id)
        .order_by(NodeExecution.started_at)
    ).all()
    return [
        {
            "id": e.id,
            "node_id": e.node_id,
            "node_type": e.node_type,
            "output_port": e.output_port,
            "input": json.loads(e.input_json),
            "output": json.loads(e.output_json),
            "attempt_count": e.attempt_count,
            "started_at": e.started_at.isoformat(),
            "ended_at": e.ended_at.isoformat() if e.ended_at else None,
        }
        for e in rows
    ]


@router.get("/{run_id}/variables")
def get_run_variables(run_id: str, session: Session = Depends(get_session)) -> list[dict]:
    rows = session.exec(select(RunVariable).where(RunVariable.run_id == run_id)).all()
    return [
        {"name": v.name, "value": json.loads(v.value_json), "set_at": v.set_at.isoformat()}
        for v in rows
    ]


@router.get("")
def list_runs(
    workflow_id: str | None = None,
    status: str | None = None,
    session: Session = Depends(get_session),
) -> list[dict]:
    query = select(Run)
    if status:
        query = query.where(Run.status == status)
    rows = session.exec(query).all()
    return [
        {
            "id": r.id,
            "status": r.status,
            "workflow_version_id": r.workflow_version_id,
            "started_at": r.started_at.isoformat(),
        }
        for r in rows
    ]
