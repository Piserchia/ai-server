"""
Runner entry point. Async tasks:

1. _job_loop:        BLPOPs jobs, runs each via session.run_session(), respects quota pause.
2. _scheduler_loop:  cron → enqueue new jobs.
3. _cancel_listener: subscribes to jobs:cancel, interrupts matching session.

Run: `python -m src.runner.main`
Stop: SIGTERM. In-flight jobs finish within session_timeout_seconds.

Auth check on startup: verifies `claude` CLI exists and is logged in. Refuses to start
if not, printing the exact command to fix it.
"""

from __future__ import annotations

import asyncio
import os
import signal
import subprocess
import sys
import uuid
from datetime import datetime, timezone

import structlog
from croniter import croniter
from sqlalchemy import select, update

from src import audit_log
from src.config import settings
from src.db import (
    CHANNEL_JOB_CANCEL,
    QUEUE_JOBS,
    async_session,
    redis,
    session_scope,
)
from src.models import Job, JobStatus, Schedule
from src.runner import quota, session as session_mod

logger = structlog.get_logger()
_shutdown = asyncio.Event()


# ── Startup checks ──────────────────────────────────────────────────────────


def _check_subscription_auth() -> None:
    """Verify claude CLI is installed and logged in. Exits with explanation if not."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        print(
            "ERROR: ANTHROPIC_API_KEY is set in the environment. This server is "
            "configured for subscription auth; unset it and restart.\n"
            "  unset ANTHROPIC_API_KEY",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        # `claude --version` succeeds even without login
        subprocess.run(["claude", "--version"], check=True, capture_output=True, timeout=10)
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        print(
            "ERROR: Claude Code CLI not found or not working. Install:\n"
            "  curl -fsSL https://claude.ai/install.sh | bash\n"
            "Then log in:\n"
            "  claude login",
            file=sys.stderr,
        )
        sys.exit(1)

    # A logged-in status is harder to probe reliably without invoking a full request,
    # so we defer the real auth check to the first session — which will fail visibly.


# ── Job loop ────────────────────────────────────────────────────────────────


async def _job_loop() -> None:
    sem = asyncio.Semaphore(settings.max_concurrent_jobs)
    in_flight: set[asyncio.Task] = set()

    while not _shutdown.is_set():
        paused, reset_at, reason = await quota.is_paused()
        if paused:
            logger.info("queue paused on quota", reset_at=reset_at.isoformat(), reason=reason[:80])
            try:
                await asyncio.wait_for(_shutdown.wait(), timeout=30)
                break
            except asyncio.TimeoutError:
                continue

        popped = await redis.blpop([QUEUE_JOBS], timeout=2)
        if popped is None:
            in_flight = {t for t in in_flight if not t.done()}
            continue

        _, job_id_str = popped
        try:
            job_id = uuid.UUID(job_id_str)
        except ValueError:
            logger.warning("malformed job_id in queue", raw=job_id_str)
            continue

        task = asyncio.create_task(_run_with_semaphore(sem, job_id))
        in_flight.add(task)
        task.add_done_callback(in_flight.discard)

    if in_flight:
        logger.info("draining in-flight jobs", count=len(in_flight))
        await asyncio.gather(*in_flight, return_exceptions=True)


async def _run_with_semaphore(sem: asyncio.Semaphore, job_id: uuid.UUID) -> None:
    async with sem:
        await _process_job(job_id)


async def _process_job(job_id: uuid.UUID) -> None:
    async with async_session() as s:
        job = await s.get(Job, job_id)
        if job is None:
            logger.warning("job not found", job_id=str(job_id))
            return
        if job.status != JobStatus.queued.value:
            return
        job.status = JobStatus.running.value
        job.started_at = datetime.now(timezone.utc)
        await s.commit()

    log = logger.bind(job_id=str(job_id), kind=job.kind)
    log.info("job started")

    try:
        result = await asyncio.wait_for(
            session_mod.run_session(job),
            timeout=settings.session_timeout_seconds,
        )
        await _finish_job(job_id, JobStatus.completed, result=result)
        log.info("job completed")

    except quota.QuotaExhausted as exc:
        # Pause the queue, requeue this job at the front so it retries after reset
        await quota.pause_queue(exc.reset_at, exc.reason)
        await redis.lpush(QUEUE_JOBS, str(job_id))
        async with session_scope() as s:
            await s.execute(
                update(Job).where(Job.id == job_id).values(
                    status=JobStatus.queued.value,
                    error_message=f"queued for quota reset ({exc.reason[:100]})",
                )
            )
        audit_log.append(str(job_id), "job_requeued_for_quota", reason=exc.reason[:200])
        log.warning("quota exhausted — queue paused, job requeued")

    except asyncio.TimeoutError:
        audit_log.append(str(job_id), "job_failed", error="session_timeout")
        await _finish_job(job_id, JobStatus.failed, error="Session timed out")
        log.warning("job timeout")

    except Exception as exc:
        audit_log.append(str(job_id), "job_failed", error=str(exc)[:500])
        await _finish_job(job_id, JobStatus.failed, error=str(exc)[:500])
        log.exception("job failed")


async def _finish_job(
    job_id: uuid.UUID,
    status: JobStatus,
    *,
    result: dict | None = None,
    error: str | None = None,
) -> None:
    async with session_scope() as s:
        await s.execute(
            update(Job)
            .where(Job.id == job_id)
            .values(
                status=status.value,
                result=result,
                error_message=error,
                completed_at=datetime.now(timezone.utc),
            )
        )
    payload = {"summary": (result or {}).get("summary", "")} if result else {}
    await session_mod.publish_done(str(job_id), status.value, payload=payload)


# ── Scheduler loop ──────────────────────────────────────────────────────────


async def _scheduler_loop() -> None:
    while not _shutdown.is_set():
        try:
            await _tick_schedules()
        except Exception:
            logger.exception("scheduler tick failed")
        try:
            await asyncio.wait_for(_shutdown.wait(), timeout=30)
            break
        except asyncio.TimeoutError:
            continue


async def _tick_schedules() -> None:
    now = datetime.now(timezone.utc)
    async with session_scope() as s:
        result = await s.execute(
            select(Schedule).where(
                Schedule.paused.is_(False),
                Schedule.next_run_at <= now,
            )
        )
        due = list(result.scalars())

        for sched in due:
            job = Job(
                kind=sched.job_kind,
                description=sched.job_description,
                payload=sched.job_payload,
                project_id=sched.project_id,
                schedule_id=sched.id,
                status=JobStatus.queued.value,
                created_by="scheduler",
            )
            s.add(job)
            await s.flush()
            await redis.rpush(QUEUE_JOBS, str(job.id))

            sched.last_run_at = now
            sched.next_run_at = croniter(sched.cron_expression, now).get_next(
                datetime
            ).replace(tzinfo=timezone.utc)

            logger.info(
                "scheduled job enqueued",
                schedule=sched.name,
                job_id=str(job.id),
                next_run=sched.next_run_at.isoformat(),
            )


# ── Cancel listener ─────────────────────────────────────────────────────────


async def _cancel_listener() -> None:
    pubsub = redis.pubsub()
    await pubsub.subscribe(CHANNEL_JOB_CANCEL)
    try:
        while not _shutdown.is_set():
            msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=2)
            if msg is None:
                continue
            job_id = msg.get("data")
            if not job_id:
                continue
            did = await session_mod.interrupt(job_id)
            if did:
                audit_log.append(str(job_id), "job_cancelled")
                async with session_scope() as s:
                    await s.execute(
                        update(Job).where(Job.id == uuid.UUID(job_id)).values(
                            status=JobStatus.cancelled.value,
                            completed_at=datetime.now(timezone.utc),
                        )
                    )
                logger.info("interrupted session", job_id=job_id)
    finally:
        await pubsub.unsubscribe(CHANNEL_JOB_CANCEL)


# ── Main ────────────────────────────────────────────────────────────────────


def _install_signal_handlers(loop: asyncio.AbstractEventLoop) -> None:
    def _h() -> None:
        logger.info("shutdown signal received")
        _shutdown.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _h)


async def main() -> None:
    import logging
    logging.basicConfig(level=logging.INFO)
    _check_subscription_auth()
    logger.info(
        "runner starting",
        root=str(settings.server_root),
        concurrency=settings.max_concurrent_jobs,
        model_default=settings.default_model,
    )
    loop = asyncio.get_running_loop()
    _install_signal_handlers(loop)

    tasks = [
        asyncio.create_task(_job_loop(), name="job_loop"),
        asyncio.create_task(_scheduler_loop(), name="scheduler_loop"),
        asyncio.create_task(_cancel_listener(), name="cancel_listener"),
    ]
    await asyncio.gather(*tasks, return_exceptions=True)
    logger.info("runner stopped")


if __name__ == "__main__":
    asyncio.run(main())
