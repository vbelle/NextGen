"""Unit tests for GitHub Repository RAG engine."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app import github_rag


def test_chunk_text():
    short = "GitHub repo text"
    assert github_rag.chunk_text(short, chunk_size=100) == ["GitHub repo text"]


def test_parse_github_file():
    path = "Jobhunting/jd/CapitalOne_DE.md"
    content = "# Capital One\nSenior Architect role #fintech [[Interview Notes]]"
    parsed = github_rag.parse_github_file(path, content)

    assert parsed["title"] == "CapitalOne_DE"
    assert parsed["rel_path"] == path
    assert "fintech" in parsed["tags"]
    assert "Interview Notes" in parsed["wikilinks"]


@pytest.mark.asyncio
async def test_sync_github_repo():
    mock_tree_data = {
        "tree": [
            {"path": "Jobhunting/CapitalOne.md", "type": "blob"},
        ]
    }

    mock_tree_resp = MagicMock()
    mock_tree_resp.status_code = 200
    mock_tree_resp.json.return_value = mock_tree_data

    mock_repo_resp = MagicMock()
    mock_repo_resp.status_code = 200
    mock_repo_resp.json.return_value = {"default_branch": "main"}

    mock_raw_resp = MagicMock()
    mock_raw_resp.status_code = 200
    mock_raw_resp.text = "# Capital One JD\nDistinguished Engineer position details"

    async def mock_get(url):
        if "trees" in url:
            return mock_tree_resp
        if "raw.githubusercontent" in url:
            return mock_raw_resp
        return mock_repo_resp

    with (
        patch("httpx.AsyncClient.get", side_effect=mock_get),
        patch("app.vectorstore.add_documents_with_metadata", new_callable=AsyncMock) as mock_add,
    ):
        status = await github_rag.sync_github_repo(owner="vbelle", repo="Interview")

        assert status["status"] == "ok"
        assert status["files_parsed"] == 1
        assert status["chunks_indexed"] == 1
        assert mock_add.called
