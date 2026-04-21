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
import json
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
from src.gateway.jobs import enqueue_job
from src.models import Job, JobStatus, Project, Schedule
from src.registry.skills import load as load_skill
from src.runner.events import event_loop
from src.runner.learning import maybe_extract_and_enqueue as maybe_extract_learning
from src.runner.review import ReviewOutcome, get_git_diff, run_code_review
from src.runner import quota, session as session_mod, writeback

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

        # Code review — runs for skills that opt in via post_review.trigger
        if job.kind not in ("chat", "_writeback") and not (job.payload or {}).get("escalated_from"):
            try:
                await _maybe_review(job, result)
            except Exception:
                log.exception("code review failed (non-fatal)")

        # Write-back verification — skip for chat and the _writeback skill itself
        if job.kind not in ("chat", "_writeback") and job.resolved_skill != "_writeback":
            try:
                await _verify_writeback(job, result)
            except Exception:
                log.exception("writeback verification failed (non-fatal)")

        # Learning extraction — skip chat, all internal skills (any kind starting
        # with "_"), and escalation retries (would double-count).
        is_internal = job.kind == "chat" or job.kind.startswith("_")
        is_internal_skill = (job.resolved_skill or "").startswith("_")
        is_escalation = bool((job.payload or {}).get("escalated_from"))
        if not is_internal and not is_internal_skill and not is_escalation:
            try:
                learning_summary = (result or {}).get("summary", "") if result else ""
                await maybe_extract_learning(str(job_id), learning_summary)
            except Exception:
                log.exception("learning extraction failed (non-fatal)")

        # Task lifecycle — if this job belongs to a task, update task state
        if job.task_id:
            try:
                await _update_task_after_job(job, result)
            except Exception:
                log.exception("task lifecycle update failed (non-fatal)")

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
        audit_log.append(str(job_id), "job_failed", error="session_timeout",
                         error_category="timeout")
        await _finish_job(job_id, JobStatus.failed, error="Session timed out")
        log.warning("job timeout")

    except Exception as exc:
        from src.runner.audit_index import categorize_error
        err_str = str(exc)[:500]
        audit_log.append(str(job_id), "job_failed", error=err_str,
                         error_category=categorize_error(err_str))
        await _finish_job(job_id, JobStatus.failed, error=err_str)
        log.exception("job failed")

        # Escalation: if the skill declares on_failure, enqueue a retry with
        # the escalated model/effort. One level only, guarded by a payload flag.
        try:
            await _maybe_escalate(job)
        except Exception:
            log.exception("escalation attempt failed (non-fatal)")


async def _maybe_review(job: Job, result: dict) -> None:
    """
    After a code-touching session, run the code-review sub-agent on the diff.
    Stamps jobs.review_outcome. If blocker, changes status to awaiting_user.
    """
    skill_name = job.resolved_skill
    if not skill_name:
        return
    skill_cfg = load_skill(skill_name)
    if not skill_cfg:
        return

    trigger = skill_cfg.post_review.get("trigger", "never")
    if trigger == "never":
        return

    # Resolve the cwd
    if job.project_id:
        async with async_session() as s:
            proj = await s.get(Project, job.project_id)
            cwd = settings.projects_dir / proj.slug if proj else settings.server_root
    else:
        slug = (job.payload or {}).get("project_slug")
        cwd = (
            settings.projects_dir / slug
            if slug and (settings.projects_dir / slug).exists()
            else settings.server_root
        )

    diff = get_git_diff(cwd)
    if not diff:
        logger.debug("no diff for review, skipping", job_id=str(job.id)[:8])
        return

    outcome = await run_code_review(str(job.id), diff, cwd)

    # Stamp review_outcome on the job
    async with session_scope() as s:
        await s.execute(
            update(Job).where(Job.id == job.id).values(
                review_outcome=outcome.value,
            )
        )

    if outcome == ReviewOutcome.blocker:
        logger.warning("code review BLOCKER", job_id=str(job.id)[:8])
        await _finish_job(
            job.id, JobStatus.awaiting_user,
            error="Code review flagged a blocker. Check the audit log.",
        )


async def _verify_writeback(job: Job, result: dict) -> None:
    """
    After a session completes, check if it modified non-doc files without
    updating any CHANGELOG. If so, enqueue a child `_writeback` job.
    """
    # Resolve the cwd that the session ran in (same logic as session.py)
    if job.project_id:
        async with async_session() as s:
            proj = await s.get(Project, job.project_id)
            cwd = settings.projects_dir / proj.slug if proj else settings.server_root
    else:
        slug = (job.payload or {}).get("project_slug")
        cwd = (
            settings.projects_dir / slug
            if slug and (settings.projects_dir / slug).exists()
            else settings.server_root
        )

    needs, modified = writeback.needs_writeback(cwd)
    if not needs:
        return

    parent_summary = (result or {}).get("summary", "")[:2000]
    description = (
        f"Write-back follow-up for job {str(job.id)[:8]} "
        f"({job.resolved_skill or job.kind}). "
        f"Prior session modified: {', '.join(modified[:10])}. "
        f"Update any CHANGELOG.md files that should reflect these changes."
    )
    payload = {
        "parent_job_summary": parent_summary,
        "modified_files": modified,
        "cwd": str(cwd),
    }
    child = await enqueue_job(
        description,
        kind="_writeback",
        payload=payload,
        project_id=job.project_id,
        created_by=f"writeback:{str(job.id)[:8]}",
    )
    # Link child → parent
    async with session_scope() as s:
        await s.execute(
            update(Job).where(Job.id == child.id).values(parent_job_id=job.id)
        )
    audit_log.append(
        str(job.id), "writeback_spawned",
        child_job_id=str(child.id),
        modified_files=modified[:20],
    )
    logger.info("write-back child job enqueued", parent=str(job.id), child=str(child.id))


async def _maybe_escalate(job: Job) -> None:
    """
    If the failed job's skill declares on_failure escalation, enqueue a retry
    with the escalated config. One level only; guarded by the `escalated_from`
    payload flag to prevent loops.
    """
    if (job.payload or {}).get("escalated_from"):
        return   # already an escalation; don't recurse

    skill_name = job.resolved_skill
    if not skill_name:
        return
    skill_cfg = load_skill(skill_name)
    if not skill_cfg or not skill_cfg.escalation:
        return
    on_failure = skill_cfg.escalation.get("on_failure")
    if not on_failure:
        return

    esc_model = on_failure.get("model")
    esc_effort = on_failure.get("effort")
    if not esc_model and not esc_effort:
        return

    new_payload = dict(job.payload or {})
    new_payload["escalated_from"] = str(job.id)
    if esc_model:
        new_payload["model"] = esc_model
    if esc_effort:
        new_payload["effort"] = esc_effort

    child = await enqueue_job(
        job.description,
        kind=job.kind,
        payload=new_payload,
        project_id=job.project_id,
        created_by=f"escalation:{str(job.id)[:8]}",
    )
    async with session_scope() as s:
        await s.execute(
            update(Job).where(Job.id == child.id).values(parent_job_id=job.id)
        )
    audit_log.append(
        str(job.id), "escalation_spawned",
        child_job_id=str(child.id),
        escalated_model=esc_model,
        escalated_effort=esc_effort,
    )
    logger.info(
        "escalation child job enqueued",
        parent=str(job.id), child=str(child.id),
        model=esc_model, effort=esc_effort,
    )


async def _update_task_after_job(job: Job, result: dict | None) -> None:
    """After a job completes, update its parent task's state.

    Scans the audit log for task_question or task_complete events to
    determine whether the task needs user input, approval, or is done.
    """
    from src.models import Task, TaskTurn, TaskStatus

    # Record assistant turn
    summary = (result or {}).get("summary", "") or ""
    if not summary:
        summary = f"Job {str(job.id)[:8]} completed."

    async with session_scope() as s:
        # Get next turn number
        from sqlalchemy import func as sqlfunc
        max_turn = await s.execute(
            select(sqlfunc.max(TaskTurn.turn_number))
            .where(TaskTurn.task_id == job.task_id)
        )
        last = max_turn.scalar() or 0

        s.add(TaskTurn(
            task_id=job.task_id,
            turn_number=last + 1,
            role="assistant",
            content=summary,
            job_id=job.id,
        ))

    # Check audit log for task_question, task_choices, or task_complete events
    events = audit_log.read(job.id)
    question = None
    choices_event = None
    is_complete = False
    for evt in events:
        if evt.get("kind") == "task_choices":
            choices_event = evt
        elif evt.get("kind") == "task_question":
            question = evt.get("question", "")
        elif evt.get("kind") == "task_complete":
            is_complete = True

    # Update task status
    if choices_event:
        async with session_scope() as s:
            await s.execute(
                update(Task)
                .where(Task.id == job.task_id)
                .values(status=TaskStatus.awaiting_user.value, updated_at=datetime.now(timezone.utc))
            )
        await redis.publish(
            "tasks:notify",
            json.dumps({
                "task_id": str(job.task_id),
                "type": "choices",
                "question": choices_event.get("question", "Pick one:"),
                "choices": choices_event.get("options", []),
            }),
        )
    elif question:
        async with session_scope() as s:
            await s.execute(
                update(Task)
                .where(Task.id == job.task_id)
                .values(status=TaskStatus.awaiting_user.value, updated_at=datetime.now(timezone.utc))
            )
        # Notify user via Redis (Telegram bot listens)
        await redis.publish(
            "tasks:notify",
            json.dumps({
                "task_id": str(job.task_id),
                "type": "question",
                "text": question,
            }),
        )
    elif is_complete:
        async with session_scope() as s:
            await s.execute(
                update(Task)
                .where(Task.id == job.task_id)
                .values(status=TaskStatus.pending_approval.value, updated_at=datetime.now(timezone.utc))
            )
        await redis.publish(
            "tasks:notify",
            json.dumps({
                "task_id": str(job.task_id),
                "type": "approval_request",
                "text": summary,
            }),
        )
    else:
        # Job completed without explicit task signals — treat as pending approval
        async with session_scope() as s:
            await s.execute(
                update(Task)
                .where(Task.id == job.task_id)
                .values(status=TaskStatus.pending_approval.value, updated_at=datetime.now(timezone.utc))
            )
        await redis.publish(
            "tasks:notify",
            json.dumps({
                "task_id": str(job.task_id),
                "type": "approval_request",
                "text": summary,
            }),
        )


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

    # Incremental audit index update (B2)
    try:
        from src.runner.audit_index import append_to_index
        append_to_index(settings.audit_log_dir, str(job_id))
    except Exception:
        pass  # non-fatal; nightly rebuild catches anything missed


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
        asyncio.create_task(event_loop(_shutdown), name="event_loop"),
    ]
    await asyncio.gather(*tasks, return_exceptions=True)
    logger.info("runner stopped")


if __name__ == "__main__":
    asyncio.run(main())
