"""Contract test for GET /api/tools — lists built-in tool implementations a
Tool node's implementation_ref can point at (User Story 11). Not in the
original tasks.md (same reasoning as vector_stores.py's endpoints for the
Memory node): the canvas needs a real list of valid refs to offer, not free
text prone to typos."""

from __future__ import annotations

import os

os.environ.setdefault("NEXTGEN_APP_PASSWORD", "test-password")
os.environ.setdefault("NEXTGEN_CREDENTIAL_KEY", "kQq4v2v7v3o5b1yqjq7c9m3n8p0r2s4t6u8w0x2y4z6=")

import pytest
from fastapi.testclient import TestClient

from app.db import init_db
from app.main import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXTGEN_DB_PATH", str(tmp_path / "test.db"))
    init_db()
    with TestClient(app) as c:
        c.post("/api/auth/login", json={"password": "test-password"})
        yield c


def test_list_tools_returns_builtin_registry(client):
    res = client.get("/api/tools")
    assert res.status_code == 200, res.text
    refs = {t["implementation_ref"] for t in res.json()}
    assert {"calculator", "current_datetime", "word_count"} <= refs
