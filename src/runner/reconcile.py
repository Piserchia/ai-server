"""
Startup reconciliation of orphaned jobs.

The per-job timeout in ``_process_job`` (``session_timeout_seconds``) only fires
for jobs the *current* process is running. If the runner is killed mid-job
(crash, SIGKILL, power loss, ``launchctl stop``), the job's DB row stays
``status='running'`` forever — nothing ever writes its terminal event, and
``self-diagnose``/upkeep see a job that looks perpetually in-flight.

At runner startup nothing is executing yet, so any row still in ``running`` is a
leftover from a previous process that died mid-job. ``reconcile_orphaned_jobs``
marks each such row ``failed``, writes a terminal audit event (preserving INV-2:
exactly one terminal event per job), and returns the count. Fail-only for now —
no auto-requeue — to keep restart behaviour predictable and avoid re-running a
job that may have already had side effects before the crash.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

import structlog
from sqlalchemy import select, update

from src import audit_log
from src.db import session_scope
from src.models import Job, JobStatus

logger = structlog.get_logger()

ORPHAN_CATEGORY = "orphaned"
ORPHAN_ERROR = (
    "Runner restarted while this job was still 'running'; marked failed by "
    "startup reconciliation (the process that owned it is gone)."
)


def orphaned_job_ids(rows: Iterable[tuple]) -> list:
    """Pure. Given ``(job_id, status)`` pairs, return the job_ids stranded in
    ``running``.

    At runner startup nothing is executing yet, so every ``running`` row is a
    leftover from a previous process that died mid-job.
    """
    return [jid for jid, status in rows if status == JobStatus.running.value]


async def reconcile_orphaned_jobs() -> int:
    """Fail every job left in ``running`` from a previous process. Returns count.

    Call once at startup, before the job loop begins consuming the queue.
    """
    async with session_scope() as s:
        result = await s.execute(
            select(Job.id, Job.status).where(Job.status == JobStatus.running.value)
        )
        rows = [(row[0], row[1]) for row in result.all()]

    ids = orphaned_job_ids(rows)
    if not ids:
        return 0

    # Terminal audit event per job first, so INV-2 holds even if the DB update
    # below fails partway (the event is the durable record of the transition).
    for job_id in ids:
        audit_log.append(
            str(job_id), "job_failed", error=ORPHAN_ERROR, error_category=ORPHAN_CATEGORY
        )

    async with session_scope() as s:
        await s.execute(
            update(Job)
            .where(Job.id.in_(ids))
            .values(
                status=JobStatus.failed.value,
                error_message=ORPHAN_ERROR,
                completed_at=datetime.now(timezone.utc),
            )
        )

    logger.warning(
        "reconciled orphaned jobs", count=len(ids), job_ids=[str(j) for j in ids]
    )
    return len(ids)
