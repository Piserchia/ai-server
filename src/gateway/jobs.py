"""
Helper used by all three gateways (telegram, web, tests) to enqueue a job consistently.

One function: `enqueue_job(...)`. Creates the Job row, pushes to Redis, returns the Job.
"""

from __future__ import annotations

import uuid
from typing import Any

from src.db import QUEUE_JOBS, async_session, redis
from src.models import Job, JobKind, JobStatus


async def enqueue_job(
    description: str,
    *,
    kind: str = JobKind.task.value,
    payload: dict[str, Any] | None = None,
    project_id: uuid.UUID | None = None,
    created_by: str = "unknown",
) -> Job:
    job = Job(
        kind=kind,
        description=description,
        payload=payload,
        project_id=project_id,
        status=JobStatus.queued.value,
        created_by=created_by,
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
