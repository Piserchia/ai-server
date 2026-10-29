"""
Helper used by all three gateways (telegram, web, tests) to enqueue a job consistently.

One function: `enqueue_job(...)`. Creates the Job row, pushes to Redis, returns the Job.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from src import audit_log
from src.db import QUEUE_JOBS, async_session, redis
from src.models import Job, JobKind, JobStatus

# Persisted origin (Observability Phase 1, migration 008). `enqueue_job`
# derives origin_channel/origin_ref from created_by through the pure helper
# below when a producer passes no explicit origin (A2); A4's notice builder
# reads the stamped columns.
ORIGIN_CHANNELS: tuple[str, ...] = ("telegram", "web", "cli", "scheduler", "system")
_ORIGIN_CHANNEL_MAX = 16   # jobs.origin_channel / tasks.origin_channel are String(16)
_ORIGIN_REF_MAX = 64       # jobs.origin_ref / origin_thread (and tasks') are String(64)


def origin_from_created_by(created_by: str | None) -> tuple[str, str | None]:
    """Pure. Fallback (origin_channel, origin_ref) for producers that pass no
    explicit origin. Mirrors migration 008's `_BACKFILL_ORIGIN` CASE arm for
    arm so backfilled and new rows agree: `telegram:<chat>` → ('telegram',
    <chat>); `web` → ('web', None); `scheduler` → ('scheduler', None);
    everything else (dispatch-mcp, event-trigger*, learning:, escalation*,
    plan:, evaluator:, auto-continue:, deploy-autopilot, owner-*, …) →
    ('system', created_by). Refs are clipped to the String(64) column and an
    empty ref is None, never '' (the SQL side's NULLIF)."""
    cb = (created_by or "").strip()
    if cb.startswith("telegram:"):
        ref = cb.split(":", 1)[1].strip()
        return "telegram", (ref[:_ORIGIN_REF_MAX] or None)
    if cb == "web":
        return "web", None
    if cb == "scheduler":
        return "scheduler", None
    return "system", (cb[:_ORIGIN_REF_MAX] or None)


async def enqueue_job(
    description: str,
    *,
    kind: str = JobKind.task.value,
    payload: dict[str, Any] | None = None,
    project_id: uuid.UUID | None = None,
    created_by: str = "unknown",
    task_id: uuid.UUID | None = None,
    parent_job_id: uuid.UUID | None = None,
    origin_channel: str | None = None,
    origin_ref: str | None = None,
    origin_thread: str | None = None,
) -> Job:
    """Create a Job row and push it onto the queue.

    task_id / parent_job_id are set at creation (P2) — previously every call
    site did a separate UPDATE after enqueue, which left a small window where
    the runner could pick up a task job before its task linkage existed.

    origin_* (Observability Phase 1 A2, migration 008) is the persisted
    job→channel binding that replaces the bot's in-process `_job_to_chat`:
    producers that know their origin pass it (the Telegram launch sites,
    the web dashboard); everyone else gets `origin_channel`/`origin_ref`
    derived from `created_by` by `origin_from_created_by`. An explicit
    `origin_channel` is taken as-is — its ref is NOT derived (a web launch
    carries `web`/NULL, matching the 008 backfill) — and must be one of
    `ORIGIN_CHANNELS` (ValueError otherwise: the column vocabulary is fixed
    by migration 008's CASE and is not widened by a caller). An empty
    `origin_channel` derives like an omitted one; empty `origin_ref` /
    `origin_thread` land as NULL; values are clipped to their columns.
    """
    if not origin_channel:
        origin_channel, derived_ref = origin_from_created_by(created_by)
        if origin_ref is None:
            origin_ref = derived_ref
    elif origin_channel not in ORIGIN_CHANNELS:
        raise ValueError(
            f"origin_channel {origin_channel!r} is not one of {ORIGIN_CHANNELS}")
    job = Job(
        kind=kind,
        description=description,
        payload=payload,
        project_id=project_id,
        status=JobStatus.queued.value,
        created_by=created_by,
        task_id=task_id,
        parent_job_id=parent_job_id,
        origin_channel=origin_channel[:_ORIGIN_CHANNEL_MAX],
        origin_ref=(origin_ref or None) and origin_ref[:_ORIGIN_REF_MAX],
        origin_thread=(origin_thread or None) and origin_thread[:_ORIGIN_REF_MAX],
    )
    async with async_session() as s:
        s.add(job)
        await s.commit()
        await s.refresh(job)
    await redis.rpush(QUEUE_JOBS, str(job.id))
    return job


async def cancel_job(job_id: uuid.UUID) -> None:
    """Publish a cancel request. The runner picks it up and calls session.interrupt()."""
    from src.db import CHANNEL_JOB_CANCEL
    await redis.publish(CHANNEL_JOB_CANCEL, str(job_id))


async def find_job_by_prefix(prefix: str) -> Job | None:
    """
    Resolve an 8-char prefix (as shown in Telegram) to a full job.
    Returns None if 0 or >1 matches.
    """
    from sqlalchemy import cast, text
    from sqlalchemy.dialects.postgresql import UUID

    async with async_session() as s:
        try:
            # Try full UUID first
            return await s.get(Job, uuid.UUID(prefix))
        except ValueError:
            pass

        # Fall back to prefix match on string-cast id
        result = await s.execute(
            text("SELECT id FROM jobs WHERE CAST(id AS TEXT) LIKE :p LIMIT 2"),
            {"p": f"{prefix}%"},
        )
        ids = [row[0] for row in result.fetchall()]
        if len(ids) == 1:
            return await s.get(Job, ids[0])
        return None  # 0 or ambiguous


# ── E3: durable cancel — ONE semantics for every cancel site (D-P1-4) ────────

def cancel_action_for_status(status: str) -> str:
    """Pure. queued/deferred → remove from Redis + flip the row here;
    running → publish jobs:cancel (the runner interrupts, INV-8);
    anything else → no-op (a second /cancel is harmless)."""
    if status in (JobStatus.queued.value, JobStatus.deferred.value):
        return "lrem_and_flip"
    if status == JobStatus.running.value:
        return "publish"
    return "noop"


async def remove_from_queue(job_id: uuid.UUID | str) -> int:
    """LREM every copy of the id from jobs:queue. Idempotent."""
    return int(await redis.lrem(QUEUE_JOBS, 0, str(job_id)))


async def cancel_job_durable(job: Job, *, stage: str) -> str:
    """Cancel a job whatever its state. The four cancel sites — the task
    Cancel button (`stage="button"`), `/cancel <prefix>` (`"telegram"`),
    `DELETE /api/jobs/{id}` (`"api"`) and `/clear` (`"cleared"`) — all route
    here, so there is one vocabulary: `status=cancelled`,
    `terminal_reason="interrupted"` (spec §2.4's value — never a 16th
    `cancelled`), `error_message="cancelled by user (<stage>)"`, one
    `job_cancelled{stage}` audit row on a real flip. The runner's listener
    stamps the same for a running job it interrupts (`stage="running"`).

    Returns `cancelled_queued` | `cancel_requested` | `already_terminal`.
    A queued/deferred row is LREM'd and flipped under
    `WHERE status IN (queued, deferred)` (INV-9 safe); rowcount 0 means the
    runner's running-flip or another cancel won the race — reported, never
    double-written.
    """
    from sqlalchemy import select, update as sql_update

    action = cancel_action_for_status(job.status)
    if action == "publish":
        await cancel_job(job.id)
        return "cancel_requested"
    if action == "noop":
        return "already_terminal"
    # Flip FIRST, then LREM (review 2026-10-29): with LREM first, a DB failure
    # would strand a `queued` row that is no longer in Redis (invisible until
    # the next restart's requeue); with the flip first, a Redis failure leaves
    # a dead id the runner skips gracefully (`_process_job` returns on
    # status != queued), and the runner popping it in between is skipped too.
    async with async_session() as s:
        res = await s.execute(
            sql_update(Job)
            .where(Job.id == job.id,
                   Job.status.in_([JobStatus.queued.value, JobStatus.deferred.value]))
            .values(status=JobStatus.cancelled.value,
                    terminal_reason="interrupted",
                    error_message=f"cancelled by user ({stage})",
                    completed_at=datetime.now(timezone.utc))
        )
        await s.commit()
        if getattr(res, "rowcount", 0) == 0:
            # Lost the race: the runner's queued→running flip or another
            # cancel got there first. Re-read — a RUNNING row still gets the
            # user's cancel (the publish); only a terminal one is a no-op.
            fresh = (await s.execute(select(Job.status).where(Job.id == job.id))).scalar()
            if fresh == JobStatus.running.value:
                await cancel_job(job.id)
                return "cancel_requested"
            return "already_terminal"
    await remove_from_queue(job.id)
    audit_log.append(str(job.id), "job_cancelled", stage=stage)
    return "cancelled_queued"
