"""
Helper used by all three gateways (telegram, web, tests) to enqueue a job consistently.

One function: `enqueue_job(...)`. Creates the Job row, pushes to Redis, returns the Job.
"""

from __future__ import annotations

import uuid
from typing import Any

from src.db import QUEUE_JOBS, async_session, redis
from src.models import Job, JobKind, JobStatus

# Persisted origin (Observability Phase 1, migration 008). The two helpers
# below are pure and, as of A1, UNCALLED: A2 wires them into enqueue_job
# (deriving origin_channel/origin_ref from created_by when a producer passes
# no explicit origin) and A4's notice builder reads the stamped columns.
ORIGIN_CHANNELS: tuple[str, ...] = ("telegram", "web", "cli", "scheduler", "system")
_ORIGIN_REF_MAX = 64   # jobs.origin_ref / tasks.origin_ref are String(64)


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
) -> Job:
    """Create a Job row and push it onto the queue.

    task_id / parent_job_id are set at creation (P2) — previously every call
    site did a separate UPDATE after enqueue, which left a small window where
    the runner could pick up a task job before its task linkage existed.
    """
    job = Job(
        kind=kind,
        description=description,
        payload=payload,
        project_id=project_id,
        status=JobStatus.queued.value,
        created_by=created_by,
        task_id=task_id,
        parent_job_id=parent_job_id,
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
