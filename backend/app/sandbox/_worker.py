"""Subprocess entry point for running one Code node snippet. Invoked as
`python -m app.sandbox._worker` by run_snippet.py — never imported directly by
anything running in the main app process. Resource limits are set as the very
first statements, before anything else in this process does real work, per
research.md §5's layered-defense design.

Protocol: reads one JSON object from stdin — {"snippet", "previous", "variables",
"cpu_seconds"} — and writes exactly one JSON object to stdout — either
{"ok": true, "result": <json-serializable>} or {"ok": false, "error": "<message>"}.
The parent (run_snippet.py) separately enforces a wall-clock timeout by killing
this process if it doesn't respond in time; RLIMIT_CPU here is a backstop, not
the primary timeout mechanism (a snippet blocked on I/O wouldn't accumulate CPU
time, so wall-clock is what actually catches that case)."""

from __future__ import annotations

import json
import resource
import sys

_MEMORY_BYTES = 256 * 1024 * 1024  # 256MB address-space cap
_NOFILE = 16  # small — enough for stdio, not enough to be useful for abuse


def _apply_resource_limits(cpu_seconds: int) -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
    resource.setrlimit(resource.RLIMIT_AS, (_MEMORY_BYTES, _MEMORY_BYTES))
    resource.setrlimit(resource.RLIMIT_NOFILE, (_NOFILE, _NOFILE))


_ALLOWED_IMPORTS = {
    "json",
    "math",
    "re",
    "string",
    "datetime",
    "statistics",
    "itertools",
    "collections",
    "decimal",
}


def _guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
    top_level = name.split(".")[0]
    if top_level not in _ALLOWED_IMPORTS:
        raise ImportError(f"Import of '{name}' is not allowed in a Code node snippet")
    return __import__(name, globals, locals, fromlist, level)


def _run(snippet: str, previous, variables: dict) -> dict:
    # Imported here (not at module top) so a snippet that somehow crashes the
    # interpreter before this point still can't have prevented the resource
    # limits above from taking effect.
    from RestrictedPython import compile_restricted, safe_builtins, safe_globals
    from RestrictedPython.Eval import default_guarded_getitem, default_guarded_getiter
    from RestrictedPython.Guards import (
        full_write_guard,
        guarded_iter_unpack_sequence,
        safer_getattr,
    )

    code = compile_restricted(snippet, "<code-node-snippet>", "exec")

    restricted_builtins = dict(safe_builtins)
    restricted_builtins["__import__"] = _guarded_import

    restricted_globals = dict(safe_globals)
    restricted_globals["__builtins__"] = restricted_builtins
    restricted_globals["_getattr_"] = safer_getattr
    restricted_globals["_getitem_"] = default_guarded_getitem
    restricted_globals["_getiter_"] = default_guarded_getiter
    restricted_globals["_iter_unpack_sequence_"] = guarded_iter_unpack_sequence
    restricted_globals["_write_"] = full_write_guard
    restricted_globals["previous"] = previous
    restricted_globals["variables"] = dict(variables)

    exec(code, restricted_globals)  # noqa: S102 — this IS the sandbox boundary
    return restricted_globals.get("result")


def main() -> None:
    payload = json.loads(sys.stdin.read())
    _apply_resource_limits(int(payload.get("cpu_seconds", 10)))
    try:
        result = _run(payload["snippet"], payload.get("previous"), payload.get("variables") or {})
        json.dumps(result)  # fail fast here with a clear error if not serializable
        sys.stdout.write(json.dumps({"ok": True, "result": result}))
    except Exception as exc:  # noqa: BLE001 — any snippet error becomes a clean failure message
        sys.stdout.write(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"}))


if __name__ == "__main__":
    main()
