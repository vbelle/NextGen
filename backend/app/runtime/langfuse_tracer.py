"""Langfuse observability and tracing integration for NextGen runs.

Provides a CallbackHandler for LangGraph / LangChain execution when
LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY are configured in the environment.
If keys are missing, gracefully returns None with zero side effects.
"""

from __future__ import annotations

import os
from typing import Any

from app.logging import get_logger

logger = get_logger(__name__)


def get_langfuse_callback_handler(run_id: str, workflow_name: str | None = None) -> Any | None:
    """Instantiates a Langfuse CallbackHandler for the given run_id.

    Returns None if Langfuse API keys are not configured.
    """
    public_key = os.environ.get("LANGFUSE_PUBLIC_KEY", "").strip()
    secret_key = os.environ.get("LANGFUSE_SECRET_KEY", "").strip()

    if not public_key or not secret_key:
        logger.debug("Langfuse keys not configured; tracing skipped for run '%s'", run_id)
        return None

    try:
        from langfuse.langchain import CallbackHandler

        handler = CallbackHandler()
        logger.info("Initialized Langfuse trace handler for run '%s'", run_id)
        return handler
    except Exception as exc:
        logger.warning("Failed to init Langfuse CallbackHandler for run '%s': %s", run_id, exc)
        return None
