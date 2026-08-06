"""Unit tests for High-Accuracy Hybrid RAG Search (Markdown Header Chunking & RRF Fusion)."""

import pytest
from unittest.mock import AsyncMock, patch

from app import github_rag, vectorstore


def test_markdown_section_chunker():
    markdown_doc = """
# Capital One Senior Role
Distinguished Engineer leading Generative AI platforms.

# Requirements
- 10+ years distributed systems
- Python, Go, Rust

# Salary & Compensation
Competitive base pay and equity grants.
"""
    chunks = github_rag.markdown_section_chunker(markdown_doc, max_chunk_size=100)
    assert len(chunks) >= 2
    assert "Capital One" in chunks[0]


@pytest.mark.asyncio
async def test_hybrid_query_store():
    mock_vector_docs = [
        {"content": "Generic engineering role details", "distance": 0.3, "metadata": {}},
        {"content": "Capital One Distinguished Engineer role details", "distance": 0.1, "metadata": {}},
    ]

    with patch("app.vectorstore.query_store", new_callable=AsyncMock) as mock_qs:
        mock_qs.return_value = mock_vector_docs

        results = await vectorstore.hybrid_query_store(
            store_name="interview_vault",
            query_text="give jd of capital one",
            top_k=5,
        )

        assert len(results) == 2
        assert "Capital One" in results[0]["content"]
