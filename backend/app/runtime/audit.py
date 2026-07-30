"""Writes NodeExecution audit rows as the graph executes. Satisfies FR-029, SC-007,
Constitution VII ("Every Run Is Audited") — a row is written immediately after each
node's output is known, not batched at the end of the run."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlmodel import Session

from app.models.run import NodeExecution


def record_node_execution(
    session: Session,
    *,
    run_id: str,
    node_id: str,
    node_type: str,
    output_port: str,
    input_data,
    output_data,
    started_at: datetime,
    attempt_count: int | None = None,
) -> NodeExecution:
    execution = NodeExecution(
        run_id=run_id,
        node_id=node_id,
        node_type=node_type,
        output_port=output_port,
        input_json=json.dumps(input_data, default=str),
        output_json=json.dumps(output_data, default=str),
        attempt_count=attempt_count,
        started_at=started_at,
        ended_at=datetime.now(timezone.utc),
    )
    session.add(execution)
    session.commit()
    return execution
