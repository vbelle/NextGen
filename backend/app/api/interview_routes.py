"""REST API routes for Interview Repository RAG status and on-demand ingestion."""

from __future__ import annotations

from fastapi import APIRouter

from app.interview import get_interview_status, sync_interview_vault

router = APIRouter(prefix="/api/interview", tags=["interview"])


@router.get("/status")
def status():
    """Returns Interview vault indexing status."""
    return get_interview_status()


@router.post("/sync")
async def sync():
    """Triggers an on-demand sync of the Interview vault into ChromaDB."""
    return await sync_interview_vault()
