"""Unit tests for the built-in tool implementation registry (User Story 11).
See app/graph/tool_registry.py's module docstring for the design rationale
(a small fixed registry rather than user-authored code or an HTTP call)."""

from __future__ import annotations

import os

os.environ.setdefault("NEXTGEN_APP_PASSWORD", "test-password")
os.environ.setdefault("NEXTGEN_CREDENTIAL_KEY", "kQq4v2v7v3o5b1yqjq7c9m3n8p0r2s4t6u8w0x2y4z6=")

import pytest

from app.graph import tool_registry


def test_calculator_evaluates_arithmetic():
    assert tool_registry.calculator("2 + 3 * 4") == "14"
    assert tool_registry.calculator("(2 + 3) * 4") == "20"
    assert tool_registry.calculator("10 / 4") == "2.5"


def test_calculator_rejects_unsafe_expression():
    with pytest.raises(ValueError):
        tool_registry.calculator("__import__('os').system('echo pwned')")


def test_current_datetime_returns_iso_string():
    result = tool_registry.current_datetime()
    assert "T" in result  # ISO 8601 date/time separator


def test_word_count_counts_words():
    assert tool_registry.word_count("the quick brown fox") == "4"
    assert tool_registry.word_count("") == "0"


def test_list_tool_implementations_includes_builtins():
    refs = tool_registry.list_tool_implementations()
    assert {"calculator", "current_datetime", "word_count"} <= set(refs)


def test_get_tool_implementation_unknown_ref_raises():
    with pytest.raises(tool_registry.UnknownToolImplementationError):
        tool_registry.get_tool_implementation("does-not-exist")


def test_get_tool_implementation_returns_args_schema_and_func():
    impl = tool_registry.get_tool_implementation("calculator")
    assert impl.func("1 + 1") == "2"
    fields = impl.args_schema.model_fields
    assert "expression" in fields
