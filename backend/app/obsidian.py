"""Obsidian Vault RAG Engine: parses Markdown notes, frontmatter, tags, and wikilinks,
and indexes them into ChromaDB for vector retrieval."""

from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import re
from typing import Any

from app.logging import get_logger
from app import vectorstore

logger = get_logger(__name__)

OBSIDIAN_COLLECTION = "obsidian_vault"
_LAST_SYNC_INFO: dict[str, Any] = {
    "last_synced_at": None,
    "notes_parsed": 0,
    "chunks_indexed": 0,
    "vault_path": None,
}


def get_vault_path() -> Path:
    p = os.environ.get("OBSIDIAN_VAULT_PATH", "./data/obsidian_vault")
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


def parse_obsidian_note(file_path: Path) -> dict[str, Any]:
    """Parses an Obsidian .md note into title, content, tags, and wikilinks."""
    content = file_path.read_text(encoding="utf-8", errors="replace")
    rel_path = file_path.name

    # Extract tags e.g. #finance #project
    tags = re.findall(r"#([a-zA-Z0-9_\-/]+)", content)
    # Extract wikilinks e.g. [[Note Name]]
    wikilinks = re.findall(r"\[\[([^\]]+)\]\]", content)

    # Strip YAML frontmatter if present
    clean_content = re.sub(r"^---[\s\S]*?---\n", "", content)

    return {
        "title": file_path.stem,
        "rel_path": rel_path,
        "content": clean_content.strip(),
        "tags": list(set(tags)),
        "wikilinks": list(set(wikilinks)),
    }


async def sync_obsidian_vault(vault_dir: Path | None = None) -> dict[str, Any]:
    """Scans the Obsidian vault directory and indexes all Markdown files into ChromaDB."""
    target_dir = vault_dir or get_vault_path()
    logger.info("Starting Obsidian Vault RAG sync for '%s'", target_dir)

    md_files = list(target_dir.rglob("*.md"))
    documents: list[str] = []
    metadatas: list[dict[str, str]] = []
    ids: list[str] = []

    notes_parsed = 0
    for file_path in md_files:
        try:
            parsed = parse_obsidian_note(file_path)
            chunks = markdown_section_chunker(parsed["content"])
            if not chunks:
                continue

            notes_parsed += 1
            tags_str = ", ".join(parsed["tags"])
            links_str = ", ".join(parsed["wikilinks"])

            for idx, chunk in enumerate(chunks):
                chunk_id = f"obsidian-{parsed['title']}-{idx}"
                doc_text = f"Title: {parsed['title']}\nTags: {tags_str}\nContent:\n{chunk}"

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
            logger.warning("Failed to parse Obsidian note '%s': %s", file_path, exc)

    if documents:
        await vectorstore.add_documents_with_metadata(
            store_name=OBSIDIAN_COLLECTION,
            documents=documents,
            metadatas=metadatas,
            ids=ids,
        )

    now_iso = datetime.now(timezone.utc).isoformat()
    _LAST_SYNC_INFO["last_synced_at"] = now_iso
    _LAST_SYNC_INFO["notes_parsed"] = notes_parsed
    _LAST_SYNC_INFO["chunks_indexed"] = len(documents)
    _LAST_SYNC_INFO["vault_path"] = str(target_dir)

    logger.info(
        "Obsidian Vault RAG sync complete: %d notes, %d chunks indexed",
        notes_parsed,
        len(documents),
    )
    return get_obsidian_status()


def get_obsidian_status() -> dict[str, Any]:
    vault_path = get_vault_path()
    note_count = len(list(vault_path.rglob("*.md")))
    return {
        "vault_path": str(vault_path),
        "total_vault_notes": note_count,
        "last_synced_at": _LAST_SYNC_INFO["last_synced_at"],
        "notes_parsed": _LAST_SYNC_INFO["notes_parsed"],
        "chunks_indexed": _LAST_SYNC_INFO["chunks_indexed"],
        "collection_name": OBSIDIAN_COLLECTION,
    }
