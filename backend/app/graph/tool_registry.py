"""Backend registry of built-in tools a Tool node's `implementation_ref` can
resolve to.

2026-07-30 design decision (asked, not guessed — contracts/graph-schema.md's
`implementation_ref: "string, maps to a registered backend tool"` doesn't say
what a "registered backend tool" actually is): a small, fixed registry of
pre-written Python functions shipped with the app, rather than user-authored
code (that's the Code node's job — a Tool node config has no snippet field)
or an HTTP call (that's the API node's job — this would just duplicate it).

Each entry pairs a Pydantic args schema — needed because the Tool node's own
config carries no parameter schema, only a name/description/ref — with a
plain, synchronous, side-effect-free Python callable. LangChain's tool
wrapper (built in app/graph/nodes/llm_node.py, since that's where a run_id
is available for audit logging) runs sync callables like these in a thread
automatically when awaited, so there's no need for these to be async."""

from __future__ import annotations

import ast
import operator
from collections.abc import Callable
from datetime import datetime, timezone

from pydantic import BaseModel, Field


class CalculatorArgs(BaseModel):
    expression: str = Field(description="An arithmetic expression, e.g. '2 * (3 + 4)'")


class DatetimeArgs(BaseModel):
    pass


class WordCountArgs(BaseModel):
    text: str = Field(description="The text to count words in")


_ALLOWED_BIN_OPS: dict[type, Callable] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv,
}
_ALLOWED_UNARY_OPS: dict[type, Callable] = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def _safe_eval(node: ast.AST) -> float:
    # Whitelist-based arithmetic evaluator (no eval()/exec()) — same spirit as
    # the Code node's RestrictedPython sandboxing, scoped down to arithmetic
    # since that's all a calculator tool needs.
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_BIN_OPS:
        return _ALLOWED_BIN_OPS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_UNARY_OPS:
        return _ALLOWED_UNARY_OPS[type(node.op)](_safe_eval(node.operand))
    raise ValueError(f"Unsupported expression element: {ast.dump(node)}")


def calculator(expression: str) -> str:
    try:
        tree = ast.parse(expression, mode="eval")
        return str(_safe_eval(tree.body))
    except Exception as exc:
        raise ValueError(f"Could not evaluate '{expression}': {exc}") from exc


def current_datetime() -> str:
    # timezone.utc, not the datetime.UTC alias, to match every other
    # started_at/ended_at timestamp in this codebase (e.g. app/runtime/audit.py).
    return datetime.now(timezone.utc).isoformat()  # noqa: UP017


def word_count(text: str) -> str:
    return str(len(text.split()))


class ToolImplementation:
    def __init__(self, args_schema: type[BaseModel], func: Callable[..., str]):
        self.args_schema = args_schema
        self.func = func


_REGISTRY: dict[str, ToolImplementation] = {
    "calculator": ToolImplementation(CalculatorArgs, calculator),
    "current_datetime": ToolImplementation(DatetimeArgs, current_datetime),
    "word_count": ToolImplementation(WordCountArgs, word_count),
}


class UnknownToolImplementationError(Exception):
    def __init__(self, ref: str):
        self.ref = ref
        super().__init__(
            f"'{ref}' is not a registered tool implementation. Known: {sorted(_REGISTRY)}"
        )


def get_tool_implementation(ref: str) -> ToolImplementation:
    if ref not in _REGISTRY:
        raise UnknownToolImplementationError(ref)
    return _REGISTRY[ref]


def list_tool_implementations() -> list[str]:
    return sorted(_REGISTRY)
