"""Vector store access for the Memory/Retrieval node (User Story 10).

2026-07-27 design decision: nothing in the spec/contracts named a vector store
backend, embeddings provider, or store-registration mechanism at all — a
bigger gap than the Loop node's — so this was asked rather than guessed.
Chosen: Chroma (embedded, no extra Docker service, persists to a local file —
fits the same "self-hosted, no extra infra" shape as SQLite) with embeddings
via Ollama, using chromadb's own built-in OllamaEmbeddingFunction rather than
wrapping langchain_ollama a second time.

A "vector store" in this app IS a Chroma collection — there's no separate
SQLModel table duplicating "which stores exist"; Chroma's own collection list
is the single source of truth, the same way the compiled LangGraph is the
source of truth for a workflow's execution paths (Constitution IV's spirit
applied here too).

Embedding calls go through the SAME process-wide semaphore
app/providers/ollama_provider.py uses for generation calls — FR-026's
"queue calls to the shared Ollama instance" concern applies just as much to
embeddings hitting that same instance."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import chromadb
from chromadb.api.models.Collection import Collection
from chromadb.utils.embedding_functions import OllamaEmbeddingFunction

from app.providers.ollama_provider import OLLAMA_SEMAPHORE

DEFAULT_EMBEDDING_MODEL = "nomic-embed-text"

_client_cache: dict[str, chromadb.ClientAPI] = {}
_embedding_fn_override: OllamaEmbeddingFunction | None = None


def get_vector_store_path() -> str:
    return os.environ.get("NEXTGEN_VECTOR_STORE_PATH", "./vector_stores")


def _get_client() -> chromadb.ClientAPI:
    path = get_vector_store_path()
    if path not in _client_cache:
        Path(path).mkdir(parents=True, exist_ok=True)
        _client_cache[path] = chromadb.PersistentClient(path=path)
    return _client_cache[path]


def _embedding_function() -> OllamaEmbeddingFunction:
    # Tests use monkeypatch.setattr(vectorstore, "_embedding_fn_override", ...)
    # to inject a fake, offline embedding function rather than needing a live
    # Ollama instance — monkeypatch handles cleanup between tests for free.
    if _embedding_fn_override is not None:
        return _embedding_fn_override
    base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    model_name = os.environ.get("NEXTGEN_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)
    return OllamaEmbeddingFunction(url=base_url, model_name=model_name)


class VectorStoreNotFoundError(Exception):
    def __init__(self, name: str):
        self.name = name
        super().__init__(f"Vector store '{name}' does not exist")


def list_stores() -> list[str]:
    return [c.name for c in _get_client().list_collections()]


def create_store(name: str) -> None:
    _get_client().create_collection(name=name, embedding_function=_embedding_function())


def _get_existing_collection(name: str) -> Collection:
    try:
        return _get_client().get_collection(name=name, embedding_function=_embedding_function())
    except chromadb.errors.NotFoundError as exc:
        raise VectorStoreNotFoundError(name) from exc


async def add_documents(store_name: str, documents: list[str]) -> None:
    collection = _get_existing_collection(store_name)
    ids = [f"{store_name}-{collection.count() + i}" for i in range(len(documents))]

    async with OLLAMA_SEMAPHORE:
        await asyncio.to_thread(collection.add, ids=ids, documents=documents)


async def query_store(store_name: str, query_text: str, top_k: int) -> list[dict]:
    collection = _get_existing_collection(store_name)

    async with OLLAMA_SEMAPHORE:
        result = await asyncio.to_thread(
            collection.query, query_texts=[query_text], n_results=top_k
        )

    documents = (result.get("documents") or [[]])[0]
    distances = (result.get("distances") or [[]])[0]
    return [{"content": doc, "distance": dist} for doc, dist in zip(documents, distances)]
