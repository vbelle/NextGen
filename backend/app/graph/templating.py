"""{{variable}} (Handlebars-style) template resolution. See research.md §4, FR-023, FR-025."""

from __future__ import annotations

import json
import re

from app.graph.state import GraphState

_VAR_PATTERN = re.compile(r"\{\{\s*([A-Za-z0-9_\-\s]+?)\s*\}\}")
_WHOLE_REF_PATTERN = re.compile(r"^\{\{\s*([A-Za-z0-9_\-\s]+?)\s*\}\}$")

RESERVED_PREVIOUS = "previous"


class VariableNotSetError(Exception):
    """Raised when {{name}} references a Variable/Node that never executed in this run."""

    def __init__(self, name: str):
        self.name = name
        super().__init__(f"Variable '{{{{{name}}}}}' was referenced but never set in this run")


def _stringify(value) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value)


def _get_val(name: str, state: GraphState):
    node_outputs = state.get("node_outputs", {})
    variables = state.get("variables", {})

    if name == RESERVED_PREVIOUS:
        return node_outputs.get("__latest__")
    if name in variables:
        return variables[name]
    if name in node_outputs:
        return node_outputs[name]
    if name.lower() in node_outputs:
        return node_outputs[name.lower()]

    raise VariableNotSetError(name)


def render_template(text: str, state: GraphState) -> str:
    def _replace(match: re.Match) -> str:
        name = match.group(1).strip()
        val = _get_val(name, state)
        return _stringify(val)

    return _VAR_PATTERN.sub(_replace, text)


def has_variable_refs(text: str) -> bool:
    return bool(_VAR_PATTERN.search(text))


def resolve_value_reference(ref: str, state: GraphState):
    match = _WHOLE_REF_PATTERN.match(ref.strip())
    if not match:
        raise ValueError(
            f"'{ref}' must be exactly {{{{previous}}}} or {{{{variable_name}}}} to "
            "resolve to a value — not embedded in surrounding text"
        )
    name = match.group(1).strip()
    return _get_val(name, state)
