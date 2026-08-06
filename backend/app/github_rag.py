"""GitHub Repository RAG Engine: fetches notes, job descriptions, and markdown docs directly
from GitHub repositories via GitHub REST API and indexes them into ChromaDB."""

from __future__ import annotations

from datetime import datetime, timezone
import httpx
import os
import re
from typing import Any

from app import vectorstore
from app.logging import get_logger

logger = get_logger(__name__)

_EXCLUDED_PATH_PARTS = {
    "node_modules/",
    ".git/",
    ".obsidian/",
    "__pycache__/",
    ".rtk/",
    ".trash/",
}

_SYNC_STATUS_CACHE: dict[str, dict[str, Any]] = {}


def chunk_text(text: str, chunk_size: int = 600, overlap: int = 60) -> list[str]:
    cleaned = text.strip()
    if not cleaned:
        return []
    if len(cleaned) <= chunk_size:
        return [cleaned]
    chunks: list[str] = []
    start = 0
    while start < len(cleaned):
        end = start + chunk_size
        chunks.append(cleaned[start:end])
        start += chunk_size - overlap
    return chunks


def parse_github_file(path: str, content: str) -> dict[str, Any]:
    title = path.split("/")[-1].rsplit(".", 1)[0]
    tags = re.findall(r"#([a-zA-Z0-9_\-/]+)", content)
    wikilinks = re.findall(r"\[\[([^\]]+)\]\]", content)
    clean_content = re.sub(r"^---[\s\S]*?---\n", "", content)

    return {
        "title": title,
        "rel_path": path,
        "content": clean_content.strip(),
        "tags": list(set(tags)),
        "wikilinks": list(set(wikilinks)),
    }


async def sync_github_repo(
    owner: str = "vbelle",
    repo: str = "Interview",
    branch: str | None = None,
    token: str | None = None,
    target_collection: str = "interview_vault",
) -> dict[str, Any]:
    auth_token = token or os.environ.get("GITHUB_TOKEN", "").strip() or None
    headers = {"User-Agent": "NextGen-Agent-Platform"}
    if auth_token:
        headers["Authorization"] = f"token {auth_token}"

    logger.info(
        "Starting GitHub RAG sync for repo '%s/%s' into collection '%s'",
        owner,
        repo,
        target_collection,
    )

    async with httpx.AsyncClient(headers=headers, timeout=30.0) as client:
        # Detect default branch if not specified
        target_branch = branch
        if not target_branch:
            repo_resp = await client.get(f"https://api.github.com/repos/{owner}/{repo}")
            if repo_resp.status_code == 404:
                raise ValueError(
                    f"GitHub repo '{owner}/{repo}' not found or private (provide GITHUB_TOKEN)"
                )
            repo_resp.raise_for_status()
            target_branch = repo_resp.json().get("default_branch", "main")

        # Fetch full repository tree recursively
        tree_url = (
            f"https://api.github.com/repos/{owner}/{repo}/git/trees/{target_branch}?recursive=1"
        )
        tree_resp = await client.get(tree_url)
        if tree_resp.status_code == 404:
            raise ValueError(f"Could not access branch '{target_branch}' for repo '{owner}/{repo}'")
        tree_resp.raise_for_status()
        tree_data = tree_resp.json()

        items = tree_data.get("tree", [])
        valid_items = [
            item
            for item in items
            if item.get("type") == "blob"
            and item.get("path", "").endswith((".md", ".txt"))
            and not any(ex in item.get("path", "") for ex in _EXCLUDED_PATH_PARTS)
        ]

        documents: list[str] = []
        metadatas: list[dict[str, str]] = []
        ids: list[str] = []
        files_parsed = 0

        for item in valid_items:
            path = item["path"]
            raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{target_branch}/{path}"
            content_resp = await client.get(raw_url)
            if content_resp.status_code != 200:
                continue

            content = content_resp.text
            parsed = parse_github_file(path, content)
            chunks = chunk_text(parsed["content"])
            if not chunks:
                continue

            files_parsed += 1
            tags_str = ", ".join(parsed["tags"])
            links_str = ", ".join(parsed["wikilinks"])

            for idx, chunk in enumerate(chunks):
                safe_name = re.sub(r"[^a-zA-Z0-9_\-]", "_", path)
                chunk_id = f"github-{safe_name}-{idx}"
                doc_text = (
                    f"Repository: {owner}/{repo}\n"
                    f"File: {path}\n"
                    f"Title: {parsed['title']}\n"
                    f"Tags: {tags_str}\n"
                    f"Content:\n{chunk}"
                )

                documents.append(doc_text)
                metadatas.append(
                    {
                        "source": path,
                        "title": parsed["title"],
                        "tags": tags_str,
                        "wikilinks": links_str,
                        "repo": f"{owner}/{repo}",
                    }
                )
                ids.append(chunk_id)

        if documents:
            await vectorstore.add_documents_with_metadata(
                store_name=target_collection,
                documents=documents,
                metadatas=metadatas,
                ids=ids,
            )

        now_iso = datetime.now(timezone.utc).isoformat()
        cache_key = f"{owner}/{repo}"
        result_status = {
            "owner": owner,
            "repo": repo,
            "branch": target_branch,
            "target_collection": target_collection,
            "files_parsed": files_parsed,
            "chunks_indexed": len(documents),
            "last_synced_at": now_iso,
            "status": "ok",
        }
        _SYNC_STATUS_CACHE[cache_key] = result_status
        logger.info(
            "GitHub RAG sync complete for '%s/%s': %d files, %d chunks indexed into '%s'",
            owner,
            repo,
            files_parsed,
            len(documents),
            target_collection,
        )
        return result_status


def get_github_sync_status(owner: str = "vbelle", repo: str = "Interview") -> dict[str, Any]:
    cache_key = f"{owner}/{repo}"
    return _SYNC_STATUS_CACHE.get(
        cache_key,
        {
            "owner": owner,
            "repo": repo,
            "branch": "main",
            "files_parsed": 0,
            "chunks_indexed": 0,
            "last_synced_at": None,
            "status": "idle",
        },
    )
