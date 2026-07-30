"""Vector store REST endpoints (User Story 10). A "store" here is a Chroma
collection — see app/vectorstore.py for why there's no separate DB table.
Minimal by design (create + list + add documents): this exists so the Memory
node is genuinely testable/usable, not to be a full document-management UI."""

from __future__ import annotations

import chromadb.errors
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app import vectorstore

router = APIRouter(prefix="/api/vector-stores", tags=["vector-stores"])


class VectorStoreCreate(BaseModel):
    name: str


class VectorStoreOut(BaseModel):
    name: str


class DocumentsAdd(BaseModel):
    documents: list[str]


@router.get("", response_model=list[VectorStoreOut])
def list_vector_stores() -> list[VectorStoreOut]:
    return [VectorStoreOut(name=n) for n in vectorstore.list_stores()]


@router.post("", response_model=VectorStoreOut, status_code=201)
def create_vector_store(body: VectorStoreCreate) -> VectorStoreOut:
    if body.name in vectorstore.list_stores():
        raise HTTPException(status_code=409, detail=f"Vector store '{body.name}' already exists")
    try:
        vectorstore.create_store(body.name)
    except chromadb.errors.InvalidArgumentError as exc:
        # Chroma's own collection-naming rules (3-512 chars, [a-zA-Z0-9._-],
        # must start/end alphanumeric) — surfaced as a clean 422 rather than
        # an unhandled 500.
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return VectorStoreOut(name=body.name)


@router.post("/{name}/documents", status_code=201)
async def add_documents(name: str, body: DocumentsAdd) -> dict:
    try:
        await vectorstore.add_documents(name, body.documents)
    except vectorstore.VectorStoreNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"added": len(body.documents)}
