"""Unit tests for Obsidian Vault RAG pipeline."""

import pytest
from unittest.mock import AsyncMock, patch

from app import obsidian


def test_chunk_text():
    short = "Hello world"
    assert obsidian.chunk_text(short, chunk_size=100) == ["Hello world"]

    long_text = "A" * 120
    chunks = obsidian.chunk_text(long_text, chunk_size=50, overlap=10)
    assert len(chunks) > 1
    assert chunks[0] == "A" * 50


def test_parse_obsidian_note(tmp_path):
    note_file = tmp_path / "My Project.md"
    note_content = "---\ntitle: Note\n---\n# Header\n#finance [[Other Note]]\n"
    note_file.write_text(note_content, encoding="utf-8")

    parsed = obsidian.parse_obsidian_note(note_file)
    assert parsed["title"] == "My Project"
    assert "finance" in parsed["tags"]
    assert "Other Note" in parsed["wikilinks"]
    assert "# Header" in parsed["content"]


@pytest.mark.asyncio
async def test_sync_obsidian_vault(tmp_path):
    note1 = tmp_path / "Note 1.md"
    note1.write_text("# Note 1\nContent for note 1 with #tag1", encoding="utf-8")

    note2 = tmp_path / "Note 2.md"
    note2.write_text("# Note 2\nContent for note 2 referencing [[Note 1]]", encoding="utf-8")

    with patch("app.vectorstore.add_documents_with_metadata", new_callable=AsyncMock) as mock_add:
        status = await obsidian.sync_obsidian_vault(tmp_path)

        assert status["notes_parsed"] == 2
        assert status["chunks_indexed"] == 2
        assert mock_add.called
        call_args = mock_add.call_args[1]
        assert call_args["store_name"] == "obsidian_vault"
        assert len(call_args["documents"]) == 2
