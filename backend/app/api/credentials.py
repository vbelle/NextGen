"""Credential REST endpoints. See contracts/rest-api.md §Credentials."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app import crypto
from app.db import get_session
from app.models.credential import Credential

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
    session.delete(cred)
    session.commit()
