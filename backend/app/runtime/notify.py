"""Minimal in-process pub/sub bridging the background run executor to whichever
WebSocket connection is waiting on that run. Single-process design (research.md
§7) — no Redis/pubsub needed at this scale."""

from __future__ import annotations

import asyncio

_QUEUES: dict[str, asyncio.Queue] = {}


def register(run_id: str) -> asyncio.Queue:
    queue: asyncio.Queue = asyncio.Queue()
    _QUEUES[run_id] = queue
    return queue


def unregister(run_id: str) -> None:
    _QUEUES.pop(run_id, None)


async def _put(run_id: str, message: dict) -> None:
    queue = _QUEUES.get(run_id)
    if queue is not None:
        await queue.put(message)


async def input_requested(run_id: str, prompt: dict) -> None:
    await _put(run_id, {"type": "input_request", "payload": {"run_id": run_id, **prompt}})


async def run_completed(run_id: str, content) -> None:
    await _put(run_id, {"type": "response", "payload": {"run_id": run_id, "content": content}})


async def run_failed(run_id: str, message: str) -> None:
    await _put(run_id, {"type": "run_failed", "payload": {"run_id": run_id, "message": message}})
