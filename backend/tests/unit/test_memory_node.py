"""Unit tests for the Memory node and its underlying vector store
(app/vectorstore.py) — User Story 10. Uses a deterministic, offline fake
embedding function (real Ollama isn't available in this sandbox) against a
REAL Chroma instance persisted to a pytest tmp_path, so this exercises actual
Chroma add/query behavior, not a hand-rolled fake store. The fake embedding is
hash-based, not semantic, so these tests check plumbing (right count, content
round-trips, config resolution, error cases) rather than genuine relevance
ranking — that's Ollama's job in production. See
tests/integration/test_memory_node.py (T070) for the full graph-level proof."""

from __future__ import annotations

import hashlib
import os

os.environ.setdefault("NEXTGEN_APP_PASSWORD", "test-password")
os.environ.setdefault("NEXTGEN_CREDENTIAL_KEY", "kQq4v2v7v3o5b1yqjq7c9m3n8p0r2s4t6u8w0x2y4z6=")

import pytest
from chromadb import EmbeddingFunction

from app import vectorstore
from app.graph.nodes import memory_node


class FakeEmbeddingFunction(EmbeddingFunction):
    def __init__(self):
        pass

    @staticmethod
    def name():
        return "fake"

    def get_config(self):
        return {}

    @staticmethod
    def build_from_config(config):
        return FakeEmbeddingFunction()

    def __call__(self, input):
        return [[b / 255.0 for b in hashlib.sha256(text.encode()).digest()[:8]] for text in input]


@pytest.fixture()
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXTGEN_VECTOR_STORE_PATH", str(tmp_path / "vector_stores"))
    monkeypatch.setattr(vectorstore, "_embedding_fn_override", FakeEmbeddingFunction())
    monkeypatch.setattr(vectorstore, "_client_cache", {})
    yield


BASE_STATE = {"variables": {}, "node_outputs": {}, "retry_counts": {}, "last_output_port": {}}


def _state(**overrides):
    state = {k: dict(v) if isinstance(v, dict) else v for k, v in BASE_STATE.items()}
    state.update(overrides)
    return state


def test_create_store_then_list(store):
    assert vectorstore.list_stores() == []
    vectorstore.create_store("recipes")
    assert vectorstore.list_stores() == ["recipes"]


@pytest.mark.asyncio
async def test_add_and_query_round_trips_content(store):
    vectorstore.create_store("recipes")
    await vectorstore.add_documents(
        "recipes", ["apple pie recipe", "banana bread recipe", "car engine repair"]
    )
    results = await vectorstore.query_store("recipes", "dessert", top_k=2)
    assert len(results) == 2
    assert all("content" in r and "distance" in r for r in results)
    assert {r["content"] for r in results} <= {
        "apple pie recipe",
        "banana bread recipe",
        "car engine repair",
    }


@pytest.mark.asyncio
async def test_top_k_larger_than_store_returns_all(store):
    vectorstore.create_store("small")
    await vectorstore.add_documents("small", ["only one document"])
    results = await vectorstore.query_store("small", "anything", top_k=5)
    assert len(results) == 1


@pytest.mark.asyncio
async def test_query_nonexistent_store_raises(store):
    with pytest.raises(vectorstore.VectorStoreNotFoundError):
        await vectorstore.query_store("does-not-exist", "query", top_k=5)


@pytest.mark.asyncio
async def test_add_to_nonexistent_store_raises(store):
    with pytest.raises(vectorstore.VectorStoreNotFoundError):
        await vectorstore.add_documents("does-not-exist", ["doc"])


@pytest.mark.asyncio
async def test_memory_node_renders_query_template_and_returns_matches(store):
    vectorstore.create_store("kb-store")
    await vectorstore.add_documents("kb-store", ["Ada's favorite color is blue", "unrelated fact"])

    state = _state(variables={"person": "Ada"})
    result = await memory_node.execute(
        "mem1",
        {"vector_store_ref": "kb-store", "query": "What does {{person}} like?", "top_k": 2},
        state,
    )
    assert result["last_output_port"]["mem1"] == "default"
    assert len(result["node_outputs"]["mem1"]) == 2
    assert result["node_outputs"]["mem1"] == result["node_outputs"]["__latest__"]


@pytest.mark.asyncio
async def test_memory_node_missing_store_raises(store):
    state = _state()
    with pytest.raises(vectorstore.VectorStoreNotFoundError):
        await memory_node.execute(
            "mem1", {"vector_store_ref": "ghost", "query": "hi", "top_k": 3}, state
        )
