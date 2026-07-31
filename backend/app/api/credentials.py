"""Credential REST endpoints. See contracts/rest-api.md §Credentials."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, col, select

from app import crypto
from app.db import get_session
from app.models.credential import Credential
from app.models.workflow import Workflow, WorkflowVersion

router = APIRouter(prefix="/api/credentials", tags=["credentials"])


class CredentialCreate(BaseModel):
    name: str
    value: str


class CredentialOut(BaseModel):
    id: str
    name: str
    created_at: str


@router.get("", response_model=list[CredentialOut])
def list_credentials(session: Session = Depends(get_session)) -> list[CredentialOut]:
    rows = session.exec(select(Credential)).all()
    return [CredentialOut(id=r.id, name=r.name, created_at=r.created_at.isoformat()) for r in rows]


@router.post("", response_model=CredentialOut, status_code=201)
def create_credential(
    body: CredentialCreate, session: Session = Depends(get_session)
) -> CredentialOut:
    existing = session.exec(select(Credential).where(Credential.name == body.name)).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Credential '{body.name}' already exists")
    cred = Credential(name=body.name, encrypted_value=crypto.encrypt(body.value))
    session.add(cred)
    session.commit()
    session.refresh(cred)
    return CredentialOut(id=cred.id, name=cred.name, created_at=cred.created_at.isoformat())


@router.delete("/{credential_id}", status_code=204)
def delete_credential(credential_id: str, session: Session = Depends(get_session)) -> None:
    cred = session.get(Credential, credential_id)
    if not cred:
        raise HTTPException(status_code=404, detail="Credential not found")

    # Hard-block deletion if any active workflow version references this credential.
    # graph_json is stored as a raw JSON string — a LIKE search for the UUID is
    # cheap, unambiguous (UUIDs are unique by construction), and avoids a full
    # deserialisation of every version's graph. See contracts/rest-api.md §Credentials.
    active_versions_with_cred = session.exec(
        select(WorkflowVersion)
        .join(Workflow, col(Workflow.active_version_id) == col(WorkflowVersion.id))
        .where(col(WorkflowVersion.graph_json).contains(credential_id))
    ).all()

    if active_versions_with_cred:
        # Resolve workflow names for a clear error message.
        workflow_ids = {v.workflow_id for v in active_versions_with_cred}
        workflows = session.exec(select(Workflow).where(col(Workflow.id).in_(workflow_ids))).all()
        names = ", ".join(f"'{w.name}'" for w in workflows)
        raise HTTPException(
            status_code=409,
            detail=(
                f"Cannot delete credential '{cred.name}': it is referenced by the active "
                f"version of workflow(s) {names}. Remove the credential from those workflows "
                "first, or deactivate those workflows."
            ),
        )

    session.delete(cred)
    session.commit()
