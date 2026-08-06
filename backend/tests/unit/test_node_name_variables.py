"""Unit tests for Named Node Variable Resolution (e.g. {{User Question}}, {{Interview Vault Memory RAG}})."""

import pytest

from app.graph.templating import render_template


def test_node_name_variable_resolution():
    state = {
        "node_outputs": {
            "input-1": "give jd of capitalone",
            "User Question": "give jd of capitalone",
            "memory-1": "Capital One Distinguished Engineer role details",
            "Interview Vault Memory RAG": "Capital One Distinguished Engineer role details",
        }
    }

    template = (
        "User Question: {{User Question}}\n"
        "Retrieved Notes: {{Interview Vault Memory RAG}}"
    )

    rendered = render_template(template, state)

    assert "User Question: give jd of capitalone" in rendered
    assert "Retrieved Notes: Capital One Distinguished Engineer role details" in rendered
