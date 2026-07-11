"""
Startup reconciliation of orphaned jobs.

The per-job timeout in ``_process_job`` (``session_timeout_seconds``) only fires
for jobs the *current* process is running. If the runner is killed mid-job
(crash, SIGKILL, power loss, ``launchctl stop``), the job's DB row stays
``status='running'`` forever — nothing ever writes its terminal event, and
``self-diagnose``/upkeep see a job that looks perpetually in-flight.

At runner startup nothing is executing yet, so any row still in ``running`` is a
leftover from a previous process that died mid-job. ``reconcile_orphaned_jobs``
brings each such row to a terminal state:

- If the job's audit log has **no** terminal event, the process died before
  finishing: synthesise a ``job_failed`` event (``error_category='orphaned'``) so
  INV-2 holds, and mark the row ``failed``. Fail-only, no auto-requeue — a job may
  have had side effects before the crash, so blindly re-running could double them.
- If a terminal event **already exists** (the rare crash *between* writing the
  event and committing the DB update), don't write a second one — reconcile the
  DB row to match the outcome the log already records. This keeps INV-2 at exactly
  one terminal event and makes reconciliation idempotent across repeated restarts.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Iterable

import structlog
from sqlalchemy import select, update

from src import audit_log
from src.config import settings
from src.db import session_scope
from src.models import Job, JobStatus
from src.runner.audit_index import append_to_index

logger = structlog.get_logger()

ORPHAN_CATEGORY = "orphaned"
ORPHAN_ERROR = (
    "Runner restarted while this job was still 'running'; marked failed by "
    "startup reconciliation (the process that owned it is gone)."
)

_TERMINAL_EVENT_STATUS = {
    "job_completed": JobStatus.completed,
    "job_failed": JobStatus.failed,
    "job_cancelled": JobStatus.cancelled,
}


STRANDED_REQUEUE_MAX_AGE_HOURS = 24


def stranded_queued_ids(rows: Iterable[tuple], redis_members: set[str]) -> list:
    """Pure. rows = (job_id, status) pairs; return ids stuck in 'queued' with
    no matching entry in the Redis queue (crash between BLPOP and
    status=running, or a Redis restart that dropped the list)."""
    return [
        jid for jid, status in rows
        if status == JobStatus.queued.value and str(jid) not in redis_members
    ]


async def reconcile_stranded_queued() -> int:
    """Re-push stranded queued rows younger than STRANDED_REQUEUE_MAX_AGE_HOURS;
    fail older ones (their moment passed — schedules re-fire on their own).
    Runs at startup after reconcile_orphaned_jobs. Returns count handled."""
    from src.db import QUEUE_JOBS, redis

    async with session_scope() as s:
        result = await s.execute(
            select(Job.id, Job.status, Job.created_at)
            .where(Job.status == JobStatus.queued.value)
        )
        rows = list(result.all())
    if not rows:
        return 0

    members = {str(m) for m in await redis.lrange(QUEUE_JOBS, 0, -1)}
    stranded = set(stranded_queued_ids([(r[0], r[1]) for r in rows], members))
    if not stranded:
        return 0

    now = datetime.now(timezone.utc)
    handled = 0
    for job_id, _, created_at in rows:
        if job_id not in stranded:
            continue
        age_h = (now - created_at).total_seconds() / 3600
        if age_h <= STRANDED_REQUEUE_MAX_AGE_HOURS:
            await redis.rpush(QUEUE_JOBS, str(job_id))
            logger.warning("re-queued stranded job", job_id=str(job_id))
        else:
            audit_log.append(str(job_id), "job_failed",
                             error="stranded: queued row with no Redis entry",
                             error_category="stranded")
            async with session_scope() as s:
                await s.execute(update(Job).where(Job.id == job_id).values(
                    status=JobStatus.failed.value,
                    error_message="stranded queued job (startup reconciliation)",
                    completed_at=now,
                ))
            append_to_index(settings.audit_log_dir, str(job_id))
        handled += 1
    return handled


def orphaned_job_ids(rows: Iterable[tuple]) -> list:
    """Pure. Given ``(job_id, status)`` pairs, return the job_ids stranded in
    ``running``.

    At runner startup nothing is executing yet, so every ``running`` row is a
    leftover from a previous process that died mid-job.
    """
    return [jid for jid, status in rows if status == JobStatus.running.value]


def _existing_terminal_status(job_id) -> JobStatus | None:
    """Return the status implied by an already-written terminal event, or None.

    None is the normal orphan case: the process died before writing any terminal
    event. A non-None result means we must reconcile the DB to that outcome rather
    than inventing a new (duplicate, possibly conflicting) one.
    """
    path = settings.audit_log_dir / f"{job_id}.jsonl"
    if not path.exists():
        return None
    result: JobStatus | None = None
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            evt = json.loads(line)
        except json.JSONDecodeError:
            continue
        st = _TERMINAL_EVENT_STATUS.get(evt.get("kind", ""))
        if st is not None:
            result = st  # last terminal event wins
    return result


async def reconcile_orphaned_jobs() -> int:
    """Bring every job left in ``running`` by a previous process to a terminal
    state. Returns the count reconciled.

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

    # Decide each job's terminal outcome. Synthesise a job_failed event only when
    # the log has none (write it before the DB update so the durable record leads);
    # otherwise adopt the existing terminal outcome without a duplicate event.
    resolutions: list[tuple] = []  # (job_id, JobStatus, error_message_or_None)
    for job_id in ids:
        existing = _existing_terminal_status(job_id)
        if existing is None:
            audit_log.append(
                str(job_id), "job_failed",
                error=ORPHAN_ERROR, error_category=ORPHAN_CATEGORY,
            )
            resolutions.append((job_id, JobStatus.failed, ORPHAN_ERROR))
        else:
            resolutions.append((job_id, existing, None))

    async with session_scope() as s:
        for job_id, status, err in resolutions:
            values = {"status": status.value, "completed_at": datetime.now(timezone.utc)}
            if err is not None:
                values["error_message"] = err
            await s.execute(update(Job).where(Job.id == job_id).values(**values))

    # Keep the incremental audit index in step (nightly rebuild would otherwise be
    # the first place these show up), mirroring _finish_job.
    for job_id, _, _ in resolutions:
        try:
            append_to_index(settings.audit_log_dir, str(job_id))
        except Exception:
            pass  # non-fatal; nightly rebuild catches anything missed

    logger.warning(
        "reconciled orphaned jobs", count=len(ids), job_ids=[str(j) for j in ids]
    )
    return len(ids)
