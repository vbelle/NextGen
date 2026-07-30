"""Contract test for the vector store REST endpoints (User Story 10) — create,
list, and add documents. Not in the original tasks.md (store management wasn't
originally scoped for this story), added because building the Memory node
without any way to put content into a store isn't genuinely testable/usable —
see app/vectorstore.py's docstring for the full design rationale."""

from __future__ import annotations

import hashlib
import os

os.environ.setdefault("NEXTGEN_APP_PASSWORD", "test-password")
os.environ.setdefault("NEXTGEN_CREDENTIAL_KEY", "kQq4v2v7v3o5b1yqjq7c9m3n8p0r2s4t6u8w0x2y4z6=")

import pytest
from chromadb import EmbeddingFunction
from fastapi.testclient import TestClient

from app import vectorstore
from app.db import init_db
from app.main import app


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
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXTGEN_DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("NEXTGEN_VECTOR_STORE_PATH", str(tmp_path / "vector_stores"))
    monkeypatch.setattr(vectorstore, "_embedding_fn_override", FakeEmbeddingFunction())
    monkeypatch.setattr(vectorstore, "_client_cache", {})
    init_db()
    with TestClient(app) as c:
        c.post("/api/auth/login", json={"password": "test-password"})
        yield c


def test_create_and_list_store(client):
    res = client.post("/api/vector-stores", json={"name": "docs"})
    assert res.status_code == 201, res.text
    assert res.json() == {"name": "docs"}

    listed = client.get("/api/vector-stores").json()
    assert listed == [{"name": "docs"}]


def test_create_duplicate_store_rejected(client):
    client.post("/api/vector-stores", json={"name": "docs"})
    res = client.post("/api/vector-stores", json={"name": "docs"})
    assert res.status_code == 409


def test_add_documents_to_store(client):
    client.post("/api/vector-stores", json={"name": "docs"})
    res = client.post(
        "/api/vector-stores/docs/documents",
        json={"documents": ["first doc", "second doc"]},
    )
    assert res.status_code == 201, res.text
    assert res.json() == {"added": 2}


def test_add_documents_to_nonexistent_store_404s(client):
    res = client.post("/api/vector-stores/ghost/documents", json={"documents": ["doc"]})
    assert res.status_code == 404


def test_create_store_with_invalid_name_rejected(client):
    # Chroma's own collection-naming rule requires >= 3 characters.
    res = client.post("/api/vector-stores", json={"name": "kb"})
    assert res.status_code == 422
