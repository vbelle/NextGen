"""Sub-workflow node: runs a version-pinned saved workflow as a single node
inside another workflow (FR per User Story 12), with its own success/failure
outputs (DUAL_OUTPUT_TYPES — see schema.py).

2026-07-30 design decisions (asked, not guessed — spec.md's acceptance
scenarios describe the desired outcome but not the mechanics, and every
saved workflow is required to have an entry Input node, which
unconditionally pauses via interrupt() on its first pass with no live chat
user attached to answer it inside a nested run):

1. The embedded workflow's entry Input node is auto-resumed with whatever
   flows into this Sub-workflow node itself (the same {{previous}} value
   every other node type consumes) — the entry Input node doubles as the
   sub-workflow's "parameter," matching input_node.py's own documented dual
   purpose (starting parameter vs. mid-flow pause).
2. If the embedded workflow tries to pause a second time (a genuine
   mid-flow human-in-the-loop Input node), that's treated as this node's
   failure output firing — there's no live chat user attached to a nested
   run to answer it, and propagating the pause up to the parent's chat
   conversation would need substantial new plumbing across GraphState, the
   executor, and checkpointing (a much bigger feature than one node type).
3. The embedded invocation gets its OWN Run row (own run_id/checkpointer
   thread, same chat_session_id as the parent) rather than reusing the
   parent's run_id — node IDs are only unique within a single graph, not
   globally, so two different saved workflows could collide if their
   executions were flattened into one audit trail.

MAX_SUBWORKFLOW_DEPTH bounds a self-referential/circular embed the same way
Retry's max_attempts and the LLM node's MAX_TOOL_ROUNDS bound their own
loops — not explicitly spec'd, but the same class of runaway-recursion
hazard."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from pydantic import BaseModel
from sqlmodel import Session

from app.db import get_engine
from app.graph.schema import register_node_type
from app.graph.state import GraphState
from app.models.run import Run, RunStatus
from app.models.workflow import WorkflowVersion

MAX_SUBWORKFLOW_DEPTH = 10


class SubworkflowConfig(BaseModel):
    workflow_id: str
    pinned_version_id: str


def _paused(result: dict) -> bool:
    return bool(result.get("__interrupt__"))


def _mark_run(run_id: str, status: RunStatus) -> None:
    with Session(get_engine()) as session:
        run = session.get(Run, run_id)
        if run:
            run.status = status
            # timezone.utc, not the datetime.UTC alias, to match every other
            # started_at/ended_at timestamp in this codebase (e.g. app/runtime/audit.py).
            run.ended_at = datetime.now(timezone.utc)  # noqa: UP017
            session.add(run)
            session.commit()


async def execute(node_id: str, config: dict, state: GraphState) -> dict:
    # Imported lazily: app.graph.compiler imports app.graph.nodes (this
    # package) at module load time to register every node type, so importing
    # it back at this module's top level would be circular. Same reasoning
    # for app.runtime.executor (imports app.graph.compiler) and
    # langgraph.types.Command.
    from langgraph.types import Command

    from app.graph.compiler import compile_graph
    from app.runtime.executor import get_checkpointer

    cfg = SubworkflowConfig(**config)
    child_run_id: str | None = None
    try:
        depth = state.get("subworkflow_depth", 0)
        if depth >= MAX_SUBWORKFLOW_DEPTH:
            raise RuntimeError(
                f"Sub-workflow nesting exceeded {MAX_SUBWORKFLOW_DEPTH} levels — "
                "aborting to avoid a runaway self-referential/circular embed"
            )

        upstream_value = state.get("node_outputs", {}).get("__latest__")
        parent_run_id = state.get("run_id")
        if not parent_run_id:
            raise ValueError("Sub-workflow node has no parent run context to attach to")

        with Session(get_engine()) as session:
            parent_run = session.get(Run, parent_run_id)
            if parent_run is None:
                raise ValueError("Sub-workflow node has no parent run context to attach to")

            version = session.get(WorkflowVersion, cfg.pinned_version_id)
            if version is None:
                raise ValueError(
                    f"Pinned workflow version '{cfg.pinned_version_id}' no longer exists"
                )
            if version.workflow_id != cfg.workflow_id:
                raise ValueError(
                    f"Pinned version '{cfg.pinned_version_id}' does not belong to "
                    f"workflow '{cfg.workflow_id}' — the node's config is inconsistent"
                )

            child_run = Run(
                workflow_version_id=version.id, chat_session_id=parent_run.chat_session_id
            )
            session.add(child_run)
            session.commit()
            child_run_id = child_run.id
            graph_json = json.loads(version.graph_json)
            workflow_id = version.workflow_id

        checkpointer = await get_checkpointer()
        builder = compile_graph(graph_json)
        compiled = builder.compile(checkpointer=checkpointer)
        child_config = {"configurable": {"thread_id": child_run_id}}

        initial_state = {
            "run_id": child_run_id,
            "workflow_id": workflow_id,
            "subworkflow_depth": depth + 1,
        }
        result = await compiled.ainvoke(initial_state, config=child_config)

        if _paused(result):
            result = await compiled.ainvoke(Command(resume=upstream_value), config=child_config)

        if _paused(result):
            raise RuntimeError(
                "Embedded workflow tried to pause on a mid-flow Input node — nested "
                "sub-workflows can only auto-answer their entry Input node, not "
                "further human-in-the-loop pauses"
            )

        response = result.get("node_outputs", {}).get("__response__")
        _mark_run(child_run_id, RunStatus.completed)
        return {
            "node_outputs": {node_id: response, "__latest__": response},
            "last_output_port": {node_id: "success"},
        }
    except Exception as exc:  # noqa: BLE001 — any failure routes to failure output
        if child_run_id:
            _mark_run(child_run_id, RunStatus.failed)
        error = {"error": str(exc)}
        return {
            "node_outputs": {node_id: error, "__latest__": error},
            "last_output_port": {node_id: "failure"},
        }


register_node_type("subworkflow", SubworkflowConfig, execute)
