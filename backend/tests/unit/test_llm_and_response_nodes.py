"""Unit tests for LLM/Response node execution functions — deliberately don't go
through the compiled graph (so they run on any Python 3.10+, unlike the Input
node's interrupt() which needs 3.11 — see integration/test_core_loop.py)."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch

os.environ.setdefault("NEXTGEN_APP_PASSWORD", "test-password")
os.environ.setdefault("NEXTGEN_CREDENTIAL_KEY", "kQq4v2v7v3o5b1yqjq7c9m3n8p0r2s4t6u8w0x2y4z6=")

import pytest

from app.graph.nodes import llm_node, response_node


@pytest.mark.asyncio
async def test_llm_node_success_renders_previous_and_calls_provider():
    state = {
        "variables": {},
        "node_outputs": {"__latest__": "Ada"},
        "retry_counts": {},
        "last_output_port": {},
    }
    with patch("app.graph.nodes.llm_node._get_provider") as get_provider:
        mock_provider = AsyncMock()
        mock_provider.generate.return_value = "Hello Ada!"
        get_provider.return_value = mock_provider

        result = await llm_node.execute(
            "llm1", {"model": "llama3.2", "prompt": "Say hello to {{previous}}"}, state
        )

    assert result["last_output_port"]["llm1"] == "success"
    assert result["node_outputs"]["llm1"] == "Hello Ada!"
    assert mock_provider.generate.call_args.kwargs["prompt"] == "Say hello to Ada"


@pytest.mark.asyncio
async def test_llm_node_unresolved_variable_routes_to_failure_not_exception():
    """FR-025: a missing {{variable}} reference is the *node's* failure, never a
    silent empty string and never an unhandled exception that crashes the run."""
    state = {"variables": {}, "node_outputs": {}, "retry_counts": {}, "last_output_port": {}}
    result = await llm_node.execute(
        "llm1", {"model": "llama3.2", "prompt": "Use {{missing_var}}"}, state
    )
    assert result["last_output_port"]["llm1"] == "failure"
    assert "missing_var" in str(result["node_outputs"]["llm1"])


@pytest.mark.asyncio
async def test_response_node_renders_previous_and_sets_dunder_response_key():
    state = {
        "variables": {},
        "node_outputs": {"__latest__": "Hello Ada!"},
        "retry_counts": {},
        "last_output_port": {},
    }
    result = await response_node.execute("resp1", {"content": "{{previous}}"}, state)
    assert result["node_outputs"]["__response__"] == "Hello Ada!"
    assert result["last_output_port"]["resp1"] == "default"
