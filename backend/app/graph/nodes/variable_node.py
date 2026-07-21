"""Variable node: saves whatever flowed into it (the direct-upstream/'previous'
output) under a builder-chosen unique name, readable later in the same run via
`{{name}}` from ANY node — not just direct neighbors (FR-022/FR-023, SC-009). See
contracts/graph-schema.md: the node's only config is `name`; it doesn't need its
own value expression because it captures state["node_outputs"]["__latest__"],
matching how the user originally framed it: "save either successful output or
failures or anything related to previous node and use it later."

Also writes a RunVariable row per set (app/models/variable.py) as a durable,
queryable audit trail of what a run remembered and when — separate from
`variables` in GraphState, which is what render_template() actually reads."""

from __future__ import annotations

import json

from pydantic import BaseModel
from sqlmodel import Session

from app.db import get_engine
from app.graph.schema import register_node_type
from app.graph.state import GraphState
from app.models.variable import RunVariable


class VariableConfig(BaseModel):
    name: str


async def execute(node_id: str, config: dict, state: GraphState) -> dict:
    cfg = VariableConfig(**config)
    value = state.get("node_outputs", {}).get("__latest__")

    run_id = state.get("run_id")
    if run_id:
        with Session(get_engine()) as session:
            session.add(
                RunVariable(
                    run_id=run_id,
                    name=cfg.name,
                    value_json=json.dumps(value, default=str),
                )
            )
            session.commit()

    return {
        "variables": {cfg.name: value},
        "node_outputs": {node_id: value, "__latest__": value},
        "last_output_port": {node_id: "default"},
    }


register_node_type("variable", VariableConfig, execute)
