"""Unit tests for User Story 11: an LLM node's function-calling support.

Covers app/graph/nodes/llm_node.py's _make_tool() (building a LangChain
StructuredTool from a bound Tool node + writing its own audit row per
invocation) and execute()'s wiring of bound_tools into the provider call.
See tests/integration/test_tool_node.py (T073) for the full graph-level
proof that an LLM node can actually invoke a wired Tool node mid-generation."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch

os.environ.setdefault("NEXTGEN_APP_PASSWORD", "test-password")
os.environ.setdefault("NEXTGEN_CREDENTIAL_KEY", "kQq4v2v7v3o5b1yqjq7c9m3n8p0r2s4t6u8w0x2y4z6=")

import pytest
from sqlmodel import Session, select

from app.db import get_engine, init_db
from app.graph import tool_registry
from app.graph.nodes import llm_node
from app.models.run import NodeExecution

BASE_STATE = {"variables": {}, "node_outputs": {}, "retry_counts": {}, "last_output_port": {}}


def _state(**overrides):
    state = {k: dict(v) if isinstance(v, dict) else v for k, v in BASE_STATE.items()}
    state.update(overrides)
    return state


def test_make_tool_builds_structured_tool_from_binding():
    binding = llm_node.BoundTool(
        node_id="tool1",
        function_name="add",
        description="Adds numbers",
        implementation_ref="calculator",
    )
    tool = llm_node._make_tool(binding, run_id=None)
    assert tool.name == "add"
    assert tool.description == "Adds numbers"
    assert tool.args_schema.model_fields.keys() == {"expression"}


def test_make_tool_invocation_writes_audit_row_when_run_id_present(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXTGEN_DB_PATH", str(tmp_path / "test.db"))
    init_db()

    binding = llm_node.BoundTool(
        node_id="tool1",
        function_name="add",
        description="Adds numbers",
        implementation_ref="calculator",
    )
    tool = llm_node._make_tool(binding, run_id="run-abc")
    result = tool.func(expression="2 + 3")
    assert result == "5"

    with Session(get_engine()) as session:
        rows = session.exec(select(NodeExecution).where(NodeExecution.run_id == "run-abc")).all()
    assert len(rows) == 1
    row = rows[0]
    assert row.node_id == "tool1"
    assert row.node_type == "tool"
    assert row.output_port == "default"


def test_make_tool_invocation_without_run_id_skips_audit_write():
    binding = llm_node.BoundTool(
        node_id="tool1", function_name="add", description="Adds", implementation_ref="calculator"
    )
    tool = llm_node._make_tool(binding, run_id=None)
    # No NEXTGEN_DB_PATH/init_db() — if this tried to write, it would blow up.
    assert tool.func(expression="1 + 1") == "2"


def test_make_tool_unknown_implementation_ref_raises():
    binding = llm_node.BoundTool(
        node_id="tool1", function_name="ghost", description="?", implementation_ref="does-not-exist"
    )
    with pytest.raises(tool_registry.UnknownToolImplementationError):
        llm_node._make_tool(binding, run_id=None)


@pytest.mark.asyncio
async def test_execute_passes_bound_tools_to_provider():
    state = _state(node_outputs={"__latest__": "Ada"})
    config = {
        "model": "llama3.2",
        "prompt": "Say hello to {{previous}}",
        "bound_tools": [
            {
                "node_id": "tool1",
                "function_name": "add",
                "description": "Adds numbers",
                "implementation_ref": "calculator",
            }
        ],
    }
    with patch("app.graph.nodes.llm_node._get_provider") as get_provider:
        mock_provider = AsyncMock()
        mock_provider.generate.return_value = "Hello Ada!"
        get_provider.return_value = mock_provider

        result = await llm_node.execute("llm1", config, state)

    assert result["last_output_port"]["llm1"] == "success"
    passed_tools = mock_provider.generate.call_args.kwargs["tools"]
    assert passed_tools is not None
    assert len(passed_tools) == 1
    assert passed_tools[0].name == "add"


@pytest.mark.asyncio
async def test_execute_with_no_bound_tools_passes_none():
    state = _state(node_outputs={"__latest__": "Ada"})
    config = {"model": "llama3.2", "prompt": "Say hello to {{previous}}"}
    with patch("app.graph.nodes.llm_node._get_provider") as get_provider:
        mock_provider = AsyncMock()
        mock_provider.generate.return_value = "Hello Ada!"
        get_provider.return_value = mock_provider

        await llm_node.execute("llm1", config, state)

    assert mock_provider.generate.call_args.kwargs["tools"] is None
