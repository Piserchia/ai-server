"""
DB + Redis connection helpers. Thin and async.

Usage:
    from src.db import async_session, redis

    async with async_session() as s:
        job = await s.get(Job, job_id)
        ...

    await redis.rpush("jobs:queue", str(job.id))
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config import settings

# ── Postgres ────────────────────────────────────────────────────────────────

engine = create_async_engine(
    settings.postgres_dsn,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    echo=False,
)

async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

# ── Redis ───────────────────────────────────────────────────────────────────

redis: aioredis.Redis = aioredis.from_url(
    settings.redis_url, encoding="utf-8", decode_responses=True
)

# ── Queue constants (one place, don't inline strings) ───────────────────────

QUEUE_JOBS = "jobs:queue"                         # RPUSH from gateways, BLPOP from runner
CHANNEL_JOB_STREAM = "jobs:stream"                # pub: jobs:stream:<job_id>
CHANNEL_JOB_DONE = "jobs:done"                    # pub: jobs:done:<job_id>
CHANNEL_JOB_CANCEL = "jobs:cancel"                # pub: jobs:cancel (body = job_id)


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Convenience context manager with commit-on-exit, rollback-on-error."""
    async with async_session() as s:
        try:
            yield s
            await s.commit()
        except Exception:
            await s.rollback()
            raise
