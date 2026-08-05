"""Unit tests for Langfuse tracing initialization."""

from app.runtime.langfuse_tracer import get_langfuse_callback_handler


def test_get_langfuse_callback_handler_missing_keys(monkeypatch):
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)

    handler = get_langfuse_callback_handler(run_id="run-123")
    assert handler is None


def test_get_langfuse_callback_handler_with_keys(monkeypatch):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-test-123")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-test-456")
    monkeypatch.setenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

    handler = get_langfuse_callback_handler(run_id="run-123", workflow_name="test_flow")
    assert handler is not None
