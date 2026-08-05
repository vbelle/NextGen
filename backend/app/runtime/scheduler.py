"""Background Cron Scheduler engine for automated workflow execution.

Uses APScheduler's AsyncIOScheduler to run recurring cron-triggered workflows.
"""

from __future__ import annotations

import json

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlmodel import Session, select

from app.db import get_engine
from app.logging import get_logger
from app.models.run import Run, RunStatus
from app.models.trigger import WorkflowTrigger
from app.models.workflow import Workflow, WorkflowVersion
from app.runtime import executor

logger = get_logger(__name__)

_SCHEDULER: AsyncIOScheduler | None = None


def _get_scheduler() -> AsyncIOScheduler:
    global _SCHEDULER
    if _SCHEDULER is None:
        _SCHEDULER = AsyncIOScheduler()
    return _SCHEDULER


async def _run_cron_job(workflow_id: str, trigger_id: str) -> None:
    logger.info("Executing scheduled cron trigger '%s' for workflow '%s'", trigger_id, workflow_id)
    engine = get_engine()
    with Session(engine) as session:
        workflow = session.get(Workflow, workflow_id)
        if not workflow or not workflow.active_version_id:
            logger.warning(
                "Cron trigger '%s' skipped: workflow '%s' has no active version",
                trigger_id,
                workflow_id,
            )
            return

        version = session.get(WorkflowVersion, workflow.active_version_id)
        if not version:
            return

        graph_json = json.loads(version.graph_json)

        # Create Run
        run = Run(
            workflow_version_id=version.id,
            status=RunStatus.running,
        )
        session.add(run)
        session.commit()
        session.refresh(run)

        run_id = run.id

    initial_input = {"question": "Scheduled automated execution"}

    def _session_factory():
        return Session(get_engine())

    await executor.start_run(
        session_factory=_session_factory,
        run_id=run_id,
        graph_json=graph_json,
        initial_state=initial_input,
    )


def reload_cron_triggers() -> None:
    """Reloads all active cron triggers from DB into APScheduler."""
    scheduler = _get_scheduler()
    scheduler.remove_all_jobs()

    engine = get_engine()
    with Session(engine) as session:
        triggers = session.exec(
            select(WorkflowTrigger).where(
                WorkflowTrigger.trigger_type == "cron",
                WorkflowTrigger.enabled == True,  # noqa: E712
            )
        ).all()

        for t in triggers:
            if not t.cron_expression:
                continue
            try:
                trigger = CronTrigger.from_crontab(t.cron_expression.strip())
                job_id = f"cron_{t.id}"
                scheduler.add_job(
                    _run_cron_job,
                    trigger=trigger,
                    id=job_id,
                    args=[t.workflow_id, t.id],
                    replace_existing=True,
                )
                logger.info(
                    "Scheduled cron job '%s' for workflow '%s' with expr '%s'",
                    job_id,
                    t.workflow_id,
                    t.cron_expression,
                )
            except Exception as exc:
                logger.error(
                    "Failed to parse cron expr '%s' for trigger '%s': %s",
                    t.cron_expression,
                    t.id,
                    exc,
                )


def start_scheduler() -> None:
    """Starts the background cron scheduler if not already running."""
    scheduler = _get_scheduler()
    if not scheduler.running:
        scheduler.start()
        logger.info("Background Cron Scheduler started")
    reload_cron_triggers()
