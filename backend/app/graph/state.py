"""Shared LangGraph state. Every node function receives and returns a partial
GraphState; LangGraph merges updates in per the reducers below. See research.md §4."""

from __future__ import annotations

from typing import Annotated, Any, TypedDict


def _merge_dicts(left: dict, right: dict) -> dict:
    merged = dict(left)
    merged.update(right)
    return merged


class GraphState(TypedDict, total=False):
    run_id: str
    workflow_id: str
    workflow_version: int

    # Explicit named values set by Variable nodes (FR-022/FR-023). Keyed by
    # builder-chosen unique name.
    variables: Annotated[dict[str, Any], _merge_dicts]

    # Implicit "what did node X output last" — used for direct upstream
    # references that don't go through a Variable node.
    node_outputs: Annotated[dict[str, Any], _merge_dicts]

    # Retry node attempt counters, keyed by the Retry node's own id.
    retry_counts: Annotated[dict[str, int], _merge_dicts]

    # Loop node bookkeeping, keyed by the Loop node's own id: {"items": [...],
    # "index": int, "results": [...]}. Lives in GraphState (not local Python
    # state) so a pause/resume mid-loop-body checkpoints correctly, same
    # reasoning as retry_counts.
    loop_state: Annotated[dict[str, dict], _merge_dicts]

    # Which output port each node fired last (success/failure/true/false/...),
    # used by the compiler's routing functions to pick the next edge.
    last_output_port: Annotated[dict[str, str], _merge_dicts]

    # Set by an Input node when it interrupts; cleared on resume.
    pending_input_node_id: str | None

    # How many Sub-workflow nodes deep the current node is nested (User Story
    # 12). Not reducer-merged — each nested invocation's own initial_state
    # sets it explicitly to depth + 1 before compiling/invoking the child
    # graph, guarding against a runaway self-referential/circular embed the
    # same way retry_counts/MAX_TOOL_ROUNDS bound their own loops.
    subworkflow_depth: int
