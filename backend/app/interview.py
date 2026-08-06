"""Interview Repository RAG Engine: parses interview prep docs, job descriptions, resume guides,
and technical cheat sheets from /Users/raj/Documents/Interview into ChromaDB."""

from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import re
from typing import Any

from app import vectorstore
from app.logging import get_logger

logger = get_logger(__name__)

INTERVIEW_COLLECTION = "interview_vault"
_LAST_SYNC_INFO: dict[str, Any] = {
    "last_synced_at": None,
    "files_parsed": 0,
    "chunks_indexed": 0,
    "vault_path": None,
}

_EXCLUDED_DIRS = {
    "node_modules",
    ".git",
    ".obsidian",
    "__pycache__",
    ".rtk",
    ".trash",
}


def get_interview_vault_path() -> Path:
    p = os.environ.get("INTERVIEW_VAULT_PATH", "/Users/raj/Documents/Interview")
    path = Path(p).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def markdown_section_chunker(
    text: str, max_chunk_size: int = 1500, overlap: int = 150
) -> list[str]:
    """Chunks markdown documents structurally by section headers (#, ##, ###)."""
    cleaned = text.strip()
    if not cleaned:
        return []

    header_pattern = r"(?=\n#{1,3}\s+)"
    raw_sections = re.split(header_pattern, "\n" + cleaned)
    sections = [s.strip() for s in raw_sections if s.strip()]

    chunks: list[str] = []
    current_chunk = ""

    for sec in sections:
        if len(current_chunk) + len(sec) <= max_chunk_size:
            current_chunk = (current_chunk + "\n\n" + sec).strip()
        else:
            if current_chunk:
                chunks.append(current_chunk)
            if len(sec) > max_chunk_size:
                start = 0
                while start < len(sec):
                    end = start + max_chunk_size
                    chunks.append(sec[start:end].strip())
                    start += max_chunk_size - overlap
                current_chunk = ""
            else:
                current_chunk = sec

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def parse_interview_file(file_path: Path, base_dir: Path) -> dict[str, Any]:
    """Parses an interview note/doc into metadata and text content."""
    content = file_path.read_text(encoding="utf-8", errors="replace")
    rel_path = str(file_path.relative_to(base_dir))

    tags = re.findall(r"#([a-zA-Z0-9_\-/]+)", content)
    wikilinks = re.findall(r"\[\[([^\]]+)\]\]", content)

    clean_content = re.sub(r"^---[\s\S]*?---\n", "", content)

    return {
        "title": file_path.stem,
        "rel_path": rel_path,
        "content": clean_content.strip(),
        "tags": list(set(tags)),
        "wikilinks": list(set(wikilinks)),
    }


async def sync_interview_vault(vault_dir: Path | None = None) -> dict[str, Any]:
    """Scans the Interview vault directory and indexes all Markdown/text documents into ChromaDB."""
    target_dir = vault_dir or get_interview_vault_path()
    logger.info("Starting Interview Vault RAG sync for '%s'", target_dir)

    all_files: list[Path] = []
    for root, dirs, files in os.walk(target_dir):
        dirs[:] = [d for d in dirs if d not in _EXCLUDED_DIRS]
        for f in files:
            if f.endswith((".md", ".txt")):
                all_files.append(Path(root) / f)

    documents: list[str] = []
    metadatas: list[dict[str, str]] = []
    ids: list[str] = []

    files_parsed = 0
    for file_path in all_files:
        try:
            parsed = parse_interview_file(file_path, target_dir)
            chunks = markdown_section_chunker(parsed["content"])
            if not chunks:
                continue

            files_parsed += 1
            tags_str = ", ".join(parsed["tags"])
            links_str = ", ".join(parsed["wikilinks"])

            for idx, chunk in enumerate(chunks):
                safe_name = re.sub(r"[^a-zA-Z0-9_\-]", "_", parsed["rel_path"])
                chunk_id = f"interview-{safe_name}-{idx}"
                doc_text = (
                    f"File: {parsed['rel_path']}\n"
                    f"Title: {parsed['title']}\n"
                    f"Tags: {tags_str}\n"
                    f"Content:\n{chunk}"
                )

                documents.append(doc_text)
                metadatas.append(
                    {
                        "source": parsed["rel_path"],
                        "title": parsed["title"],
                        "tags": tags_str,
                        "wikilinks": links_str,
                    }
                )
                ids.append(chunk_id)
        except Exception as exc:
            logger.warning("Failed to parse Interview file '%s': %s", file_path, exc)

    if documents:
        await vectorstore.add_documents_with_metadata(
            store_name=INTERVIEW_COLLECTION,
            documents=documents,
            metadatas=metadatas,
            ids=ids,
        )

    now_iso = datetime.now(timezone.utc).isoformat()
    _LAST_SYNC_INFO["last_synced_at"] = now_iso
    _LAST_SYNC_INFO["files_parsed"] = files_parsed
    _LAST_SYNC_INFO["chunks_indexed"] = len(documents)
    _LAST_SYNC_INFO["vault_path"] = str(target_dir)

    logger.info(
        "Interview Vault RAG sync complete: %d files, %d chunks indexed",
        files_parsed,
        len(documents),
    )
    return get_interview_status()


def get_interview_status() -> dict[str, Any]:
    vault_path = get_interview_vault_path()
    file_count = 0
    for root, dirs, files in os.walk(vault_path):
        dirs[:] = [d for d in dirs if d not in _EXCLUDED_DIRS]
        for f in files:
            if f.endswith((".md", ".txt")):
                file_count += 1

    return {
        "vault_path": str(vault_path),
        "total_files": file_count,
        "last_synced_at": _LAST_SYNC_INFO["last_synced_at"],
        "files_parsed": _LAST_SYNC_INFO["files_parsed"],
        "chunks_indexed": _LAST_SYNC_INFO["chunks_indexed"],
        "collection_name": INTERVIEW_COLLECTION,
    }
