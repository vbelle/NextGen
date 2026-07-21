"""{{variable}} (Handlebars-style) template resolution. See research.md §4, FR-023, FR-025."""

from __future__ import annotations

import json
import re

from app.graph.state import GraphState

_VAR_PATTERN = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")


class VariableNotSetError(Exception):
    """Raised when {{name}} references a Variable that never executed in this run.
    FR-025: this MUST be treated as a failure of the *referencing* node, not a
    silent empty-string substitution."""

    def __init__(self, name: str):
        self.name = name
        super().__init__(f"Variable '{{{{{name}}}}}' was referenced but never set in this run")


def _stringify(value) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value)


RESERVED_PREVIOUS = "previous"


def render_template(text: str, state: GraphState) -> str:
    """Resolve every {{name}} in `text`. `{{previous}}` is a reserved name that
    always resolves to the most recently completed node's output (direct upstream
    reference, no Variable node required — this is what a minimal Input -> LLM ->
    Response chain uses). Any other {{name}} resolves against state['variables']
    (explicit Variable-node writes, FR-023) and raises VariableNotSetError if unset
    (FR-025) — never a silent empty string."""
    variables = state.get("variables", {})
    node_outputs = state.get("node_outputs", {})

    def _replace(match: re.Match) -> str:
        name = match.group(1)
        if name == RESERVED_PREVIOUS:
            return _stringify(node_outputs.get("__latest__", ""))
        if name not in variables:
            raise VariableNotSetError(name)
        return _stringify(variables[name])

    return _VAR_PATTERN.sub(_replace, text)


def has_variable_refs(text: str) -> bool:
    return bool(_VAR_PATTERN.search(text))
