"""
Runner entry point. Async tasks:

1. _job_loop:        BLPOPs jobs, runs each via session.run_session(), respects quota pause.
2. _scheduler_loop:  cron → enqueue new jobs.
3. _cancel_listener: subscribes to jobs:cancel, interrupts matching session.

On startup, before the loops begin, reconcile_orphaned_jobs() fails any job left
in 'running' by a previous process that died mid-job (see runner/reconcile.py).

Run: `python -m src.runner.main`
Stop: SIGTERM. In-flight jobs finish within their resolved session timeout
(global default, or the per-job payload override capped at 5400s).

Auth check on startup: refuses to start if ANTHROPIC_API_KEY is set (INV-3) or if
the Agent SDK cannot resolve a Claude Code CLI (bundled inside the SDK package,
with the system install as fallback).
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import signal
import sys
import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from collections.abc import Iterable
from typing import Any

import structlog
from croniter import croniter
from sqlalchemy import select, update

from src import audit_log
from src.config import settings
from src.db import (
    CHANNEL_JOB_CANCEL,
    KEY_RUNNER_HEARTBEAT,
    KEY_SCHEDULE_GAP_NOTIFIED_PREFIX,
    QUEUE_JOBS,
    TTL_RUNNER_HEARTBEAT,
    TTL_SCHEDULE_GAP_NOTIFIED,
    async_session,
    redis,
    session_scope,
)
from src.gateway.jobs import enqueue_job
from src.models import Job, JobStatus, Project, Schedule
from src.notify.outbox import build_job_notice, build_ops_notice, build_task_notice, enqueue_notice
from src.registry import models as models_registry
from src.registry.manifest import Manifest, coerce_env_names
from src.registry.skills import load as load_skill
from src.runner import router
from src.runner.events import event_loop
from src.runner.learning import maybe_extract_and_enqueue as maybe_extract_learning
from src.runner.reconcile import reconcile_orphaned_jobs, requeue_stranded_queued
from src.runner.review import (
    MAX_DIFF_CHARS,
    ReviewOutcome,
    get_git_diff,
    head_commit_epoch,
    is_stale_head,
    run_code_review,
)
from src.runner import delivery, quota, session as session_mod, writeback
from src.runner.result_capture import terminal_reason_for_exception, usage_columns

logger = structlog.get_logger()
_shutdown = asyncio.Event()


# ── Startup checks ──────────────────────────────────────────────────────────


def _check_subscription_auth() -> None:
    """Verify subscription-only auth posture and SDK runnability. Exits if broken.

    The Agent SDK spawns the Claude Code CLI bundled inside its own package
    (falling back to a system install), so the check mirrors the SDK's
    resolution instead of shelling out to `claude --version`.
    """
    if os.environ.get("ANTHROPIC_API_KEY"):
        print(
            "ERROR: ANTHROPIC_API_KEY is set in the environment — INV-3: this server "
            "runs on subscription auth only; unset it and restart.\n"
            "  unset ANTHROPIC_API_KEY",
            file=sys.stderr,
        )
        sys.exit(1)

    # E7 (spec §6): vendor and auth keys live in .env and are read by Settings
    # in-process only. Anything in os.environ is inherited by every Claude
    # subprocess and every Bash child of every job — refuse to start rather
    # than leak. FAIL-CLOSED on the whole set: CLAUDE_CODE_OAUTH_TOKEN,
    # ANTHROPIC_AUTH_TOKEN and ANTHROPIC_BASE_URL are exactly what outranks the
    # Keychain /login. Named Anthropic keys, never a blanket ANTHROPIC_* prefix.
    from src.runner.claude_env import vendor_keys_in
    leaked = vendor_keys_in(os.environ)
    if leaked:
        print(
            f"ERROR: forbidden credentials in the runner environment: {', '.join(leaked)} "
            "(INV-3).\n"
            "  Every one of these is inherited by each Claude subprocess and by every Bash\n"
            "  call in every skill; CLAUDE_CODE_OAUTH_TOKEN, ANTHROPIC_AUTH_TOKEN and\n"
            "  ANTHROPIC_BASE_URL also outrank the Keychain /login (spec §6).\n"
            "  Remove them from the launchd plist / shell profile and restart; vendor keys\n"
            "  belong in .env (Settings reads them in-process; pydantic-settings does not\n"
            "  export). If you launched through `pipenv run`, set PIPENV_DONT_LOAD_ENV=1 —\n"
            "  `pipenv run` copies .env into os.environ (scripts/run.sh does this already).",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        import claude_agent_sdk
    except ImportError:
        print(
            "ERROR: claude-agent-sdk is not installed in this environment.\n"
            "  pipenv install",
            file=sys.stderr,
        )
        sys.exit(1)

    bundled = Path(claude_agent_sdk.__file__).parent / "_bundled" / "claude"
    if not bundled.exists() and not shutil.which("claude"):
        print(
            "ERROR: no Claude Code CLI available. The SDK package is missing its "
            "bundled CLI and no system `claude` was found. Reinstall the SDK:\n"
            "  pipenv run pip install --force-reinstall 'claude-agent-sdk>=0.1.63,<0.2'",
            file=sys.stderr,
        )
        sys.exit(1)

    # A logged-in status is harder to probe reliably without invoking a full request,
    # so we defer the real auth check to the first session — which will fail visibly.


# ── E8: alembic history vs disk — the rollback rule as a startup check ────────


def migration_gap(db_revision: str | None, disk_revisions: Iterable[str]) -> str | None:
    """Pure. A message when the DB's current revision has no script on disk.

    None means "fine" OR "cannot tell": a fresh database has no alembic_version
    row, and refusing to boot on that would make an empty DB unbootable. The
    refusal case is narrow — the DB is AHEAD of the scripts on disk, which is
    exactly what a `git revert` of a migration file leaves behind and what
    breaks the next `alembic upgrade head` mid-incident (spec §9 rollback rule;
    `alembic/applied_history.txt` + tests/test_migrations.py are the gate-side
    belt, this is the live-row belt no test can see).
    """
    rev = (db_revision or "").strip()
    if not rev:
        return None
    if rev in set(disk_revisions):
        return None
    return (f"possible_bad_rollback: alembic_version={rev} has no script under "
            f"alembic/versions/. A revert removed a migration file. Restore it; if the "
            f"migration itself must go, run `alembic downgrade -1` on this DB BEFORE "
            f"removing the file (spec §9 rollback rule).")


async def _check_alembic_history() -> None:
    """Refuse to start when the live `alembic_version` is ahead of the scripts
    on disk. Fail-closed on a real gap; tolerant of "cannot tell" (no table,
    no row, an alembic env that will not load). The refusal IS the alarm:
    launchd restarts the runner, `healthcheck-all.sh` sees it down and DMs
    through `notify send`. The `notice(kind=possible_bad_rollback)` ROW is
    Phase 2 — this is the belt that exists in Phase 1."""
    try:
        from alembic.config import Config
        from alembic.script import ScriptDirectory
        from sqlalchemy import text

        cfg = Config(str(settings.server_root / "alembic.ini"))
        cfg.set_main_option("script_location", str(settings.server_root / "alembic"))
        script = ScriptDirectory.from_config(cfg)
        on_disk = {r.revision for r in script.walk_revisions()}
        async with async_session() as s:
            current = (await s.execute(
                text("SELECT version_num FROM alembic_version"))).scalar()
    except Exception as exc:  # noqa: BLE001 — "cannot tell" never blocks a boot
        logger.warning("alembic history check skipped (cannot tell): %s", exc)
        return
    gap = migration_gap(current, on_disk)
    if gap:
        logger.error("%s", gap)
        raise SystemExit(1)


# ── Job loop ────────────────────────────────────────────────────────────────


async def _job_loop() -> None:
    sem = asyncio.Semaphore(settings.max_concurrent_jobs)
    in_flight: set[asyncio.Task] = set()

    while not _shutdown.is_set():
        # Liveness heartbeat + quota check + queue poll are all Redis reads. A
        # transient Redis error here must NOT kill the loop — a dead job loop
        # strands the whole runner while the process stays "up" under launchd.
        # (The heartbeat stops on a real death, so /health still catches that.)
        try:
            # Epoch seconds (bash-comparable for healthcheck-all.sh) with a TTL
            # so a dead runner's key vanishes instead of going stale-but-present.
            await redis.set(KEY_RUNNER_HEARTBEAT, int(time.time()), ex=TTL_RUNNER_HEARTBEAT)
            paused, reset_at, reason = await quota.is_paused()
        except Exception:
            logger.warning("heartbeat/quota check failed — retrying shortly")
            try:
                await asyncio.wait_for(_shutdown.wait(), timeout=2)
                break
            except asyncio.TimeoutError:
                continue

        if paused:
            logger.info("queue paused on quota", reset_at=reset_at.isoformat(), reason=reason[:80])
            try:
                await asyncio.wait_for(_shutdown.wait(), timeout=30)
                break
            except asyncio.TimeoutError:
                continue

        # Acquire a concurrency slot BEFORE consuming from Redis
        # (2026-08-31, EVALUATION_2026-08-30 F2.2): a popped id exists only in
        # this process's memory. The old order BLPOP'd eagerly and parked ids
        # on semaphore waiters, so a crash lost every waiting id — rows stayed
        # 'queued' in Postgres with no Redis entry, invisible forever.
        # (requeue_stranded_queued() heals any pre-existing strandings at
        # startup; this ordering stops creating new ones.)
        try:
            await asyncio.wait_for(sem.acquire(), timeout=2)
        except asyncio.TimeoutError:
            in_flight = {t for t in in_flight if not t.done()}
            continue

        try:
            popped = await redis.blpop([QUEUE_JOBS], timeout=2)
        except Exception:
            sem.release()
            logger.warning("queue poll failed — retrying shortly")
            try:
                await asyncio.wait_for(_shutdown.wait(), timeout=2)
                break
            except asyncio.TimeoutError:
                continue
        if popped is None:
            sem.release()
            in_flight = {t for t in in_flight if not t.done()}
            continue

        _, job_id_str = popped
        try:
            job_id = uuid.UUID(job_id_str)
        except ValueError:
            sem.release()
            logger.warning("malformed job_id in queue", raw=job_id_str)
            continue

        task = asyncio.create_task(_run_with_held_slot(sem, job_id))
        in_flight.add(task)
        task.add_done_callback(in_flight.discard)

    if in_flight:
        logger.info("draining in-flight jobs", count=len(in_flight))
        await asyncio.gather(*in_flight, return_exceptions=True)

    # Held-lane requeues (T6) sleep without a slot; cancel them so each id
    # is RPUSHed NOW instead of sitting as a queued row with no Redis entry
    # until the next startup's requeue_stranded_queued().
    pending_holds = list(_held_requeues)
    if pending_holds:
        for t in pending_holds:
            t.cancel()
        await asyncio.gather(*pending_holds, return_exceptions=True)


async def _run_with_held_slot(sem: asyncio.Semaphore, job_id: uuid.UUID) -> None:
    """Run one job on a semaphore slot the job loop already acquired."""
    try:
        await _process_job(job_id)
    finally:
        sem.release()


# ── Enqueue visibility race (BLPOP can win against the INSERT's commit) ─────
#
# Producers make the id visible in Redis before the Job row is visible to other
# transactions — `_tick_schedules` RPUSHes inside an open transaction, and the
# gateway's commit races the BLPOP by sub-ms. Dropping the popped id on
# not-found strands the row in status='queued' forever (job e38d0028,
# 2026-07-30). So: retry the SELECT over ~2s, then requeue to the TAIL exactly
# once, then drop for good.

# Delay before each SELECT attempt; first is immediate, sleeps total ~2s.
# Per-job session timeout: defined in `session.py` since T4 (the executor
# branch needs the same ceiling and session must not import main); the names
# stay importable from here for existing callers and tests.
SESSION_TIMEOUT_CAP_SECONDS = session_mod.SESSION_TIMEOUT_CAP_SECONDS
resolve_session_timeout = session_mod.resolve_session_timeout


_JOB_FETCH_DELAYS: tuple[float, ...] = (0.0, 0.2, 0.3, 0.5, 1.0)

# Post-session code review (the flag-only second belt) is a nested SDK
# sub-agent; bound it so a hung reviewer can't pin a concurrency slot. Well
# under SESSION_TIMEOUT_SECONDS (the session itself is already done here).
_POST_REVIEW_TIMEOUT_SECONDS = 600

# Ids already given their one requeue. In-memory on purpose: bounded (an id is
# cleared when its row appears or when it is dropped), and a restart merely
# grants a rare id one more retry cycle.
_requeued_missing_ids: set[str] = set()


def note_missing_job(job_id_str: str, requeued_once: set[str]) -> str:
    """Decide-and-record for a popped queue id whose Job row is still missing
    after the `_JOB_FETCH_DELAYS` retries. Deterministic, no I/O.

    First miss → "requeue": the id is recorded and the caller pushes it back to
    the queue TAIL exactly once (covers a race that outlives the in-process
    retries). Repeat miss → "drop": the id is cleared and the caller gives up —
    the row is truly gone (deleted), and without the record a dead id would
    ping-pong through the queue forever.
    """
    if job_id_str in requeued_once:
        requeued_once.discard(job_id_str)
        return "drop"
    requeued_once.add(job_id_str)
    return "requeue"


def queue_wait_ms(created_at: datetime | None, started_at: datetime | None) -> int | None:
    """Pure. Milliseconds a job sat between enqueue and the running flip
    (jobs.queue_wait_ms, migration 008 — Observability Phase 1 A2); None
    when either stamp is missing, never negative (clock skew)."""
    if created_at is None or started_at is None:
        return None
    return max(0, int((started_at - created_at).total_seconds() * 1000))


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


async def _refetch_job(job_id: uuid.UUID, fallback: Job, log) -> Job:
    """Reload the Job row after the session ran, so post-steps see fields the
    session wrote in its OWN db transaction — chiefly `resolved_skill`, which
    the pre-session instance never sees (detached, expire_on_commit=False).
    Every resolved_skill-keyed post-step (review, writeback, learning gate,
    escalation config) depends on this; a stale instance made them silent
    no-ops (post_review: 0/516). Returns the fresh row, or `fallback`
    unchanged on any DB error (logged — never fatal to the post-step flow)."""
    try:
        async with async_session() as s:
            fresh = await s.get(Job, job_id)
        return fresh if fresh is not None else fallback
    except Exception:
        log.exception("post-session job refresh failed — post-steps see the "
                      "stale instance (resolved_skill may be missing)")
        return fallback


def _non_anthropic_lane(job) -> str | None:
    """The job's non-Anthropic provider, or None. Pure read of the
    `resolved_provider` stamp `session.run_session` writes BEFORE the process
    starts, so a timed-out or crashed non-Anthropic job is still
    recognisable afterwards. Used by the timeout and generic failure
    branches of `_process_job` to skip `_maybe_escalate`: the skill's
    `on_failure` target is an Anthropic model, and re-running a Codex job
    there is a vendor switch this slice does not make (T4 note 4; review
    round 1, 2026-10-21). An unstamped job (died before the session's
    stamp) is treated as Anthropic — the pre-T4 behaviour."""
    provider = getattr(job, "resolved_provider", None)
    if not provider or provider == models_registry.DEFAULT_PROVIDER:
        return None
    return provider


# ── Per-provider lane holds (cross-vendor writer slice T6, 2026-10-21) ──────
#
# The global pause (Anthropic, INV-12) stops the loop before BLPOP. A paused
# NON-Anthropic lane must not: its jobs are HELD — never marked running, never
# a process — and requeued at the TAIL (plan §4g) after a bounded delay so the
# loop neither spins on one held id nor pins a concurrency slot on it. The
# delayed RPUSH runs as its own task (no slot); `_job_loop` cancels them on
# shutdown so they push at once, and `requeue_stranded_queued()` heals the
# crash case at the next startup.

#: Longest a held job waits before it is re-offered to the loop (and the
#: lane re-checked). Bounded so a manual `/resume <provider>` is felt soon.
HOLD_RECHECK_SECONDS: float = 30.0

#: In-flight delayed requeues (kept so the tasks are not GC'd; drained on shutdown).
_held_requeues: set[asyncio.Task] = set()

#: job_id → ISO `until` of the pause window last audited as `job_held`, so a
#: job cycling every HOLD_RECHECK_SECONDS writes ONE audit line per window.
_held_audited: dict[str, str] = {}


def preresolve_provider(
    kind: str,
    description: str,
    payload: dict | None,
    *,
    load=None,
    route=None,
) -> str | None:
    """Cheap guess at the job's provider BEFORE the session: the same
    precedence as `session.resolve_model_choice` (`payload.model > skill pin
    > settings.default_model`) with the same kind→skill mapping as
    `session._resolve_skill`, minus the LLM router fallback (not cheap; a
    task-kind job with no rule match pre-resolves to the default). Pure
    given `load`/`route`. Never raises and never refuses: `None` means "could
    not tell" and the job proceeds to the session, which raises the real
    `ProviderRefused` / `SkillResolutionError` with its audit. The enabled
    set is NOT consulted here — this answers WHICH lane, not whether it may
    run. `load`/`route` default to the module-level `load_skill` /
    `router.route` at CALL time (not definition time) so a test's
    `monkeypatch.setattr(main, "load_skill", ...)` is honoured."""
    load = load or load_skill
    route = route or router.route
    payload = payload or {}
    try:
        raw = payload.get("model") or ""
        if not raw:
            skill_name = ""
            if kind == "task":
                skill_name = route(description) or ""
            elif kind:
                skill_name = kind if kind.startswith("_") else kind.replace("_", "-")
            cfg = load(skill_name) if skill_name else None
            raw = (getattr(cfg, "model", "") or "") if cfg is not None else ""
        if not raw:
            raw = settings.default_model
        return models_registry.resolve(raw).provider
    except Exception:
        return None


def hold_delay(until: datetime | None, now: datetime) -> float:
    """Seconds to park a held job: the remaining pause window, capped at
    `HOLD_RECHECK_SECONDS`, never negative. Pure."""
    if until is None:
        return HOLD_RECHECK_SECONDS
    return max(0.0, min(HOLD_RECHECK_SECONDS, (until - now).total_seconds()))


async def _requeue_held(job_id: str, delay: float) -> None:
    try:
        await asyncio.sleep(delay)
    finally:
        # Also on cancellation (shutdown): push now rather than strand.
        try:
            await redis.rpush(QUEUE_JOBS, job_id)
        except Exception:
            logger.exception("held requeue failed — startup reconcile re-pushes it",
                             job_id=job_id)


def _schedule_held_requeue(job_id: str, delay: float) -> asyncio.Task:
    task = asyncio.create_task(_requeue_held(job_id, delay), name=f"held_requeue:{job_id[:8]}")
    _held_requeues.add(task)
    task.add_done_callback(_held_requeues.discard)
    return task


async def _hold_if_provider_paused(job: Job, log) -> bool:
    """True when the job's provider lane is paused and the job was held
    (audited, delayed tail requeue scheduled). The caller must then NOT mark
    it running. The provider is the session's `resolved_provider` stamp from
    an earlier attempt (a job requeued after a Codex `rate_limited`) else
    the cheap pre-resolution. Never raises: a Redis blip fails OPEN to the
    session — if the lane really is red the executor's own 429 re-pauses it."""
    job_id = str(job.id)
    provider = (getattr(job, "resolved_provider", None)
                or preresolve_provider(job.kind, job.description, job.payload))
    if not provider or provider == models_registry.DEFAULT_PROVIDER:
        return False
    try:
        paused, until, reason = await quota.is_provider_paused(provider)
    except Exception:
        log.warning("provider pause check failed — running the job", provider=provider)
        return False
    if not paused:
        _held_audited.pop(job_id, None)
        return False
    until_iso = until.isoformat() if until else ""
    if _held_audited.get(job_id) != until_iso:
        audit_log.append(job_id, "job_held", provider=provider, reason=reason[:200],
                         until=until_iso)
        _held_audited[job_id] = until_iso
        log.info("job held — provider lane paused", provider=provider, until=until_iso,
                 reason=reason[:80])
    _schedule_held_requeue(job_id, hold_delay(until, datetime.now(timezone.utc)))
    return True


async def _process_job(job_id: uuid.UUID) -> None:
    job: Job | None = None
    for delay in _JOB_FETCH_DELAYS:
        if delay:
            await asyncio.sleep(delay)
        # Fresh session per attempt: only a new transaction can see a commit
        # that landed after the previous attempt began.
        async with async_session() as s:
            job = await s.get(Job, job_id)
            if job is not None:
                _requeued_missing_ids.discard(str(job_id))
                if job.status != JobStatus.queued.value:
                    return
                # T6: a paused provider lane holds the job here — before it
                # is ever marked running (no DB write, no slot held, no
                # process); it returns to the queue tail after a bounded
                # delay. Anthropic is never held here (global pause gates
                # the loop before BLPOP).
                if await _hold_if_provider_paused(job, logger.bind(job_id=str(job_id))):
                    return
                job.status = JobStatus.running.value
                job.started_at = datetime.now(timezone.utc)
                # getattr: the ORM row always has created_at; the row
                # stand-ins the _process_job test harnesses build do not.
                job.queue_wait_ms = queue_wait_ms(getattr(job, "created_at", None),
                                                  job.started_at)
                await s.commit()
        if job is not None:
            break

    if job is None:
        # The Redis entry is already consumed — dropping the id here is what
        # stranded queued jobs. One tail-requeue, then give up loudly. The
        # RPUSH is guarded (loop hygiene, 2026-07-28): on a Redis blip the id
        # survives only in this log line, never as an unraised exception.
        action = note_missing_job(str(job_id), _requeued_missing_ids)
        if action == "requeue":
            try:
                await redis.rpush(QUEUE_JOBS, str(job_id))
                logger.warning("job not found after retries — requeued at queue tail once",
                               job_id=str(job_id))
            except Exception:
                logger.exception("job not found and tail-requeue failed — id may be lost",
                                 job_id=str(job_id))
        else:
            logger.error("job not found after retries and one requeue — dropping for good",
                         job_id=str(job_id))
        return

    log = logger.bind(job_id=str(job_id), kind=job.kind)
    log.info("job started")

    # Pre-flight validation: catch misconfigs before wasting a session
    preflight_error = await _preflight_check(job, log)
    if preflight_error:
        audit_log.append(str(job_id), "job_failed", error=preflight_error,
                         error_category="preflight", terminal_reason="error")
        await _finish_job(job_id, JobStatus.failed, error=preflight_error,
                          terminal_reason="error")
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
            timeout=resolve_session_timeout(
                job.payload, settings.session_timeout_seconds),
        )
        await _finish_job(
            job_id, JobStatus.completed, result=result,
            provider=result.get("provider"),
            terminal_reason=result.get("terminal_reason"),
            model_served=result.get("model_served"),
            review_outcome=result.get("review_outcome"),
            # B3: the token/cost subset the session already stamped at its
            # one-site UPDATE, re-written on the terminal transition from
            # the same result dict (same values; both lanes).
            usage=result.get("usage"),
            num_turns=result.get("num_turns"),
            cost_usd_list=result.get("cost_usd_list"),
        )
        log.info("job completed")

        # Refresh the ORM instance before the post-steps: resolved_skill is
        # stamped by the session in a SEPARATE db session, so this pre-session
        # instance never sees it — which made every resolved_skill-keyed
        # post-step a silent no-op (post_review NEVER fired for any job:
        # 0/516 review_outcome, found 2026-08-05).
        job = await _refetch_job(job_id, job, log)

        # Promote deferred dependents whose dependencies are now met — both the
        # task-scoped plan-DAG path and (2026-07-31) task-less depends_on
        # children, so the call runs for EVERY completing job. plans_mod
        # handles both paths and never raises past its per-item isolation.
        try:
            from src.runner import plans as plans_mod
            promoted = await plans_mod.promote_deferred_for(job)
            if promoted:
                log.info("promoted deferred jobs", count=promoted)
        except Exception:
            log.exception("deferred promotion failed (non-fatal)")

        # Code review — runs for skills that opt in via post_review.trigger.
        # Internal skills (leading _, e.g. _evaluate/_writeback) are exempt.
        # Stamps jobs.review_outcome and flags a blocker/error loudly (a
        # second belt for owner attention — the merge gate is the in-session
        # code-review before push; deploy executors carry their own test
        # gates). It never re-statuses the job. Escalated retries are NOT
        # exempt (INV-13: the retry's diff ships with the same authority).
        _is_internal_kind = job.kind == "chat" or job.kind.startswith("_")
        if not _is_internal_kind:
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
        is_internal = _is_internal_kind
        is_internal_skill = (job.resolved_skill or "").startswith("_")
        is_escalation = bool((job.payload or {}).get("escalated_from"))
        if not is_internal and not is_internal_skill and not is_escalation:
            try:
                learning_summary = (result or {}).get("summary", "") if result else ""
                await maybe_extract_learning(str(job_id), learning_summary)
            except Exception:
                log.exception("learning extraction failed (non-fatal)")

        # Task lifecycle — if this job belongs to a task, update task state.
        # (Post-review only flags; it never re-statuses the job, so the task
        # advances normally — a flagged blocker is surfaced via review_outcome
        # + the task DM from _maybe_review, not by halting the DAG.)
        if job.task_id:
            try:
                await _update_task_after_job(job, result)
            except Exception:
                log.exception("task lifecycle update failed (non-fatal)")

    except quota.QuotaExhausted as exc:
        # Pause the queue, requeue this job at the front so it retries after reset
        await quota.pause_queue(exc.reset_at, exc.reason,
                                source=getattr(exc, "source", "estimated"))
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

    except session_mod.SkillResolutionError as exc:
        # Skill contract failure (missing skill for an explicit kind, or
        # corrupt SKILL.md frontmatter) — terminal, NOT escalated. Running the
        # job on registry defaults was the F1.6 silent-host hole; a bigger
        # model would hit the same broken contract (2026-08-31).
        reason = str(exc)
        audit_log.append(str(job_id), "job_failed", error=reason,
                         error_category="skill_contract", terminal_reason="error")
        await _finish_job(job_id, JobStatus.failed, error=f"Skill contract: {reason}",
                          terminal_reason="error")
        log.warning("skill resolution failed — job terminal", reason=reason)
        if job.task_id:
            try:
                await _notify_task(job.task_id, "failed",
                                   text=f"Skill contract failure: {reason}")
            except Exception:
                pass

    except models_registry.ProviderRefused as exc:
        # Unknown `[provider/]model_id`, a provider outside
        # ROUTER_PROVIDERS_ENABLED, or one with no executor — terminal, NOT
        # escalated (a bigger model would re-refuse the same policy). Raised
        # by session._resolve_model before any clone or process exists
        # (T1, 2026-10-21; C12 fail-closed) — or, as the E1 subclass
        # `SettingsOverrideRefused`, after the clone and before the SDK (the
        # session keeps that clone for forensics).
        reason = str(exc)
        audit_log.append(str(job_id), "provider_refused",
                         provider=exc.provider, model=exc.model_id, raw=exc.raw,
                         reason=exc.reason,
                         # E1 (additive): the settings-override subclass names
                         # the key, the file and whether it was an auth key.
                         key=getattr(exc, "key", None), file=getattr(exc, "file", None),
                         auth_key=getattr(exc, "auth_key", None))
        audit_log.append(str(job_id), "job_failed", error=reason,
                         error_category="provider_refused", terminal_reason="provider_refused")
        await _finish_job(job_id, JobStatus.failed, error=f"Provider refused: {reason}",
                          provider=exc.provider, terminal_reason="provider_refused")
        log.warning("provider refused — job terminal", reason=reason)
        if job.task_id:
            try:
                await _notify_task(job.task_id, "failed",
                                   text=f"Provider refused: {reason}")
            except Exception:
                pass

    except session_mod.ReviewBlocked as exc:
        # The pre-push Anthropic review gate (T5, 2026-10-21; INV-21(c))
        # did not LGTM a non-Anthropic job's diff — terminal, NOT escalated
        # (re-running on an Anthropic model would be a vendor switch, and
        # the verdict is about this diff). Nothing was committed, pushed or
        # synced; the clone is kept with the diff for the owner. The
        # verdict is stamped as `review_outcome` so /status and the
        # retrospective read it like a post-review verdict.
        reason = str(exc)
        audit_log.append(str(job_id), "job_failed", error=reason,
                         error_category="review_blocked", terminal_reason="review_blocked")
        refused = getattr(exc, "refused_reason", None)
        if refused == "denied_path" or (refused is None and exc.denied_paths):
            card = (f"Pre-push review gate refused the diff on job {str(job_id)[:8]} "
                    f"({exc.provider}/{exc.model_id}): it touches denied paths "
                    f"({', '.join(exc.denied_paths)}) — refused before any reviewer "
                    f"ran. Nothing was pushed; the clone is kept.")
        elif refused == "unparseable_path":
            card = (f"Pre-push review gate refused the diff on job {str(job_id)[:8]} "
                    f"({exc.provider}/{exc.model_id}): {len(exc.denied_paths)} diff "
                    f"header(s) name a git-quoted path the gate cannot parse, so the "
                    f"deny list could not be applied — refused before any reviewer "
                    f"ran. Nothing was pushed; the clone is kept.")
        elif refused == "diff_too_large":
            card = (f"Pre-push review gate refused the diff on job {str(job_id)[:8]} "
                    f"({exc.provider}/{exc.model_id}): {exc.diff_chars} chars exceeds "
                    f"the reviewer's {MAX_DIFF_CHARS}-char read — a partial "
                    f"review is never an LGTM. Nothing was pushed; the clone is kept "
                    f"(split the work or review it by hand).")
        else:
            card = (f"Pre-push review gate: {exc.verdict} on job {str(job_id)[:8]} "
                    f"({exc.provider}/{exc.model_id}, {exc.findings_n} finding(s)"
                    f"{', reviewer timed out' if exc.timed_out else ''}). "
                    f"Nothing was pushed; the clone is kept — see the audit log's "
                    f"code_review_done for the findings.")
        await _finish_job(job_id, JobStatus.failed, error=f"Review blocked: {reason}",
                          provider=exc.provider, terminal_reason="review_blocked",
                          review_outcome=exc.verdict,
                          done_payload={"summary": card})
        log.warning("pre-push review gate blocked — job terminal",
                    provider=exc.provider, verdict=exc.verdict,
                    findings=exc.findings_n)
        if job.task_id:
            try:
                await _notify_task(job.task_id, "failed", text=card)
            except Exception:
                pass

    except session_mod.ExecutorFailed as exc:
        reason = str(exc)
        if exc.terminal_reason == "rate_limited":
            # The vendor throttled THIS lane (T6, 2026-10-21): pause only
            # that provider's key — never `quota:paused_until`, which is the
            # Anthropic/global pause — and requeue at the FRONT like the
            # Anthropic path (INV-12). The next pop finds the lane paused and
            # holds the job to the tail (plan §4g) until the window passes.
            # The stream carries no reset time → settings.quota_pause_minutes.
            # Not failed, not escalated, no task DM (same as QuotaExhausted).
            until = await quota.pause_provider(exc.provider, None, reason)
            await redis.lpush(QUEUE_JOBS, str(job_id))
            async with session_scope() as s:
                await s.execute(
                    update(Job).where(Job.id == job_id).values(
                        status=JobStatus.queued.value,
                        error_message=(f"queued for {exc.provider} quota reset "
                                       f"({reason[:100]})"),
                    )
                )
            audit_log.append(str(job_id), "job_requeued_for_quota", reason=reason[:200],
                             provider=exc.provider, until=until.isoformat())
            log.warning("executor rate limited — provider lane paused, job requeued",
                        provider=exc.provider, until=until.isoformat())
            return

        # Any other non-`ok` end (auth_expired, api_error, timeout,
        # interrupted) — terminal, NOT escalated: the skill's escalation
        # target is an Anthropic model, and silently re-running the job on
        # another vendor is a routing decision this slice does not make
        # (T4, 2026-10-21). The executor already audited `executor_error`;
        # the clone is kept like any failed job.
        audit_log.append(str(job_id), "job_failed", error=reason,
                         error_category=exc.terminal_reason, terminal_reason=exc.terminal_reason)
        await _finish_job(job_id, JobStatus.failed, error=f"Executor failed: {reason}",
                          provider=exc.provider, terminal_reason=exc.terminal_reason,
                          model_served=exc.model_served)
        log.warning("executor failed — job terminal", provider=exc.provider,
                    terminal_reason=exc.terminal_reason, reason=reason)
        if job.task_id:
            try:
                await _notify_task(job.task_id, "failed",
                                   text=f"Executor failed: {reason}")
            except Exception:
                pass

    except delivery.DeployRefused as exc:
        # Delivery-contract violation — terminal, NOT escalated (retrying a
        # policy refusal would just re-violate it).
        reason = str(exc)
        audit_log.append(str(job_id), "job_failed", error=reason,
                         error_category="deploy_refused", terminal_reason="error")
        await _finish_job(job_id, JobStatus.failed, error=f"Deploy refused: {reason}",
                          terminal_reason="error")
        log.warning("deploy refused by delivery contract", reason=reason)
        if job.task_id:
            try:
                await _notify_task(job.task_id, "failed",
                                   text=f"Deploy refused by policy: {reason}")
            except Exception:
                pass

    except delivery.DeployNeedsApproval as exc:
        # autonomy: human-approval + an autonomous trigger. There is no
        # deploy-resume path (the telegram Approve button completes a TASK, it
        # does not re-enqueue a deploy job), so DO NOT park in awaiting_user —
        # that would hang forever. Fail terminally with an actionable nudge; a
        # human re-trigger ("redeploy <slug>") is a human trigger → allowed.
        reason = str(exc)
        slug = (job.payload or {}).get("project_slug") or "<slug>"
        guidance = (f"{reason}. This deploy needs you to trigger it — "
                    f"reply `redeploy {slug}` to run it yourself.")
        audit_log.append(str(job_id), "job_failed", error=guidance,
                         error_category="deploy_needs_approval", terminal_reason="error")
        await _finish_job(job_id, JobStatus.failed, error=guidance,
                          terminal_reason="error")
        log.info("auto-deploy declined (human-approval, autonomous trigger)", reason=reason)
        if job.task_id:
            try:
                await _notify_task(job.task_id, "failed",
                                   text=f"Auto-deploy declined — needs your trigger. {guidance}")
            except Exception:
                pass

    except asyncio.TimeoutError:
        audit_log.append(str(job_id), "job_failed", error="session_timeout",
                         error_category="timeout", terminal_reason="timeout")
        # Refetch BEFORE the terminal stamp: the session stamps
        # `resolved_provider` (and resolved_skill) in its own transaction,
        # and the lane decision below reads it.
        job = await _refetch_job(job_id, job, log)
        if job.status == JobStatus.cancelled.value:
            # Owner cancelled mid-flight (INV-9 keeps the row `cancelled`;
            # _finish_job's WHERE would suppress the stamp anyway). Never
            # escalate it — _maybe_escalate has no cancelled guard and
            # would enqueue a retry the owner just killed (A2, 2026-10-21).
            log.info("job timeout on a cancelled job — not escalated")
            return
        lane = _non_anthropic_lane(job)
        if lane:
            # Main's deadline won over the executor's (its child was killed
            # by the cancellation) — stamp the typed terminal reason the
            # executor would have, and stop: no Anthropic escalation off a
            # non-Anthropic lane (review round 1, 2026-10-21).
            await _finish_job(job_id, JobStatus.failed, error="Session timed out",
                              provider=lane, terminal_reason="timeout")
            audit_log.append(str(job_id), "note",
                             text=f"{lane} lane timed out — terminal, not escalated "
                                  f"(no vendor switch onto Anthropic)")
            log.warning("job timeout — non-Anthropic lane, terminal", provider=lane)
        else:
            await _finish_job(job_id, JobStatus.failed, error="Session timed out",
                              terminal_reason="timeout")
            log.warning("job timeout")

            # Timeouts escalate like any other failure. This branch used to
            # return without _maybe_escalate, making every session timeout a
            # silent dead end system-wide (no retry, no self-diagnose) — found
            # by the atlas-momo-research smoke run 2026-08-07, which timed out
            # and produced no escalation child. Same refetch rationale as the
            # generic branch: the session may have stamped resolved_skill.
            try:
                await _maybe_escalate(job)
            except Exception:
                log.exception("escalation attempt failed (non-fatal)")

    except Exception as exc:
        from src.runner.audit_index import categorize_error
        err_str = str(exc)[:500]
        # B3: the typed reason from the exception class / the category the
        # session wrote into its error text (`unrecognized_model`, the
        # api_retry enforcement categories, `rate_limited`, …). One reason
        # per handler: the audit row and the DB row never disagree.
        # `categorize_error` keeps its own vocabulary; consumers read
        # terminal_reason first, error_category as the fallback.
        reason = terminal_reason_for_exception(exc)
        audit_log.append(str(job_id), "job_failed", error=err_str,
                         error_category=categorize_error(err_str), terminal_reason=reason)
        log.exception("job failed")

        # Refresh the ORM instance here too — the session may have stamped
        # resolved_skill (and resolved_provider) before dying, and
        # _maybe_escalate's level-0 path reads it for the skill-declared
        # escalation config (same detached-instance staleness as the
        # completed branch; without this, level-0 escalation silently
        # jumped to self-diagnose for task-kind jobs).
        job = await _refetch_job(job_id, job, log)
        if job.status == JobStatus.cancelled.value:
            # A /cancel that interrupts the session before its first API
            # call surfaces here; the row is already `cancelled` — see the
            # timeout branch's guard (A2, 2026-10-21).
            log.info("job failed after cancel — not escalated")
            return
        lane = _non_anthropic_lane(job)
        if lane:
            # Anything the ExecutorFailed handler above did not already
            # type (an infrastructure error around the executor) — terminal
            # on the lane it ran on, never escalated onto Anthropic
            # (review round 1, 2026-10-21).
            await _finish_job(job_id, JobStatus.failed, error=err_str,
                              provider=lane, terminal_reason=reason)
            audit_log.append(str(job_id), "note",
                             text=f"{lane} lane failed — terminal, not escalated "
                                  f"(no vendor switch onto Anthropic)")
            log.warning("job failed — non-Anthropic lane, terminal", provider=lane)
        else:
            await _finish_job(job_id, JobStatus.failed, error=err_str,
                              terminal_reason=reason)

            # Escalation: if the skill declares on_failure, enqueue a retry with
            # the escalated model/effort. One level only, guarded by a payload flag.
            try:
                await _maybe_escalate(job)
            except Exception:
                log.exception("escalation attempt failed (non-fatal)")


async def _maybe_review(job: Job, result: dict) -> None:
    """
    Second-belt post-session code review. Stamps `jobs.review_outcome` and,
    on a blocker/error verdict, emits a loud audit event + owner notification.
    It does NOT halt, un-merge, or re-status the job — the code has already
    been committed/pushed by the time this runs.

    Why flag, not gate: code-writing skills run an in-session `code-review`
    subagent BEFORE they push (that is the merge gate), and deploy executors
    carry their own test gates (red = old code keeps serving). This is the
    belt-and-suspenders second opinion — its job is to RECORD a verdict
    (read by /status, the retrospective, and the weekly manager sweeps) and
    to surface a blocker the first gate missed, not to park a job whose work
    is already live. (Parking to awaiting_user here only mis-reported the
    already-sent completion DM and stranded task state — 2026-08-05.)
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

    lane = _non_anthropic_lane(job)
    if lane:
        # Non-Anthropic lanes are reviewed BEFORE anything is pushed (the
        # pre-push gate, T5, 2026-10-21) by the same fixed Anthropic
        # reviewer; its verdict is already stamped as `review_outcome`. A
        # second pass here would grade the same diff twice — and the
        # stale-head guard below would skip it anyway until the gate's
        # commit lands. The gate is the review of record for these lanes.
        audit_log.append(str(job.id), "post_review_skipped",
                         reason="pre_push_gate", provider=lane,
                         verdict=(result or {}).get("review_outcome"))
        return

    # Resolve the cwd the session actually worked in (delivery-aware): for a
    # dev-repo project the code was committed to the dev repo, not the runtime
    # clone — reviewing the clone would find an empty diff and skip the review.
    cwd = await session_mod._resolve_cwd(job, job.resolved_skill)

    # Wrong-diff guard: a workspace job's canonical ff-sync can fail
    # (dirty/diverged dev clone — routine in multi-machine dev), or the
    # session may have committed nothing, leaving this checkout's HEAD at an
    # OLDER commit that isn't this job's work. Reviewing HEAD~1 would then
    # grade someone else's commit. If HEAD predates the job's start, skip
    # loudly rather than review the wrong diff.
    started_epoch = job.started_at.timestamp() if job.started_at else None
    if is_stale_head(head_commit_epoch(cwd), started_epoch):
        audit_log.append(str(job.id), "post_review_skipped",
                         reason="stale_head", cwd=str(cwd))
        logger.warning("post-review skipped: checkout HEAD predates the job "
                       "(canonical sync failed or nothing committed)",
                       job_id=str(job.id)[:8], cwd=str(cwd))
        return

    diff = get_git_diff(cwd)
    if not diff:
        audit_log.append(str(job.id), "post_review_skipped",
                         reason="no_diff", cwd=str(cwd))
        logger.debug("no diff for review, skipping", job_id=str(job.id)[:8])
        return

    # Fixed, capable reviewer for everyone — a skill does not get to choose
    # (let alone downgrade) the reviewer that grades its own diffs.
    # Timeout-bounded: post_review is a nested SDK sub-agent and, now that it
    # actually fires (was 0/516), a hung reviewer would otherwise pin this
    # job's concurrency-semaphore slot indefinitely while /health still reads
    # healthy. A timeout is a skip (infra issue, not a code verdict), not a
    # blocker — the flag-only belt never wedges the runner.
    try:
        outcome = await asyncio.wait_for(
            run_code_review(str(job.id), diff, cwd),
            timeout=_POST_REVIEW_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        audit_log.append(str(job.id), "post_review_skipped",
                         reason="timeout", cwd=str(cwd))
        logger.warning("post-review timed out after %ss — skipping (flag-only "
                       "second belt never wedges the runner)",
                       _POST_REVIEW_TIMEOUT_SECONDS, job_id=str(job.id)[:8])
        return

    # Stamp review_outcome on the job (leave status = completed).
    async with session_scope() as s:
        await s.execute(
            update(Job).where(Job.id == job.id).values(
                review_outcome=outcome.value,
            )
        )

    if outcome in (ReviewOutcome.blocker, ReviewOutcome.error):
        # blocker = review found a serious issue; error = review couldn't run.
        # Surface it loudly: audit event (read by the retrospective + manager
        # sweeps), a warning, and a task DM when this job belongs to a task.
        audit_log.append(str(job.id), "post_review_flagged", outcome=outcome.value)
        logger.warning("post-review flagged a %s — job left completed; the "
                       "diff is already pushed, this is the after-the-fact "
                       "second belt", outcome.value, job_id=str(job.id)[:8])
        if job.task_id:
            try:
                # Plain text — the tasks:notify consumer's review_flagged
                # branch adds the ⚠️ prefix (matching every other branch).
                await _notify_task(
                    job.task_id, "review_flagged", job_id=str(job.id),
                    text=(f"Post-session code review flagged a "
                          f"{outcome.value} on job {str(job.id)[:8]} "
                          f"({skill_name}). The change is already pushed — "
                          f"review the diff and the audit log."))
            except Exception:
                logger.exception("review-flag task notify failed for %s",
                                 str(job.id)[:8])


async def _verify_writeback(job: Job, result: dict) -> None:
    """
    After a session completes, check if it modified non-doc files without
    updating any CHANGELOG. If so, enqueue a child `_writeback` job.
    """
    # Resolve the cwd the session ran in (delivery-aware — dev-repo projects
    # commit to the dev repo, not the runtime clone).
    cwd = await session_mod._resolve_cwd(job, job.resolved_skill)

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
            from src.models import TaskStatus
            try:
                from src.runner import plans as plans_mod
                cascaded = await plans_mod.fail_dependents_of(job)
                if cascaded:
                    logger.warning("failed deferred dependents", count=cascaded,
                                   job_id=str(job.id)[:8])
            except Exception:
                logger.exception("dependency cascade failed (non-fatal)")
            # Routed through _set_task_status (updated_at + awaiting_since
            # cleared) so the runner keeps one writer of tasks.status (A2).
            await _set_task_status(job.task_id, TaskStatus.failed.value)
            await _notify_task(
                job.task_id, "failed",
                text=(f"Task failed after 3 escalation attempts. "
                      f"Last error: {(job.error_message or 'unknown')[:300]}. "
                      f"Reply to retry or /clear to abandon."),
            )
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


_AWAITING_STATUSES = ("awaiting_user", "pending_approval")


def awaiting_since_for(status: str, now: datetime) -> datetime | None:
    """Pure. Stamp when a task starts waiting on the owner; clear otherwise
    (tasks.awaiting_since, migration 008 — stuck asks finally have an age)."""
    return now if status in _AWAITING_STATUSES else None


async def _set_task_status(task_id, status: str) -> None:
    """The one writer of tasks.status from the runner: stamps/clears
    `awaiting_since` with the same clock read as `updated_at`. The bot's own
    transitions (thread reply, approve, choice, reopen) do the same inline."""
    from src.models import Task
    now = datetime.now(timezone.utc)
    async with session_scope() as s:
        await s.execute(
            update(Task).where(Task.id == task_id).values(
                status=status, updated_at=now,
                awaiting_since=awaiting_since_for(status, now))
        )


def effective_origin_channel(own: str | None, parent: str | None) -> str | None:
    """Pure. Spec §4.2: dispatch-MCP / escalation / self-diagnose / evaluator /
    writeback children INHERIT the parent's eligibility. A child's own
    `created_by` (`dispatch-mcp`, `event-trigger*`, `escalation:<job8>`)
    derives `origin_channel="system"`, which would silence the completion DM
    of a child the owner launched from Telegram and DM the owner for a child
    of a schedule row — wrong in both directions. An own human channel
    always wins; no parent → unchanged."""
    return parent if (own in (None, "system")) and parent else own


def job_notice_kwargs(job: Any) -> dict[str, Any]:
    """Pure. `build_job_notice(**kwargs)` from a Job row (or any object with
    the same attributes). `status` is left None for the caller; the lane
    label reads the 007 columns (`resolved_provider`/`resolved_model`/
    `model_served`) and `num_turns` (008 — NULL until B3) straight off the
    row."""
    result = job.result if isinstance(job.result, dict) else None
    duration = None
    if job.started_at and job.completed_at:
        duration = max(0.0, (job.completed_at - job.started_at).total_seconds())
    return dict(
        job_id=str(job.id), status=None, kind=job.kind, resolved_skill=job.resolved_skill,
        summary=result.get("summary") if result else None,
        error_message=job.error_message, terminal_reason=job.terminal_reason,
        origin_channel=job.origin_channel, origin_ref=job.origin_ref,
        origin_thread=job.origin_thread, created_by=job.created_by, task_id=job.task_id,
        model_served=job.model_served, resolved_provider=job.resolved_provider,
        resolved_model=job.resolved_model, num_turns=job.num_turns,
        duration_seconds=duration,
    )


async def _enqueue_job_notice(job_id: uuid.UUID, status: str) -> None:
    """Outbox row for a job terminal (DoneCard / FailedCard, spec §4.2). Built
    from the ROW (`error_message`, `terminal_reason`, …), never from the
    `jobs:done` payload. A child (`parent_job_id` set) inherits the parent's
    channel — and with it the parent's `origin_ref`/`origin_thread`, so the
    card lands in the chat that launched the parent (one extra indexed read,
    children only)."""
    async with async_session() as s:
        job = await s.get(Job, job_id)
        if job is None:
            return
        parent = await s.get(Job, job.parent_job_id) if job.parent_job_id else None
    kwargs = job_notice_kwargs(job)
    kwargs["status"] = status
    if parent is not None:
        channel = effective_origin_channel(job.origin_channel, parent.origin_channel)
        if channel != job.origin_channel:
            kwargs.update(origin_channel=channel, origin_ref=parent.origin_ref,
                          origin_thread=parent.origin_thread)
    notice = build_job_notice(**kwargs)
    if notice is not None:
        await enqueue_notice(notice)


async def _task_target(task_id) -> tuple[str | None, str | None]:
    """(chat, thread) for a task card: `origin_ref`/`origin_thread` (008)
    first, the legacy `chat_id`/`thread_message_id` second; (None, None) →
    the owner chat."""
    from src.models import Task
    async with async_session() as s:
        task = await s.get(Task, task_id)
    if task is None:
        return None, None
    target = task.origin_ref or (str(task.chat_id) if task.chat_id else None)
    thread = task.origin_thread or (str(task.thread_message_id) if task.thread_message_id else None)
    return target, thread


async def _notify_task(task_id, notify_type: str, **fields) -> None:
    """The single chokepoint for task lifecycle cards. DUAL-WRITE (D-P1-10):
    the legacy `tasks:notify` publish is unconditional and byte-identical to
    before A5, then a durable outbox row + nudge is written UNCONDITIONALLY
    (the DB read and insert are non-fatal). Which renderer sends is the bot's
    decision (`telegram_bot._task_notifier` vs the outbox listener, A6) —
    nothing under src/runner/ reads the kill switch."""
    await redis.publish("tasks:notify", json.dumps({
        "task_id": str(task_id), "type": notify_type, **fields,
    }))
    if notify_type == "choices" and not fields.get("choices"):
        return      # parity: the legacy renderer skips a choices card with no options
    try:
        target, thread = await _task_target(task_id)
        notice = build_task_notice(
            task_id=str(task_id), notify_type=notify_type,
            text=str(fields.get("text", "") or ""),
            question=fields.get("question"), choices=fields.get("choices"),
            target=target, thread=thread,
        )
        await enqueue_notice(notice)
    except Exception:  # noqa: BLE001 — the legacy card already went out
        logger.exception("task notice enqueue failed (non-fatal)",
                         task_id=str(task_id)[:8], notify_type=notify_type)


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
        await _set_task_status(job.task_id, TaskStatus.awaiting_user.value)
        await _notify_task(job.task_id, "choices",
                           question=choices_event.get("question", "Pick one:"),
                           choices=choices_event.get("options", []))
    elif question:
        await _set_task_status(job.task_id, TaskStatus.awaiting_user.value)
        # Notify user via Redis (Telegram bot listens) + the outbox row
        await _notify_task(job.task_id, "question", text=question)
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
            _now = datetime.now(timezone.utc)
            async with session_scope() as s:
                # Shared session with the TaskTurn insert below, so this
                # stays inline rather than going through _set_task_status;
                # it stamps awaiting_since itself (A2).
                await s.execute(
                    update(Task)
                    .where(Task.id == job.task_id)
                    .values(status=TaskStatus.pending_approval.value,
                            updated_at=_now, awaiting_since=_now)
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
            await _notify_task(job.task_id, "approval_request", text=summary)
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
            await _notify_task(job.task_id, "progress",
                               text=f"Phase complete. Auto-continuing... (job {str(child.id)[:8]})")


def _terminal_values(
    status: JobStatus,
    *,
    result: dict | None,
    error: str | None,
    provider: str | None = None,
    terminal_reason: str | None = None,
    model_served: str | None = None,
    review_outcome: str | None = None,
    usage: dict | None = None,
    num_turns: int | None = None,
    cost_usd_list: Any = None,
) -> dict:
    """The column values a terminal transition writes. Pure.

    The provider columns (migration 007: `resolved_provider`,
    `terminal_reason`, `model_served`) are written only when known, so a
    path that does not know them (timeout, generic failure) leaves what the
    session stamped at start untouched (T4, 2026-10-21). Likewise the 008
    token/cost subset (B3): `usage` (SDK key names, either lane) becomes the
    five token columns through `result_capture.usage_columns`; `num_turns`
    and `cost_usd_list` (→ Decimal for numeric(10,4)) when known.
    """
    values: dict = dict(
        status=status.value,
        result=result,
        error_message=error,
        completed_at=datetime.now(timezone.utc),
    )
    if provider is not None:
        values["resolved_provider"] = provider
    if terminal_reason is not None:
        values["terminal_reason"] = terminal_reason
    if model_served is not None:
        values["model_served"] = model_served
    if review_outcome is not None:
        # The pre-push gate's verdict (T5); the Anthropic post-review
        # stamps this column itself in `_maybe_review`.
        values["review_outcome"] = review_outcome
    if usage is not None:
        values.update(usage_columns(usage))
    if num_turns is not None:
        values["num_turns"] = num_turns
    if cost_usd_list is not None:
        values["cost_usd_list"] = Decimal(str(cost_usd_list))
    return values


async def _finish_job(
    job_id: uuid.UUID,
    status: JobStatus,
    *,
    result: dict | None = None,
    error: str | None = None,
    provider: str | None = None,
    terminal_reason: str | None = None,
    model_served: str | None = None,
    review_outcome: str | None = None,
    done_payload: dict | None = None,
    usage: dict | None = None,
    num_turns: int | None = None,
    cost_usd_list: Any = None,
) -> None:
    """Terminal transition + `jobs:done` publish. `done_payload` overrides
    the published payload (the done DM's text) — used by the review-blocked
    path so the DM names the verdict instead of a bare "failed"."""
    async with session_scope() as s:
        # INV-9: never overwrite a user cancellation. The cancel listener may set
        # `cancelled` in the race window before a session finishes; without this
        # guard the trailing _finish_job(completed) would silently resurrect the
        # job as completed. Other completed→X transitions (e.g. the multi-turn
        # task flow flipping to awaiting_user via task_question) stay allowed —
        # only `cancelled` is protected. (Post-review no longer parks; it
        # flags while the job stays completed — 2026-08-05.)
        result_proxy = await s.execute(
            update(Job)
            .where(Job.id == job_id)
            .where(Job.status != JobStatus.cancelled.value)
            .values(**_terminal_values(
                status, result=result, error=error, provider=provider,
                terminal_reason=terminal_reason, model_served=model_served,
                review_outcome=review_outcome, usage=usage,
                num_turns=num_turns, cost_usd_list=cost_usd_list))
        )
        if result_proxy.rowcount == 0:
            logger.info("finish suppressed — job already in a protected terminal state",
                        job_id=str(job_id)[:8], attempted=status.value)
            return
    if done_payload is not None:
        payload = dict(done_payload)
    else:
        payload = {"summary": (result or {}).get("summary", "")} if result else {}
    await session_mod.publish_done(str(job_id), status.value, payload=payload)

    # Outbox (A5): DoneCard / FailedCard for every eligible terminal —
    # task-less completions, every non-internal failure, scheduled ones
    # included. After publish_done so an INV-9-suppressed finish (returned
    # above) writes no row; built from the ROW, never from done_payload.
    # Unconditional: the kill switch is the bot's (D-P1-10).
    if status in (JobStatus.completed, JobStatus.failed):
        try:
            await _enqueue_job_notice(job_id, status.value)
        except Exception:  # noqa: BLE001 — the legacy publish already went out
            logger.exception("job notice enqueue failed (non-fatal)", job_id=str(job_id)[:8])

    # Incremental audit index update (B2)
    try:
        from src.runner.audit_index import append_to_index
        append_to_index(settings.audit_log_dir, str(job_id))
    except Exception as exc:  # noqa: BLE001
        # non-fatal; nightly rebuild catches anything missed — but log it
        logger.debug("audit index append failed", job_id=str(job_id)[:8], error=str(exc))


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


# ── Provisioning pre-check (D1, 2026-10-21; spec §8.3) ──────────────────────
#
# A due row whose project .env lacks a key the manifest (or the row's own
# job_payload.env_required, D-P1-7) declares cannot succeed: before D1 it ran
# a full session and reported "completed" having produced nothing (spec §8.2:
# 37/37 provisioning_gap runs "successful"). Defer it instead — no Job, the
# clock still advances — write schedule_deferred to the schedule's stream on
# every deferral, and DM once per project per UTC day. FAIL-OPEN on every
# unknown: a pre-check that can silence 41 schedules on a file-read error is
# worse than the waste it prevents. The ONLY thing that defers a row is a
# positively declared name that the canonical .env positively lacks.

# Names a project may never be required to carry in its own .env, because
# this server refuses them everywhere (INV-3 / subscription auth). Verified
# on prod: projects/atlas/manifest.yml declares env_required: [DATABASE_URL,
# ANTHROPIC_API_KEY] and the second is absent from the atlas .env BY DESIGN —
# without this exemption every atlas row would defer on its first tick. A
# LOCAL set on purpose: codex_cli.DENIED_ENV_* denies exactly the broker /
# vendor keys this check must be able to look for.
PROVISIONING_EXEMPT: frozenset[str] = frozenset({
    "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN",
})
PROVISIONING_EXEMPT_PREFIXES: tuple[str, ...] = ("ANTHROPIC_",)


def env_keys_present(env_path: Path) -> set[str]:
    """Pure-ish (one file read). The NAME= keys declared in a .env — blanks,
    `#` comments and `export ` prefixes handled. Values are never read into
    anything, never logged."""
    try:
        text = Path(env_path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set()
    out: set[str] = set()
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name = line.split("=", 1)[0].strip()
        if name.startswith("export "):
            name = name[len("export "):].strip()
        if name:
            out.add(name)
    return out


def provisioning_gap(env_required: list[str] | None, present: set[str], *,
                     exempt: frozenset[str] = PROVISIONING_EXEMPT) -> list[str]:
    """Pure. Sorted required names the .env does not declare, minus the
    exempt set and the ANTHROPIC_ prefix. Empty ⇒ run the row."""
    return sorted({
        name for name in (env_required or [])
        if name and name not in present and name not in exempt
        and not name.startswith(PROVISIONING_EXEMPT_PREFIXES)
    })


def schedule_env_required(sched: Any, manifest: Manifest | None) -> list[str]:
    """Pure. The manifest's `env_required` ∪ the row's
    `job_payload.env_required` (D-P1-7), deduplicated and sorted."""
    names = set(manifest.env_required) if manifest is not None else set()
    payload = getattr(sched, "job_payload", None) or {}
    if isinstance(payload, dict):
        names.update(coerce_env_names(payload.get("env_required")))
    return sorted(n for n in names if n)


async def _resolve_schedule_slug(sched: Any, s: Any) -> str | None:
    """payload.project_slug first, then project_id → Project.slug in the
    open session. None when the row has no project at all."""
    payload = sched.job_payload if isinstance(sched.job_payload, dict) else {}
    slug = payload.get("project_slug")
    if slug:
        return str(slug)
    if sched.project_id is None:
        return None
    project = await s.get(Project, sched.project_id)
    return project.slug if project is not None and project.slug else None


def _project_env_files(slug: str, manifest: Manifest | None) -> list[Path]:
    """The .env file(s) `provision_env_files` copies from — the SAME
    canonical `resolve_delivery_cwd` picks for a non-deploy job (for atlas:
    the dev clone, not the runtime clone)."""
    cwd, _ = delivery.resolve_delivery_cwd(
        settings.projects_dir / slug, manifest.delivery if manifest else None, is_deploy=False,
    )
    files = (manifest.delivery.env_files if manifest else None) or [".env"]
    return [cwd / f for f in files]


async def _schedule_provisioning_gap(
    sched: Any, s: Any, cache: dict[str, tuple[Manifest | None, list[Path], set[str]]],
) -> tuple[list[str], str | None, str]:
    """(missing, slug, env_file label) for a due row. Manifest/.env reads
    are cached per slug within one tick. Any exception → ([], …): the row
    runs."""
    slug: str | None = None
    try:
        slug = await _resolve_schedule_slug(sched, s)
        if not slug:
            return [], None, ""
        if slug not in cache:
            manifest = delivery.load_project_manifest(slug)
            paths = _project_env_files(slug, manifest)
            present: set[str] = set()
            for path in paths:
                present |= env_keys_present(path)
            cache[slug] = (manifest, paths, present)
        manifest, paths, present = cache[slug]
        missing = provisioning_gap(schedule_env_required(sched, manifest), present)
        return missing, slug, ", ".join(str(p) for p in paths)
    except Exception:  # noqa: BLE001 — never let the pre-check stop a schedule
        logger.debug("provisioning pre-check skipped — row runs",
                     schedule=getattr(sched, "name", "?"), exc_info=True)
        return [], slug, ""


async def _notify_schedule_deferral(sched: Any, slug: str, env_file: str,
                                    missing: list[str], now: datetime) -> None:
    """One ops DM per PROJECT per UTC day. The day claim is SET NX only after
    `enqueue_notice` returned an id, so a dropped insert does not burn the
    day. Ops kind → delivered with the outbox switch on or off (D-P1-10)."""
    key = f"{KEY_SCHEDULE_GAP_NOTIFIED_PREFIX}{slug}:{now:%Y-%m-%d}"
    if await redis.exists(key):
        return
    nid = await enqueue_notice(build_ops_notice(
        kind="schedule_deferred", severity="warn",
        text=(f"⏸ {sched.name} deferred — {env_file} lacks {', '.join(missing)}; "
              f"defers until provisioned"),
        subject=f"schedule:{sched.id}",
    ))
    if nid is not None:
        await redis.set(key, "1", nx=True, ex=TTL_SCHEDULE_GAP_NOTIFIED)


async def _tick_schedules() -> None:
    now = datetime.now(timezone.utc)
    gap_cache: dict[str, tuple[Manifest | None, list[Path], set[str]]] = {}
    async with session_scope() as s:
        result = await s.execute(
            select(Schedule).where(
                Schedule.paused.is_(False),
                Schedule.next_run_at <= now,
            )
        )
        due = list(result.scalars())

        for sched in due:
            missing, slug, env_file = await _schedule_provisioning_gap(sched, s, gap_cache)
            if missing:
                # Unconditional once missing is non-empty: advance the clock,
                # build no Job; the record and the DM are each best-effort.
                sched.last_run_at = now
                sched.next_run_at = croniter(sched.cron_expression, now).get_next(
                    datetime
                ).replace(tzinfo=timezone.utc)
                try:
                    audit_log.append_schedule_event(
                        sched.id, "schedule_deferred", schedule=sched.name,
                        reason="provisioning_gap", missing=missing, project=slug,
                        env_file=env_file,
                    )
                except Exception:  # noqa: BLE001
                    logger.warning("schedule_deferred audit append failed", schedule=sched.name)
                try:
                    await _notify_schedule_deferral(sched, slug or "", env_file, missing, now)
                except Exception:  # noqa: BLE001
                    logger.warning("schedule_deferred notice failed", schedule=sched.name)
                logger.warning(
                    "schedule deferred: provisioning gap",
                    schedule=sched.name, project=slug, missing=missing,
                    next_run=sched.next_run_at.isoformat(),
                )
                continue

            job = Job(
                kind=sched.job_kind,
                description=sched.job_description,
                payload=sched.job_payload,
                project_id=sched.project_id,
                schedule_id=sched.id,
                status=JobStatus.queued.value,
                created_by="scheduler",
                origin_channel="scheduler",
                origin_ref=sched.name[:64],
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
            # Per-iteration guard: a malformed payload (uuid.UUID("garbage") →
            # ValueError) or a transient Redis/DB error must NOT permanently kill
            # the listener. Only _job_loop writes the heartbeat, so a dead cancel
            # listener is invisible to /health — INV-8 would fail silently.
            try:
                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=2)
                if msg is None:
                    continue
                job_id = msg.get("data")
                if not job_id:
                    continue
                try:
                    job_uuid = uuid.UUID(job_id)
                except (ValueError, TypeError, AttributeError):
                    logger.warning("cancel: ignoring malformed job_id", raw=str(job_id)[:80])
                    continue
                did = await session_mod.interrupt(job_id)
                if did:
                    # E3 / D-P1-4: the same vocabulary as gateway.jobs.
                    # cancel_job_durable — one `job_cancelled{stage}` shape,
                    # terminal_reason "interrupted" (never a 16th value).
                    audit_log.append(str(job_id), "job_cancelled", stage="running")
                    async with session_scope() as s:
                        await s.execute(
                            update(Job).where(Job.id == job_uuid).values(
                                status=JobStatus.cancelled.value,
                                terminal_reason="interrupted",
                                error_message="cancelled by user (running)",
                                completed_at=datetime.now(timezone.utc),
                            )
                        )
                    logger.info("interrupted session", job_id=job_id)
            except Exception:
                logger.exception("cancel listener iteration failed (continuing)")
                await asyncio.sleep(0.5)
    finally:
        await pubsub.unsubscribe(CHANNEL_JOB_CANCEL)


# ── Main ────────────────────────────────────────────────────────────────────


def _install_signal_handlers(loop: asyncio.AbstractEventLoop) -> None:
    def _h() -> None:
        logger.info("shutdown signal received")
        _shutdown.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _h)


async def main() -> int:
    import logging
    logging.basicConfig(level=logging.INFO)
    _check_subscription_auth()
    # E8: credentials first, then the vendor-key assertion (inside the check
    # above), then migration history — cheapest and most fatal first.
    await _check_alembic_history()
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

    # Re-push 'queued' rows whose Redis entry died with the previous process
    # (BLPOP'd into an in-process waiter, never run). Idempotent; must run
    # before the job loop starts consuming (EVALUATION_2026-08-30 F2.3).
    try:
        n = await requeue_stranded_queued()
        if n:
            logger.warning("startup: re-queued stranded queued jobs", count=n)
    except Exception:
        logger.exception("stranded-queued reconciliation failed (non-fatal)")

    tasks = [
        asyncio.create_task(_job_loop(), name="job_loop"),
        asyncio.create_task(_scheduler_loop(), name="scheduler_loop"),
        asyncio.create_task(_cancel_listener(), name="cancel_listener"),
        asyncio.create_task(event_loop(_shutdown), name="event_loop"),
    ]
    # Supervise: if ANY subsystem exits on its own (not via _shutdown), bring the
    # whole process down so launchd KeepAlive restarts a clean one. A limping
    # runner with a dead scheduler or cancel-listener is worse (and invisible —
    # only _job_loop heartbeats) than a restart.
    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    # Retrieve every completed task's exception (both paths) so asyncio doesn't
    # warn "exception never retrieved"; a subsystem that exited while _shutdown
    # was still unset means it CRASHED.
    crashed = not _shutdown.is_set()
    for t in done:
        exc = t.exception() if not t.cancelled() else None
        if crashed:
            logger.error("runner subsystem exited unexpectedly — shutting down for restart",
                         task=t.get_name(), error=str(exc) if exc else "returned cleanly")
    if crashed:
        # Crash path: the runner is already broken. Force the survivors down for a
        # clean launchd restart (in-flight jobs are recovered by reconcile).
        _shutdown.set()
        for t in pending:
            t.cancel()
    # Graceful path (SIGTERM set _shutdown): do NOT cancel — `_job_loop` is
    # draining its in-flight jobs (`gather(*in_flight)`); cancelling it here
    # would abort those already-running sessions. Let the survivors finish.
    await asyncio.gather(*pending, return_exceptions=True)
    logger.info("runner stopped")
    # Crash path must exit NON-ZERO: launchd's KeepAlive {SuccessfulExit: false}
    # only resurrects failed exits, so a clean exit here leaves the runner down
    # permanently (2026-07-30 incident: latent event_loop startup crash →
    # supervised shutdown → exit 0 → launchd never restarted it).
    return 1 if crashed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
