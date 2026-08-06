"""REST API routes for Interview Repository RAG status and on-demand ingestion."""

from fastapi import APIRouter, File, UploadFile, HTTPException

from app.interview import get_interview_status, get_interview_vault_path, sync_interview_vault

router = APIRouter(prefix="/api/interview", tags=["interview"])


@router.get("/status")
def status():
    """Returns Interview vault indexing status."""
    return get_interview_status()


@router.post("/sync")
async def sync():
    """Triggers an on-demand sync of the Interview vault into ChromaDB."""
    return await sync_interview_vault()


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """Uploads a note/doc file directly into the Interview vault."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename required")

    vault_dir = get_interview_vault_path()
    save_path = vault_dir / file.filename
    content = await file.read()
    save_path.write_bytes(content)

    # Auto sync after upload
    return await sync_interview_vault()
