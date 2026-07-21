"""Decision node: evaluates a condition against an upstream field/`{{previous}}`
or a `{{variable}}` and routes true/false — binary only, per contracts/graph-schema.md
and the clarification that Decision nodes are strictly true/false (no third branch).

Unlike LLM/API/Code/Subworkflow (DUAL_OUTPUT_TYPES), Decision has no `failure` output
port (see app.graph.schema.ALLOWED_SOURCE_PORTS) — an evaluation error here (e.g. an
unset {{variable}}, or gt/lt against a non-numeric value) is a genuine run failure,
not something this node type is designed to route around."""

from __future__ import annotations

from pydantic import BaseModel

from app.graph.schema import register_node_type
from app.graph.state import GraphState
from app.graph.templating import render_template

_VALID_OPERATORS = {"equals", "contains", "gt", "lt", "truthy"}


class DecisionConfig(BaseModel):
    left: str
    operator: str
    right: str | None = None  # omitted for "truthy"


def _is_truthy(value: str) -> bool:
    return value.strip().lower() not in ("", "false", "0", "none", "null")


def _evaluate(operator: str, left: str, right: str | None) -> bool:
    if operator not in _VALID_OPERATORS:
        raise ValueError(
            f"Unknown Decision operator '{operator}' (expected one of {sorted(_VALID_OPERATORS)})"
        )
    if operator == "truthy":
        return _is_truthy(left)
    if operator == "equals":
        return left == (right or "")
    if operator == "contains":
        return (right or "") in left
    # gt / lt
    try:
        left_num = float(left)
        right_num = float(right)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Decision operator '{operator}' requires numeric values, "
            f"got left={left!r} right={right!r}"
        ) from exc
    return left_num > right_num if operator == "gt" else left_num < right_num


async def execute(node_id: str, config: dict, state: GraphState) -> dict:
    cfg = DecisionConfig(**config)
    left = render_template(cfg.left, state)
    right = render_template(cfg.right, state) if cfg.right is not None else None
    result = _evaluate(cfg.operator, left, right)
    return {"last_output_port": {node_id: "true" if result else "false"}}


register_node_type("decision", DecisionConfig, execute)
