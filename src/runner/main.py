"""
Runner entry point. Async tasks:

1. _job_loop:        BLPOPs jobs, runs each via session.run_session(), respects quota pause.
2. _scheduler_loop:  cron → enqueue new jobs.
3. _cancel_listener: subscribes to jobs:cancel, interrupts matching session.

On startup, before the loops begin, reconcile_orphaned_jobs() fails any job left
in 'running' by a previous process that died mid-job (see runner/reconcile.py).

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
    KEY_RUNNER_HEARTBEAT,
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
from src.runner.reconcile import reconcile_orphaned_jobs
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
        # Liveness heartbeat. The loop iterates at least every 2s (BLPOP timeout)
        # and keeps ticking even while jobs run in the background, so a fresh
        # value means the runner is alive. GET /health reads this; an external
        # Cloudflare Worker reads /health so silence can't masquerade as health.
        try:
            await redis.set(KEY_RUNNER_HEARTBEAT, datetime.now(timezone.utc).isoformat())
        except Exception:
            logger.warning("heartbeat write failed (non-fatal)")

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


async def _preflight_check(job: Job, log) -> str | None:
    """Validate job config before running a session. Returns error string or None.

    Checks:
    1. If task_id set but no skill resolved via router, inherit from task's first job
    2. CWD path must exist
    """
    # Check 1: If this is a task continuation with no skill, inherit from parent
    if job.task_id and not job.kind.startswith("_"):
        # The router runs later in run_session, but if kind="task" and description
        # won't match the router, we can force the skill here by changing job.kind
        from src.runner.router import route
        if job.kind == "task" and not route(job.description):
            # Router won't match — look up the task's original skill
            async with async_session() as s:
                result = await s.execute(
                    select(Job.resolved_skill)
                    .where(Job.task_id == job.task_id)
                    .where(Job.resolved_skill.isnot(None))
                    .order_by(Job.created_at)
                    .limit(1)
                )
                row = result.first()
                if row and row[0]:
                    original_skill = row[0]
                    # Change job kind to force skill resolution
                    async with async_session() as s2:
                        await s2.execute(
                            update(Job).where(Job.id == job.id).values(kind=original_skill)
                        )
                        await s2.commit()
                    job.kind = original_skill
                    log.info("preflight: inherited skill from task", skill=original_skill)

    # Check 2: CWD existence
    cwd = await session_mod._resolve_cwd(job)
    if not cwd.exists():
        return f"CWD does not exist: {cwd}"

    return None  # all checks passed


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

    # Pre-flight validation: catch misconfigs before wasting a session
    preflight_error = await _preflight_check(job, log)
    if preflight_error:
        audit_log.append(str(job_id), "job_failed", error=preflight_error,
                         error_category="preflight")
        await _finish_job(job_id, JobStatus.failed, error=preflight_error)
        log.warning("preflight failed", reason=preflight_error)
        if job.task_id:
            try:
                await _update_task_after_job(job, None)
            except Exception:
                pass
        return

    try:
        result = await asyncio.wait_for(
            session_mod.run_session(job),
            timeout=settings.session_timeout_seconds,
        )
        await _finish_job(job_id, JobStatus.completed, result=result)
        log.info("job completed")

        # Plan DAG: promote deferred siblings whose dependencies are now met (P2)
        if job.task_id:
            try:
                from src.runner import plans as plans_mod
                promoted = await plans_mod.promote_deferred_for(job)
                if promoted:
                    log.info("promoted deferred jobs", count=promoted)
            except Exception:
                log.exception("deferred promotion failed (non-fatal)")

        # Code review — runs for skills that opt in via post_review.trigger.
        # Internal skills (leading _, e.g. _evaluate/_writeback) are exempt.
        _is_internal_kind = job.kind == "chat" or job.kind.startswith("_")
        if not _is_internal_kind and not (job.payload or {}).get("escalated_from"):
            try:
                await _maybe_review(job, result)
            except Exception:
                log.exception("code review failed (non-fatal)")

        # Write-back verification — skip for chat and internal skills
        if not _is_internal_kind and not (job.resolved_skill or "").startswith("_"):
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
    Multi-level escalation chain:
    - Level 0 → 1: Standard escalation (higher model/effort from skill config)
    - Level 1 → 2: Self-diagnose with full context (audit log + task turns + error)
    - Level 2 → 3: Full-context max-effort debug (last resort)
    - Level 3: Give up, notify user
    """
    payload = job.payload or {}
    current_level = payload.get("escalation_level", 0)

    if current_level >= 3:
        # Terminal — cascade failure to any deferred dependents, notify user
        if job.task_id:
            from src.models import Task, TaskStatus
            try:
                from src.runner import plans as plans_mod
                cascaded = await plans_mod.fail_dependents_of(job)
                if cascaded:
                    logger.warning("failed deferred dependents", count=cascaded,
                                   job_id=str(job.id)[:8])
            except Exception:
                logger.exception("dependency cascade failed (non-fatal)")
            async with session_scope() as s:
                await s.execute(
                    update(Task).where(Task.id == job.task_id).values(
                        status=TaskStatus.failed.value)
                )
            from src.db import redis as _redis
            await _redis.publish("tasks:notify", json.dumps({
                "task_id": str(job.task_id),
                "type": "failed",
                "text": f"Task failed after 3 escalation attempts. "
                        f"Last error: {(job.error_message or 'unknown')[:300]}. "
                        f"Reply to retry or /clear to abandon.",
            }))
        return

    if current_level == 0:
        # Level 0 → 1: Standard escalation via skill config
        skill_name = job.resolved_skill
        if not skill_name:
            # No skill = can't escalate via config. Jump to level 2.
            current_level = 1  # fall through to level 1→2 below
        else:
            skill_cfg = load_skill(skill_name)
            if skill_cfg and skill_cfg.escalation:
                on_failure = skill_cfg.escalation.get("on_failure")
                if on_failure:
                    esc_model = on_failure.get("model")
                    esc_effort = on_failure.get("effort")
                    if esc_model or esc_effort:
                        new_payload = dict(payload)
                        new_payload["escalation_level"] = 1
                        new_payload["escalated_from"] = str(job.id)
                        if esc_model:
                            new_payload["model"] = esc_model
                        if esc_effort:
                            new_payload["effort"] = esc_effort

                        child = await enqueue_job(
                            job.description, kind=job.kind, payload=new_payload,
                            project_id=job.project_id,
                            created_by=f"escalation:{str(job.id)[:8]}",
                        )
                        async with session_scope() as s:
                            await s.execute(
                                update(Job).where(Job.id == child.id).values(
                                    parent_job_id=job.id, task_id=job.task_id)
                            )
                        audit_log.append(str(job.id), "escalation_spawned",
                                         child_job_id=str(child.id), level=1)
                        logger.info("escalation level 1 enqueued",
                                    parent=str(job.id)[:8], child=str(child.id)[:8])
                        return

            # Skill has no escalation config — fall through to level 2
            current_level = 1

    if current_level == 1:
        # Level 1 → 2: Self-diagnose with full context
        # Gather context for the diagnostic session
        audit_events = audit_log.read(job.id, limit=30)
        audit_excerpt = json.dumps(audit_events[-20:], default=str)[:3000] if audit_events else "[]"

        task_context = ""
        if job.task_id:
            from src.models import TaskTurn
            async with async_session() as s:
                result = await s.execute(
                    select(TaskTurn.content)
                    .where(TaskTurn.task_id == job.task_id)
                    .order_by(TaskTurn.turn_number)
                )
                turns = [row[0] for row in result.all()]
                task_context = "\n---\n".join(turns)[:4000]

        diag_payload = {
            "escalation_level": 2,
            "escalated_from": str(job.id),
            "target_kind": "failed-task",
            "original_job_id": str(job.id),
            "original_skill": job.resolved_skill,
            "error": (job.error_message or "unknown")[:500],
            "error_category": (payload.get("error_category") or "unknown"),
            "task_context": task_context,
            "audit_excerpt": audit_excerpt,
        }

        child = await enqueue_job(
            f"Self-diagnose: job {str(job.id)[:8]} ({job.resolved_skill or job.kind}) "
            f"failed. Error: {(job.error_message or 'unknown')[:100]}",
            kind="self-diagnose",
            payload=diag_payload,
            created_by=f"escalation-L2:{str(job.id)[:8]}",
        )
        async with session_scope() as s:
            await s.execute(
                update(Job).where(Job.id == child.id).values(
                    parent_job_id=job.id, task_id=job.task_id)
            )
        audit_log.append(str(job.id), "escalation_spawned",
                         child_job_id=str(child.id), level=2)
        logger.info("escalation level 2 (self-diagnose) enqueued",
                    parent=str(job.id)[:8], child=str(child.id)[:8])
        return

    if current_level == 2:
        # Level 2 → 3: Full-context max-effort last resort
        diag_payload = dict(payload)
        diag_payload["escalation_level"] = 3
        diag_payload["effort"] = "max"

        child = await enqueue_job(
            f"LAST RESORT debug: escalation chain exhausted for job {str(job.id)[:8]}. "
            f"Full context in payload. Fix the root cause.",
            kind="self-diagnose",
            payload=diag_payload,
            created_by=f"escalation-L3:{str(job.id)[:8]}",
        )
        async with session_scope() as s:
            await s.execute(
                update(Job).where(Job.id == child.id).values(
                    parent_job_id=job.id, task_id=job.task_id)
            )
        audit_log.append(str(job.id), "escalation_spawned",
                         child_job_id=str(child.id), level=3)
        logger.info("escalation level 3 (last resort) enqueued",
                    parent=str(job.id)[:8], child=str(child.id)[:8])
        return


async def _record_task_turn(task_id, role: str, content: str, job_id=None) -> None:
    """Append one turn to a task's conversation."""
    from src.models import TaskTurn
    from sqlalchemy import func as sqlfunc

    async with session_scope() as s:
        max_turn = await s.execute(
            select(sqlfunc.max(TaskTurn.turn_number))
            .where(TaskTurn.task_id == task_id)
        )
        last = max_turn.scalar() or 0
        s.add(TaskTurn(
            task_id=task_id,
            turn_number=last + 1,
            role=role,
            content=content,
            job_id=job_id,
        ))


async def _set_task_status(task_id, status: str) -> None:
    from src.models import Task
    async with session_scope() as s:
        await s.execute(
            update(Task).where(Task.id == task_id).values(
                status=status, updated_at=datetime.now(timezone.utc))
        )


async def _notify_task(task_id, notify_type: str, **fields) -> None:
    await redis.publish("tasks:notify", json.dumps({
        "task_id": str(task_id), "type": notify_type, **fields,
    }))


async def _handle_plan_event(job: Job, plan: dict) -> None:
    """A `plan` session emitted a task_plan event: validate, store, and
    (auto-approve default) spawn the subtask DAG."""
    from src.models import Task, TaskStatus
    from src.registry.skills import list_all
    from src.runner import plans

    known_kinds = {cfg.name for cfg in list_all()} | {"task"}
    errors = plans.validate_plan(plan, known_kinds)
    if errors:
        logger.warning("plan validation failed for task %s: %s",
                       str(job.task_id)[:8], errors)
        await _set_task_status(job.task_id, TaskStatus.awaiting_user.value)
        await _notify_task(
            job.task_id, "question",
            text=("The planner produced an invalid plan "
                  f"({'; '.join(errors[:5])}). Reply to rephrase the ask, "
                  "or /clear to abandon."),
        )
        return

    async with session_scope() as s:
        await s.execute(
            update(Task).where(Task.id == job.task_id).values(
                plan=plan, updated_at=datetime.now(timezone.utc))
        )
    audit_log.append(str(job.id), "plan_stored",
                     subtasks=len(plan.get("subtasks", [])))

    plan_text = _format_plan_for_chat(plan)

    if settings.plan_auto_approve:
        await plans.spawn_plan_jobs(job.task_id, plan, created_by=f"plan:{str(job.id)[:8]}")
        await _record_task_turn(job.task_id, "system",
                                f"Plan approved automatically; spawning subtasks.\n{plan_text}")
        await _set_task_status(job.task_id, "active")
        await _notify_task(job.task_id, "plan", text=plan_text)
    else:
        await _set_task_status(job.task_id, TaskStatus.pending_approval.value)
        await _notify_task(job.task_id, "plan_approval", text=plan_text)


def _format_plan_for_chat(plan: dict) -> str:
    """Compact human-readable plan rendering for Telegram. Pure function."""
    lines = [f"Goal: {plan.get('goal', '')}"]
    lines.append("Steps:")
    for st in plan.get("subtasks", []):
        deps = st.get("depends_on") or []
        dep_note = f" (after {', '.join(map(str, deps))})" if deps else ""
        lines.append(f"  {st.get('id')}: [{st.get('kind')}] {st.get('description', '')[:120]}{dep_note}")
    criteria = plan.get("acceptance_criteria", [])
    if criteria:
        lines.append("Done when:")
        lines.extend(f"  - {c[:120]}" for c in criteria[:6])
    return "\n".join(lines)


async def _enqueue_evaluator(job: Job, summary: str, eval_round: int) -> None:
    """Spawn the _evaluate acceptance-check job for this task (P3)."""
    from src.models import Task

    plan = None
    task_description = ""
    async with async_session() as s:
        task = await s.get(Task, job.task_id)
        if task:
            plan = task.plan
            task_description = task.description

    payload = {
        "eval_round": eval_round,
        "task_description": task_description,
        "origin_kind": job.resolved_skill or job.kind,
        "origin_summary": summary[:2000],
    }
    if plan:
        payload["plan"] = plan
    slug = (job.payload or {}).get("project_slug")
    if slug:
        payload["project_slug"] = slug

    child = await enqueue_job(
        f"Evaluate task {str(job.task_id)[:8]} against its acceptance criteria "
        f"(round {eval_round}).",
        kind="_evaluate",
        payload=payload,
        project_id=job.project_id,
        created_by=f"evaluator:{str(job.id)[:8]}",
        task_id=job.task_id,
        parent_job_id=job.id,
    )
    audit_log.append(str(job.id), "evaluator_spawned",
                     child_job_id=str(child.id), eval_round=eval_round)
    await _notify_task(job.task_id, "progress",
                       text=f"Work complete — verifying against acceptance criteria (round {eval_round})...")


async def _handle_evaluator_result(job: Job, summary: str, events: list[dict]) -> None:
    """Process an _evaluate job's outcome: pass → auto-close with evidence;
    fail → spawn a fix round or hand to the user after max rounds."""
    from src.models import TaskStatus

    eval_pass = None
    eval_fail = None
    for evt in events:
        if evt.get("kind") == "eval_pass":
            eval_pass = evt
        elif evt.get("kind") == "eval_fail":
            eval_fail = evt

    payload = job.payload or {}
    eval_round = int(payload.get("eval_round", 1))

    if eval_pass:
        evidence = eval_pass.get("evidence", "") or summary
        await _record_task_turn(job.task_id, "system",
                                f"Evaluation passed (round {eval_round}). Evidence: {evidence[:1500]}",
                                job_id=job.id)
        await _set_task_status(job.task_id, TaskStatus.completed.value)
        await _notify_task(job.task_id, "completed",
                           text=f"{evidence[:3000]}")
        return

    if eval_fail:
        feedback = eval_fail.get("feedback", "") or summary or "Evaluation failed without details."
        await _record_task_turn(job.task_id, "system",
                                f"Evaluation FAILED (round {eval_round}): {feedback[:1500]}",
                                job_id=job.id)
        if eval_round < settings.max_eval_rounds:
            # Spawn a fix continuation with the evaluator's feedback
            origin_kind = payload.get("origin_kind") or "task"
            fix_payload = {"eval_round": eval_round}
            if payload.get("project_slug"):
                fix_payload["project_slug"] = payload["project_slug"]
            child = await enqueue_job(
                f"The acceptance evaluation failed. Fix the following and complete "
                f"the task: {feedback[:1500]}",
                kind=origin_kind,
                payload=fix_payload,
                project_id=job.project_id,
                created_by=f"eval-fix:{str(job.id)[:8]}",
                task_id=job.task_id,
                parent_job_id=job.id,
            )
            audit_log.append(str(job.id), "eval_fix_spawned",
                             child_job_id=str(child.id), eval_round=eval_round)
            await _set_task_status(job.task_id, "active")
            await _notify_task(job.task_id, "progress",
                               text=f"Evaluation found issues — fixing (round {eval_round}): {feedback[:400]}")
        else:
            await _set_task_status(job.task_id, TaskStatus.awaiting_user.value)
            await _notify_task(job.task_id, "question",
                               text=(f"Evaluation still failing after {eval_round} rounds:\n"
                                     f"{feedback[:2000]}\n\nReply with guidance, or /clear to abandon."))
        return

    # Evaluator emitted neither event — defensive: hand to the user with its text
    await _set_task_status(job.task_id, TaskStatus.pending_approval.value)
    await _notify_task(job.task_id, "approval_request",
                       text=summary or "Evaluator finished without a verdict.")


async def _update_task_after_job(job: Job, result: dict | None) -> None:
    """After a job completes, update its parent task's state.

    Scans the audit log for lifecycle events (task_plan / task_question /
    task_choices / task_complete / eval_pass / eval_fail) to determine
    whether the task needs planning fan-out, user input, evaluation, or is
    done.
    """
    from src.models import Task, TaskTurn, TaskStatus

    # Record assistant turn
    summary = (result or {}).get("summary", "") or ""
    if not summary:
        summary = f"Job {str(job.id)[:8]} completed."

    await _record_task_turn(job.task_id, "assistant", summary, job_id=job.id)

    # Scan audit log for lifecycle events
    events = audit_log.read(job.id)
    question = None
    choices_event = None
    plan_event = None
    is_complete = False
    for evt in events:
        if evt.get("kind") == "task_choices":
            choices_event = evt
        elif evt.get("kind") == "task_question":
            question = evt.get("question", "")
        elif evt.get("kind") == "task_complete":
            is_complete = True
        elif evt.get("kind") == "task_plan":
            plan_event = evt

    payload = job.payload or {}
    resolved = job.resolved_skill or job.kind or ""
    is_plan_subtask = bool(payload.get("plan_subtask"))

    # ── Planner output (P2) ─────────────────────────────────────────────
    if plan_event is not None and resolved == "plan":
        plan = plan_event.get("plan")
        if isinstance(plan, dict):
            await _handle_plan_event(job, plan)
            return
        # Malformed event → fall through to normal handling (summary shows it)

    # ── Evaluator output (P3) ───────────────────────────────────────────
    if resolved == "_evaluate":
        await _handle_evaluator_result(job, summary, events)
        return

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
        # task_complete = this job's work is done.
        from src.runner import plans as plans_mod

        # Plan subtasks: completion of ONE subtask isn't completion of the
        # task — the DAG drains first (promotion happens in _process_job).
        if is_plan_subtask:
            remaining = await plans_mod.plan_jobs_remaining(job.task_id, exclude_job_id=job.id)
            if remaining > 0:
                await _notify_task(
                    job.task_id, "progress",
                    text=f"Subtask {payload.get('plan_subtask')} done — {remaining} still in flight.",
                )
                return

        # All work done → acceptance evaluation (P3) or manual approval
        already_eval_round = int(payload.get("eval_round", 0))
        if settings.auto_evaluate:
            await _enqueue_evaluator(job, summary, eval_round=already_eval_round + 1)
        else:
            await _set_task_status(job.task_id, TaskStatus.pending_approval.value)
            await _notify_task(job.task_id, "approval_request", text=summary)
    elif is_plan_subtask:
        # Subtask ended without an explicit signal: never auto-continue these —
        # their successors are already queued in the DAG. If the DAG drained,
        # run the same completion path as task_complete.
        from src.runner import plans as plans_mod
        remaining = await plans_mod.plan_jobs_remaining(job.task_id, exclude_job_id=job.id)
        if remaining > 0:
            await _notify_task(
                job.task_id, "progress",
                text=f"Subtask {payload.get('plan_subtask')} finished — {remaining} still in flight.",
            )
            return
        already_eval_round = int(payload.get("eval_round", 0))
        if settings.auto_evaluate:
            await _enqueue_evaluator(job, summary, eval_round=already_eval_round + 1)
        else:
            await _set_task_status(job.task_id, TaskStatus.pending_approval.value)
            await _notify_task(job.task_id, "approval_request", text=summary)
    else:
        # No explicit event emitted. Guard against infinite auto-continue loops:
        # Only stop when the job IS the sentinel message itself — the sentinel
        # never emits a task signal by construction, so this check is both
        # necessary and sufficient to break the loop without cutting off
        # legitimate 3+ phase tasks (whose auto-continued jobs do real work
        # and may need further continuations).
        _SENTINEL = "Continue to the next phase of the plan."
        _is_sentinel = (job.description or "").strip() == _SENTINEL

        if _is_sentinel:
            logger.warning(
                "auto-continue sentinel detected — stopping at pending_approval",
                task_id=str(job.task_id)[:8], job_id=str(job.id)[:8],
            )
            async with session_scope() as s:
                await s.execute(
                    update(Task)
                    .where(Task.id == job.task_id)
                    .values(status=TaskStatus.pending_approval.value,
                            updated_at=datetime.now(timezone.utc))
                )
                from sqlalchemy import func as sqlfunc
                max_turn = await s.execute(
                    select(sqlfunc.max(TaskTurn.turn_number))
                    .where(TaskTurn.task_id == job.task_id)
                )
                last = max_turn.scalar() or 0
                s.add(TaskTurn(
                    task_id=job.task_id,
                    turn_number=last + 1,
                    role="system",
                    content=(
                        "Auto-continue sentinel detected: job emitted no task signal. "
                        "Task moved to pending_approval — "
                        "approve to close or reply to continue."
                    ),
                ))
                await s.commit()
            await redis.publish(
                "tasks:notify",
                json.dumps({
                    "task_id": str(job.task_id),
                    "type": "approval_request",
                    "text": summary,
                }),
            )
        else:
            # Genuine multi-phase task: phase complete, auto-continue to next phase.
            logger.info("auto-continuing task to next phase",
                        task_id=str(job.task_id)[:8], job_id=str(job.id)[:8])

            continuation_kind = job.resolved_skill or job.kind or "task"
            continuation_desc = _SENTINEL

            child = await enqueue_job(
                continuation_desc,
                kind=continuation_kind,
                payload=job.payload,
                project_id=job.project_id,
                created_by=f"auto-continue:{str(job.id)[:8]}",
            )
            async with session_scope() as s:
                await s.execute(
                    update(Job).where(Job.id == child.id).values(
                        task_id=job.task_id)
                )
                # Record a system turn noting the auto-continue
                from sqlalchemy import func as sqlfunc
                max_turn = await s.execute(
                    select(sqlfunc.max(TaskTurn.turn_number))
                    .where(TaskTurn.task_id == job.task_id)
                )
                last = max_turn.scalar() or 0
                s.add(TaskTurn(
                    task_id=job.task_id,
                    turn_number=last + 1,
                    role="system",
                    content=f"Phase complete. Auto-continuing to next phase (job {str(child.id)[:8]}).",
                ))
                await s.commit()

            # Notify user that it's continuing (informational, not blocking)
            await redis.publish(
                "tasks:notify",
                json.dumps({
                    "task_id": str(job.task_id),
                    "type": "progress",
                    "text": f"Phase complete. Auto-continuing... (job {str(child.id)[:8]})",
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

    # Reconcile jobs stranded in 'running' by a previous process that died
    # mid-job. Must run before the job loop starts consuming the queue.
    try:
        n = await reconcile_orphaned_jobs()
        if n:
            logger.warning("startup: failed orphaned running jobs", count=n)
    except Exception:
        logger.exception("orphaned-job reconciliation failed (non-fatal)")

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
