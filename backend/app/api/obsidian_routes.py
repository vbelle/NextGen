"""REST API routes for Obsidian Vault RAG status and on-demand ingestion."""

from __future__ import annotations

from fastapi import APIRouter

from app.obsidian import get_obsidian_status, sync_obsidian_vault

router = APIRouter(prefix="/api/obsidian", tags=["obsidian"])


@router.get("/status")
def status():
    """Returns Obsidian vault indexing status."""
    return get_obsidian_status()


@router.post("/sync")
async def sync():
    """Triggers an on-demand sync of the Obsidian vault into ChromaDB."""
    return await sync_obsidian_vault()
