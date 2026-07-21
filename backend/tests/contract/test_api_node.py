"""Contract test for the API node's success and failure execution paths (T048,
User Story 4). Exercises app.graph.nodes.api_node.execute() directly against a real
httpx.AsyncClient wired to an httpx.MockTransport, so requests never touch the
network but still go through real request/response handling (headers, JSON
parsing, timeouts) — not a hand-rolled fake. See contracts/graph-schema.md's api
config and research.md §9 for credential resolution."""

from __future__ import annotations

import os

os.environ.setdefault("NEXTGEN_APP_PASSWORD", "test-password")
os.environ.setdefault("NEXTGEN_CREDENTIAL_KEY", "kQq4v2v7v3o5b1yqjq7c9m3n8p0r2s4t6u8w0x2y4z6=")

import httpx
import pytest
from sqlmodel import Session

from app.crypto import encrypt
from app.db import get_engine, init_db
from app.graph.nodes import api_node
from app.graph.templating import VariableNotSetError
from app.models.credential import Credential

BASE_STATE = {"variables": {}, "node_outputs": {}, "retry_counts": {}, "last_output_port": {}}


def _state(**overrides):
    state = {k: dict(v) if isinstance(v, dict) else v for k, v in BASE_STATE.items()}
    state.update(overrides)
    return state


def _patch_transport(monkeypatch, handler):
    """Makes api_node's internal `httpx.AsyncClient(timeout=...)` construction use
    a MockTransport instead of hitting the network, while still exercising the
    real AsyncClient request/response machinery."""
    transport = httpx.MockTransport(handler)
    real_async_client = httpx.AsyncClient

    def factory(*, timeout):
        return real_async_client(transport=transport, timeout=timeout)

    monkeypatch.setattr(httpx, "AsyncClient", factory)


@pytest.fixture()
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXTGEN_DB_PATH", str(tmp_path / "test.db"))
    init_db()


@pytest.mark.asyncio
async def test_2xx_routes_to_success_with_parsed_json_body(monkeypatch):
    def handler(request):
        return httpx.Response(200, json={"ok": True})

    _patch_transport(monkeypatch, handler)
    result = await api_node.execute(
        "api1", {"method": "GET", "url": "https://example.test/thing"}, _state()
    )
    assert result["last_output_port"]["api1"] == "success"
    assert result["node_outputs"]["api1"]["status_code"] == 200
    assert result["node_outputs"]["api1"]["body"] == {"ok": True}


@pytest.mark.asyncio
async def test_non_2xx_routes_to_failure(monkeypatch):
    def handler(request):
        return httpx.Response(500, text="server error")

    _patch_transport(monkeypatch, handler)
    result = await api_node.execute(
        "api1", {"method": "GET", "url": "https://example.test/thing"}, _state()
    )
    assert result["last_output_port"]["api1"] == "failure"
    assert result["node_outputs"]["api1"]["status_code"] == 500


@pytest.mark.asyncio
async def test_connection_error_routes_to_failure_not_exception(monkeypatch):
    def handler(request):
        raise httpx.ConnectError("connection refused", request=request)

    _patch_transport(monkeypatch, handler)
    result = await api_node.execute(
        "api1", {"method": "GET", "url": "https://example.test/thing"}, _state()
    )
    assert result["last_output_port"]["api1"] == "failure"
    assert "connection refused" in result["node_outputs"]["api1"]["error"]


@pytest.mark.asyncio
async def test_unresolved_variable_in_url_routes_to_failure(monkeypatch):
    # No transport patch needed — render_template must raise before any request.
    result = await api_node.execute(
        "api1", {"method": "GET", "url": "https://example.test/{{missing}}"}, _state()
    )
    assert result["last_output_port"]["api1"] == "failure"
    assert "missing" in result["node_outputs"]["api1"]["error"]


@pytest.mark.asyncio
async def test_credential_resolves_to_bearer_authorization_header(monkeypatch, db):
    with Session(get_engine()) as session:
        cred = Credential(name="my-api-key", encrypted_value=encrypt("s3cr3t-token"))
        session.add(cred)
        session.commit()
        session.refresh(cred)
        credential_id = cred.id

    captured = {}

    def handler(request):
        captured["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={"ok": True})

    _patch_transport(monkeypatch, handler)
    result = await api_node.execute(
        "api1",
        {"method": "GET", "url": "https://example.test/thing", "credential_id": credential_id},
        _state(),
    )
    assert result["last_output_port"]["api1"] == "success"
    assert captured["auth"] == "Bearer s3cr3t-token"


@pytest.mark.asyncio
async def test_explicit_authorization_header_overrides_credential(monkeypatch, db):
    with Session(get_engine()) as session:
        cred = Credential(name="my-api-key", encrypted_value=encrypt("s3cr3t-token"))
        session.add(cred)
        session.commit()
        session.refresh(cred)
        credential_id = cred.id

    captured = {}

    def handler(request):
        captured["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={"ok": True})

    _patch_transport(monkeypatch, handler)
    result = await api_node.execute(
        "api1",
        {
            "method": "GET",
            "url": "https://example.test/thing",
            "credential_id": credential_id,
            "headers": {"Authorization": "Custom explicit-value"},
        },
        _state(),
    )
    assert result["last_output_port"]["api1"] == "success"
    assert captured["auth"] == "Custom explicit-value"


@pytest.mark.asyncio
async def test_unresolved_variable_raises_via_templating_not_silently(monkeypatch):
    """Sanity check that api_node relies on the same VariableNotSetError as every
    other node type, rather than a bespoke unresolved-variable representation."""
    from app.graph.templating import render_template

    with pytest.raises(VariableNotSetError):
        render_template("{{missing}}", _state())
