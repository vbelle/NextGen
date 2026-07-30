"""Parent-side sandbox runner (research.md §5). Spawns app.sandbox._worker as a
subprocess with a minimal, secret-free environment and enforces the wall-clock
timeout — RLIMIT_CPU inside the worker is a backstop for CPU-bound loops, not
the primary mechanism, since a snippet blocked on something else wouldn't
accumulate CPU time and would otherwise hang forever."""

from __future__ import annotations

import asyncio
import json
import os
import sys


class SnippetTimeoutError(Exception):
    pass


async def run_snippet(*, snippet: str, previous, variables: dict, timeout_seconds: int) -> dict:
    """Returns {"ok": True, "result": ...} or {"ok": False, "error": "..."} for an
    ordinary snippet failure (bad code, blocked import, raised exception) — never
    raises for those. Raises SnippetTimeoutError if the subprocess doesn't finish
    within timeout_seconds, and RuntimeError if the worker process itself crashes
    (as opposed to the snippet inside it failing cleanly)."""
    cpu_seconds = max(1, min(int(timeout_seconds), 120))
    payload = json.dumps(
        {
            "snippet": snippet,
            "previous": previous,
            "variables": variables,
            "cpu_seconds": cpu_seconds,
        }
    )

    # Deliberately minimal env: a Code node snippet must never be able to read
    # NEXTGEN_CREDENTIAL_KEY, NEXTGEN_APP_PASSWORD, or the sandbox host's proxy
    # variables just because the parent process happens to have them.
    env = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": os.environ.get("PYTHONPATH", ""),
        "LANG": "C.UTF-8",
    }

    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "app.sandbox._worker",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(payload.encode()), timeout=timeout_seconds
        )
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise SnippetTimeoutError(f"Code node exceeded its {timeout_seconds}s timeout")

    if proc.returncode != 0:
        raise RuntimeError(
            "Sandbox worker process crashed "
            f"(exit {proc.returncode}): {stderr.decode(errors='replace')[-500:]}"
        )

    return json.loads(stdout.decode())
