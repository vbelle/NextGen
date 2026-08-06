"""Unit tests for Interview Vault RAG engine and interview_search tool."""

import pytest
from unittest.mock import AsyncMock, patch

from app import interview
from app.graph.tool_registry import get_tool_implementation, interview_search


def test_chunk_text():
    short = "Interview prep summary"
    assert interview.chunk_text(short, chunk_size=100) == ["Interview prep summary"]


def test_parse_interview_file(tmp_path):
    doc_file = tmp_path / "CapitalOne_Prep.md"
    doc_file.write_text(
        "# Capital One Prep\nFocus on #distributed-systems and [[System Architecture]].\n",
        encoding="utf-8",
    )

    parsed = interview.parse_interview_file(doc_file, tmp_path)
    assert parsed["title"] == "CapitalOne_Prep"
    assert "distributed-systems" in parsed["tags"]
    assert "System Architecture" in parsed["wikilinks"]


@pytest.mark.asyncio
async def test_sync_interview_vault(tmp_path):
    doc1 = tmp_path / "Prep1.md"
    doc1.write_text("# Prep 1\nNotes on system design and #ai", encoding="utf-8")

    with patch("app.vectorstore.add_documents_with_metadata", new_callable=AsyncMock) as mock_add:
        status = await interview.sync_interview_vault(tmp_path)

        assert status["files_parsed"] == 1
        assert status["chunks_indexed"] == 1
        assert mock_add.called
        call_args = mock_add.call_args[1]
        assert call_args["store_name"] == "interview_vault"


def test_interview_search_tool():
    tool = get_tool_implementation("interview_search")
    assert tool is not None
    assert tool.args_schema.__name__ == "InterviewSearchArgs"

    mock_results = [
        {"content": "File: Prep1.md\nTitle: Prep 1\nContent:\nSystem design notes"},
    ]
    with patch("app.vectorstore.query_store", new_callable=AsyncMock) as mock_query:
        mock_query.return_value = mock_results
        res = interview_search("system design")
        assert "System design notes" in res
