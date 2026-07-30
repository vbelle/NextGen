"""Unit tests for the Code node's execution function and its sandbox (T057/T058,
User Story 6). Calls code_node.execute() directly — no compiled graph, no Input
node, so these run on this sandbox's Python 3.10 (unlike interrupt()-dependent
tests). These DO spawn a real subprocess each time (app/sandbox/_worker.py) —
this is deliberately not mocked, since the subprocess boundary and resource
limits ARE the thing being tested (SC-005). See
tests/integration/test_code_sandbox.py for the full end-to-end graph proof."""

from __future__ import annotations

import os

os.environ.setdefault("NEXTGEN_APP_PASSWORD", "test-password")
os.environ.setdefault("NEXTGEN_CREDENTIAL_KEY", "kQq4v2v7v3o5b1yqjq7c9m3n8p0r2s4t6u8w0x2y4z6=")

import pytest

from app.graph.nodes import code_node

BASE_STATE = {"variables": {}, "node_outputs": {}, "retry_counts": {}, "last_output_port": {}}


def _state(**overrides):
    state = {k: dict(v) if isinstance(v, dict) else v for k, v in BASE_STATE.items()}
    state.update(overrides)
    return state


@pytest.mark.asyncio
async def test_valid_transform_routes_to_success():
    state = _state(node_outputs={"__latest__": "ada"})
    result = await code_node.execute("code1", {"snippet": "result = previous.upper()"}, state)
    assert result["last_output_port"]["code1"] == "success"
    assert result["node_outputs"]["code1"] == "ADA"


@pytest.mark.asyncio
async def test_can_read_variables_and_use_allowed_stdlib():
    state = _state(variables={"count": 3})
    result = await code_node.execute(
        "code1",
        {"snippet": "import math\nresult = math.factorial(variables['count'])"},
        state,
    )
    assert result["last_output_port"]["code1"] == "success"
    assert result["node_outputs"]["code1"] == 6


@pytest.mark.asyncio
async def test_socket_import_routes_to_failure_not_crash():
    state = _state()
    result = await code_node.execute(
        "code1", {"snippet": "import socket\nresult = socket.socket()"}, state
    )
    assert result["last_output_port"]["code1"] == "failure"
    assert "socket" in result["node_outputs"]["code1"]["error"].lower()


@pytest.mark.asyncio
async def test_filesystem_import_routes_to_failure():
    state = _state()
    result = await code_node.execute(
        "code1", {"snippet": "import os\nresult = os.listdir('/')"}, state
    )
    assert result["last_output_port"]["code1"] == "failure"


@pytest.mark.asyncio
async def test_dunder_traversal_escape_attempt_routes_to_failure():
    state = _state()
    result = await code_node.execute(
        "code1",
        {"snippet": "result = ().__class__.__bases__[0].__subclasses__()"},
        state,
    )
    assert result["last_output_port"]["code1"] == "failure"


@pytest.mark.asyncio
async def test_timeout_routes_to_failure_not_hang():
    state = _state()
    result = await code_node.execute(
        "code1",
        {"snippet": "while True:\n    pass", "timeout_seconds": 2},
        state,
    )
    assert result["last_output_port"]["code1"] == "failure"
    assert "timeout" in result["node_outputs"]["code1"]["error"].lower()


@pytest.mark.asyncio
async def test_memory_limit_routes_to_failure():
    state = _state()
    result = await code_node.execute(
        "code1", {"snippet": "result = 'x' * (500 * 1024 * 1024)"}, state
    )
    assert result["last_output_port"]["code1"] == "failure"


@pytest.mark.asyncio
async def test_unresolved_previous_reference_when_missing_is_none_not_crash():
    # No prior node ran — previous is None rather than a KeyError, since
    # node_outputs["__latest__"] is absent from the state entirely.
    state = _state()
    result = await code_node.execute("code1", {"snippet": "result = previous"}, state)
    assert result["last_output_port"]["code1"] == "success"
    assert result["node_outputs"]["code1"] is None
