"""REST API routes for GitHub Repository RAG status and on-demand ingestion."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.github_rag import get_github_sync_status, sync_github_repo

router = APIRouter(prefix="/api/github", tags=["github"])


class GitHubSyncPayload(BaseModel):
    owner: str = "vbelle"
    repo: str = "Interview"
    branch: str | None = None
    token: str | None = None
    target_collection: str = "interview_vault"
    reset: bool = False


@router.get("/status")
def status(owner: str = "vbelle", repo: str = "Interview"):
    """Returns status of GitHub repository RAG indexing."""
    return get_github_sync_status(owner, repo)


@router.post("/sync")
async def sync(payload: GitHubSyncPayload):
    """Triggers an on-demand sync of a GitHub repository into ChromaDB."""
    try:
        return await sync_github_repo(
            owner=payload.owner,
            repo=payload.repo,
            branch=payload.branch,
            token=payload.token,
            target_collection=payload.target_collection,
            reset=payload.reset,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
