"""REST API router for Webhook endpoints and Cron Schedule Triggers."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel
from sqlmodel import Session, select

from app.db import get_engine, get_session
from app.models.run import Run, RunStatus
from app.models.trigger import WorkflowTrigger
from app.models.workflow import Workflow, WorkflowVersion
from app.runtime import executor
from app.runtime.scheduler import reload_cron_triggers

router = APIRouter(prefix="/api/triggers", tags=["triggers"])


class TriggerCreate(BaseModel):
    workflow_id: str
    trigger_type: str  # "webhook" or "cron"
    cron_expression: str | None = None
    webhook_secret: str | None = None
    enabled: bool = True


class TriggerOut(BaseModel):
    id: str
    workflow_id: str
    workflow_name: str | None = None
    trigger_type: str
    cron_expression: str | None = None
    webhook_secret: str | None = None
    enabled: bool
    created_at: str
    updated_at: str


@router.get("", response_model=list[TriggerOut])
def list_triggers(session: Session = Depends(get_session)) -> list[TriggerOut]:
    rows = session.exec(select(WorkflowTrigger)).all()
    out = []
    for t in rows:
        wf = session.get(Workflow, t.workflow_id)
        out.append(
            TriggerOut(
                id=t.id,
                workflow_id=t.workflow_id,
                workflow_name=wf.name if wf else None,
                trigger_type=t.trigger_type,
                cron_expression=t.cron_expression,
                webhook_secret=t.webhook_secret,
                enabled=t.enabled,
                created_at=t.created_at.isoformat(),
                updated_at=t.updated_at.isoformat(),
            )
        )
    return out


@router.post("", response_model=TriggerOut, status_code=201)
def create_trigger(body: TriggerCreate, session: Session = Depends(get_session)) -> TriggerOut:
    workflow = session.get(Workflow, body.workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    if body.trigger_type not in ("webhook", "cron"):
        raise HTTPException(status_code=400, detail="trigger_type must be 'webhook' or 'cron'")

    if body.trigger_type == "cron" and not body.cron_expression:
        raise HTTPException(status_code=400, detail="cron_expression is required for cron trigger")

    trigger = WorkflowTrigger(
        workflow_id=body.workflow_id,
        trigger_type=body.trigger_type,
        cron_expression=body.cron_expression.strip() if body.cron_expression else None,
        webhook_secret=body.webhook_secret.strip() if body.webhook_secret else None,
        enabled=body.enabled,
    )
    session.add(trigger)
    session.commit()
    session.refresh(trigger)

    if trigger.trigger_type == "cron":
        reload_cron_triggers()

    return TriggerOut(
        id=trigger.id,
        workflow_id=trigger.workflow_id,
        workflow_name=workflow.name,
        trigger_type=trigger.trigger_type,
        cron_expression=trigger.cron_expression,
        webhook_secret=trigger.webhook_secret,
        enabled=trigger.enabled,
        created_at=trigger.created_at.isoformat(),
        updated_at=trigger.updated_at.isoformat(),
    )


@router.delete("/{trigger_id}", status_code=204)
def delete_trigger(trigger_id: str, session: Session = Depends(get_session)) -> None:
    trigger = session.get(WorkflowTrigger, trigger_id)
    if not trigger:
        raise HTTPException(status_code=404, detail="Trigger not found")
    t_type = trigger.trigger_type
    session.delete(trigger)
    session.commit()

    if t_type == "cron":
        reload_cron_triggers()


@router.post("/webhook/{identifier}", status_code=202)
async def handle_webhook(
    identifier: str,
    request: Request,
    x_nextgen_secret: str | None = Header(None, alias="X-NextGen-Secret"),
    session: Session = Depends(get_session),
) -> dict:
    """Public Webhook Execution Endpoint. Triggers workflow execution from external systems."""
    # Find workflow by name or ID
    workflow = session.exec(
        select(Workflow).where((Workflow.id == identifier) | (Workflow.name == identifier))
    ).first()
    if not workflow:
        raise HTTPException(status_code=404, detail=f"Workflow '{identifier}' not found")

    if not workflow.active_version_id:
        raise HTTPException(
            status_code=400, detail=f"Workflow '{workflow.name}' has no active version"
        )

    # Check webhook trigger & secret verification
    trigger = session.exec(
        select(WorkflowTrigger).where(
            WorkflowTrigger.workflow_id == workflow.id,
            WorkflowTrigger.trigger_type == "webhook",
            WorkflowTrigger.enabled == True,  # noqa: E712
        )
    ).first()

    if trigger and trigger.webhook_secret:
        if x_nextgen_secret != trigger.webhook_secret:
            raise HTTPException(status_code=401, detail="Invalid X-NextGen-Secret header token")

    version = session.get(WorkflowVersion, workflow.active_version_id)
    if not version:
        raise HTTPException(status_code=500, detail="Active workflow version record missing")

    graph_json = json.loads(version.graph_json)

    # Extract JSON body or query params
    payload: dict[str, Any] = {}
    try:
        payload = await request.json()
    except Exception:
        payload = dict(request.query_params)

    # Standardize input state key
    initial_input = payload if isinstance(payload, dict) else {"payload": payload}

    run = Run(
        workflow_version_id=version.id,
        status=RunStatus.running,
    )
    session.add(run)
    session.commit()
    session.refresh(run)

    def _session_factory():
        return Session(get_engine())

    await executor.start_run(
        session_factory=_session_factory,
        run_id=run.id,
        graph_json=graph_json,
        initial_state=initial_input,
    )

    return {
        "run_id": run.id,
        "status": "running",
        "workflow_id": workflow.id,
        "workflow_name": workflow.name,
    }
