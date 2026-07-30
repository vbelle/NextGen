"""Workflow CRUD/versioning REST endpoints. See contracts/rest-api.md §Workflows."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.db import get_session
from app.graph.validation import validate_graph
from app.models.run import Run
from app.models.workflow import Workflow, WorkflowVersion

router = APIRouter(prefix="/api/workflows", tags=["workflows"])


class WorkflowCreate(BaseModel):
    name: str
    graph_json: dict


class WorkflowVersionCreate(BaseModel):
    graph_json: dict


class WorkflowOut(BaseModel):
    id: str
    name: str
    active_version_id: str | None
    created_at: str


class WorkflowVersionOut(BaseModel):
    id: str
    version_number: int
    created_at: str


class WorkflowVersionDetail(WorkflowVersionOut):
    graph_json: dict


def _validate_or_422(graph_json: dict) -> None:
    result = validate_graph(graph_json)
    if not result.is_valid:
        raise HTTPException(
            status_code=422,
            detail={
                "detail": "Workflow graph failed validation",
                "errors": [
                    {"field": i.node_id or i.edge_id or "graph", "issue": i.message}
                    for i in result.issues
                ],
            },
        )


@router.get("", response_model=list[WorkflowOut])
def list_workflows(session: Session = Depends(get_session)) -> list[WorkflowOut]:
    rows = session.exec(select(Workflow)).all()
    return [
        WorkflowOut(
            id=w.id,
            name=w.name,
            active_version_id=w.active_version_id,
            created_at=w.created_at.isoformat(),
        )
        for w in rows
    ]


@router.post("", response_model=WorkflowOut, status_code=201)
def create_workflow(body: WorkflowCreate, session: Session = Depends(get_session)) -> WorkflowOut:
    existing = session.exec(select(Workflow).where(Workflow.name == body.name)).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail={
                "detail": f"Workflow name '{body.name}' already in use",
                "existing_id": existing.id,
            },
        )
    _validate_or_422(body.graph_json)

    workflow = Workflow(name=body.name)
    session.add(workflow)
    session.flush()  # assign workflow.id without committing yet

    version = WorkflowVersion(
        workflow_id=workflow.id, version_number=1, graph_json=json.dumps(body.graph_json)
    )
    session.add(version)
    session.flush()

    workflow.active_version_id = version.id
    session.add(workflow)
    session.commit()
    session.refresh(workflow)
    return WorkflowOut(
        id=workflow.id,
        name=workflow.name,
        active_version_id=workflow.active_version_id,
        created_at=workflow.created_at.isoformat(),
    )


@router.get("/{workflow_id}")
def get_workflow(workflow_id: str, session: Session = Depends(get_session)) -> dict:
    workflow = session.get(Workflow, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    version = (
        session.get(WorkflowVersion, workflow.active_version_id)
        if workflow.active_version_id
        else None
    )
    return {
        "id": workflow.id,
        "name": workflow.name,
        "active_version_id": workflow.active_version_id,
        "created_at": workflow.created_at.isoformat(),
        "graph_json": json.loads(version.graph_json) if version else None,
    }


@router.get("/{workflow_id}/versions", response_model=list[WorkflowVersionOut])
def list_versions(
    workflow_id: str, session: Session = Depends(get_session)
) -> list[WorkflowVersionOut]:
    rows = session.exec(
        select(WorkflowVersion)
        .where(WorkflowVersion.workflow_id == workflow_id)
        .order_by(WorkflowVersion.version_number)
    ).all()
    return [
        WorkflowVersionOut(
            id=v.id, version_number=v.version_number, created_at=v.created_at.isoformat()
        )
        for v in rows
    ]


@router.get("/{workflow_id}/versions/{version_id}", response_model=WorkflowVersionDetail)
def get_version(
    workflow_id: str, version_id: str, session: Session = Depends(get_session)
) -> WorkflowVersionDetail:
    version = session.get(WorkflowVersion, version_id)
    if not version or version.workflow_id != workflow_id:
        raise HTTPException(status_code=404, detail="Version not found")
    return WorkflowVersionDetail(
        id=version.id,
        version_number=version.version_number,
        created_at=version.created_at.isoformat(),
        graph_json=json.loads(version.graph_json),
    )


@router.post("/{workflow_id}/versions", response_model=WorkflowVersionOut, status_code=201)
def create_version(
    workflow_id: str, body: WorkflowVersionCreate, session: Session = Depends(get_session)
) -> WorkflowVersionOut:
    workflow = session.get(Workflow, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    _validate_or_422(body.graph_json)

    latest = session.exec(
        select(WorkflowVersion)
        .where(WorkflowVersion.workflow_id == workflow_id)
        .order_by(WorkflowVersion.version_number.desc())
    ).first()
    next_number = (latest.version_number + 1) if latest else 1

    version = WorkflowVersion(
        workflow_id=workflow_id, version_number=next_number, graph_json=json.dumps(body.graph_json)
    )
    session.add(version)
    session.commit()
    session.refresh(version)
    # Note (plan.md rest-api.md): saving does NOT auto-activate. A separate
    # /activate call is required to make an edit live for chat invocation.
    return WorkflowVersionOut(
        id=version.id,
        version_number=version.version_number,
        created_at=version.created_at.isoformat(),
    )


@router.post("/{workflow_id}/activate/{version_id}", response_model=WorkflowOut)
def activate_version(
    workflow_id: str, version_id: str, session: Session = Depends(get_session)
) -> WorkflowOut:
    workflow = session.get(Workflow, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    version = session.get(WorkflowVersion, version_id)
    if not version or version.workflow_id != workflow_id:
        raise HTTPException(status_code=404, detail="Version not found")

    workflow.active_version_id = version_id
    session.add(workflow)
    session.commit()
    session.refresh(workflow)
    return WorkflowOut(
        id=workflow.id,
        name=workflow.name,
        active_version_id=workflow.active_version_id,
        created_at=workflow.created_at.isoformat(),
    )


@router.delete("/{workflow_id}", status_code=204)
def delete_workflow(workflow_id: str, session: Session = Depends(get_session)) -> None:
    workflow = session.get(Workflow, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    version_ids = [
        v.id
        for v in session.exec(
            select(WorkflowVersion).where(WorkflowVersion.workflow_id == workflow_id)
        ).all()
    ]
    has_runs = (
        version_ids
        and session.exec(select(Run).where(Run.workflow_version_id.in_(version_ids))).first()
    )
    if has_runs:
        raise HTTPException(
            status_code=409, detail="Cannot delete a workflow with run history (Constitution VII)"
        )
    for vid in version_ids:
        session.delete(session.get(WorkflowVersion, vid))
    session.delete(workflow)
    session.commit()
