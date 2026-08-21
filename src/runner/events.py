"""
Event-triggered rules engine. Fourth async task in the runner process.

Polls every 60 seconds and evaluates two rules:
1. Skill failed >= 2 times in 10 minutes → enqueue self-diagnose
2. Project unhealthy > 20 minutes → enqueue self-diagnose

Deduplication: skip if a self-diagnose job for the same target was already
enqueued in the dedup window.

Circuit breaker (2026-07-30 incident): when >= BREAKER_FAILURE_THRESHOLD
recent failures share one normalized error signature, the substrate itself is
broken — per-rule spawning would feed the failure loop (that night ~17
self-diagnose jobs were event-spawned while self-diagnose itself was broken:
"'Server' object has no attribute 'list_tools'"). The loop then sets
KEY_EVENTS_BREAKER (TTL 30 min), enqueues exactly ONE self-diagnose naming
the signature, and skips all event-trigger spawning (skill-failure,
project-health, correlated) — but not the idle-queue review check — while
the key exists.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func

from src.db import KEY_EVENTS_BREAKER, TTL_EVENTS_BREAKER, async_session, redis
from src.gateway.jobs import enqueue_job
from src.models import Job, JobStatus, Project

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 60
SKILL_FAILURE_WINDOW_MINUTES = 10
SKILL_FAILURE_THRESHOLD = 2
PROJECT_UNHEALTHY_MINUTES = 20
REVIEW_COOLDOWN_HOURS = 24
MULTI_SKILL_CORRELATION_WINDOW_MINUTES = 5
MULTI_SKILL_CORRELATION_THRESHOLD = 3
BREAKER_WINDOW_MINUTES = 10
BREAKER_FAILURE_THRESHOLD = 5
BREAKER_SIGNATURE_LEN = 80


def _error_signature(error_message: str | None, max_len: int = BREAKER_SIGNATURE_LEN) -> str:
    """Normalize an error message into a grouping signature: whitespace
    collapsed to single spaces, truncated to max_len chars. None or blank
    messages group as "unknown". Pure function."""
    if error_message is None:
        return "unknown"
    collapsed = " ".join(str(error_message).split())
    if not collapsed:
        return "unknown"
    return collapsed[:max_len]


def should_trip_breaker(
    recent_failures: list[dict],
    threshold: int = BREAKER_FAILURE_THRESHOLD,
) -> str | None:
    """
    Pure function: given recent failed jobs, return the shared error signature
    that should trip the circuit breaker, or None.

    recent_failures: [{"error_message": str | None, "created_at": datetime}, ...]
    (the caller bounds the time window; created_at is not re-filtered here).

    Failures are grouped by normalized signature (`_error_signature`). If any
    signature's count >= threshold, that signature is returned — the largest
    cluster wins; ties break to the lexicographically smallest signature so
    the result is deterministic.
    """
    counts: dict[str, int] = {}
    for f in recent_failures:
        sig = _error_signature(f.get("error_message"))
        counts[sig] = counts.get(sig, 0) + 1
    tripping = [s for s, c in counts.items() if c >= threshold]
    if not tripping:
        return None
    return sorted(tripping, key=lambda s: (-counts[s], s))[0]


async def _check_circuit_breaker() -> bool:
    """Trip or observe the mass-failure circuit breaker. Returns True when
    event-trigger spawning must be skipped this cycle (breaker key already
    present, or just tripped). Caller wraps this non-fatally — a crash here
    must never kill the event loop."""
    if await redis.exists(KEY_EVENTS_BREAKER):
        # One info line per cycle at most while the breaker is engaged.
        logger.info("circuit breaker active — event-trigger spawning paused this cycle")
        return True

    window = datetime.now(timezone.utc) - timedelta(minutes=BREAKER_WINDOW_MINUTES)
    async with async_session() as s:
        result = await s.execute(
            select(Job.error_message, Job.created_at)
            .where(Job.status == JobStatus.failed.value)
            .where(Job.created_at >= window)
        )
        failures = [
            {"error_message": row[0], "created_at": row[1]}
            for row in result.fetchall()
        ]

    signature = should_trip_breaker(failures)
    if signature is None:
        return False

    count = sum(
        1 for f in failures if _error_signature(f.get("error_message")) == signature
    )
    # NX guards the exactly-one enqueue against a set that sneaked in between
    # the exists() check above and here.
    newly_set = await redis.set(
        KEY_EVENTS_BREAKER, signature, ex=TTL_EVENTS_BREAKER, nx=True
    )
    if not newly_set:
        return True
    logger.error(
        "circuit breaker TRIPPED: %d failures in the last %d min share signature %r "
        "— event-trigger spawning paused for %d min",
        count, BREAKER_WINDOW_MINUTES, signature, TTL_EVENTS_BREAKER // 60,
    )
    await enqueue_job(
        f"CIRCUIT BREAKER tripped: {count} failed jobs in the last "
        f"{BREAKER_WINDOW_MINUTES} minutes share the error signature "
        f"'{signature}'. Event-trigger spawning is paused for "
        f"{TTL_EVENTS_BREAKER // 60} minutes. Diagnose the shared root cause "
        f"instead of the individual failures.",
        kind="self-diagnose",
        payload={"target_kind": "circuit-breaker", "target_id": signature},
        created_by="event-trigger:circuit-breaker",
    )
    return True


def _should_trigger_skill_diagnose(
    failures: list[dict],
    existing_diagnoses: list[dict],
    window_minutes: int = SKILL_FAILURE_WINDOW_MINUTES,
    threshold: int = SKILL_FAILURE_THRESHOLD,
) -> list[str]:
    """
    Pure function: given recent failures and existing diagnose jobs,
    return skill names that should trigger a self-diagnose.

    failures: [{"resolved_skill": str, "created_at": datetime}, ...]
    existing_diagnoses: [{"description": str, "created_at": datetime}, ...]
    """
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)

    # Count failures per skill in the window
    skill_counts: dict[str, int] = {}
    for f in failures:
        skill = f.get("resolved_skill")
        created = f.get("created_at")
        if skill and created and created >= cutoff:
            skill_counts[skill] = skill_counts.get(skill, 0) + 1

    # Filter out skills that already have a recent diagnose job
    diagnosed_skills: set[str] = set()
    for d in existing_diagnoses:
        desc = d.get("description", "")
        created = d.get("created_at")
        if created and created >= cutoff:
            # Extract skill name from description like "Self-diagnose: skill '<name>' ..."
            for skill in skill_counts:
                if skill in desc:
                    diagnosed_skills.add(skill)

    return [
        skill for skill, count in skill_counts.items()
        if count >= threshold and skill not in diagnosed_skills
    ]


def _should_trigger_project_diagnose(
    projects: list[dict],
    existing_diagnoses: list[dict],
    unhealthy_minutes: int = PROJECT_UNHEALTHY_MINUTES,
) -> list[str]:
    """
    Pure function: given project health data and existing diagnose jobs,
    return project slugs that should trigger a self-diagnose.

    projects: [{"slug": str, "type": str, "last_healthy_at": datetime | None}, ...]
    existing_diagnoses: [{"description": str, "created_at": datetime}, ...]
    """
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=unhealthy_minutes)
    dedup_cutoff = datetime.now(timezone.utc) - timedelta(minutes=unhealthy_minutes)

    unhealthy: list[str] = []
    for p in projects:
        if p.get("type") == "static":
            continue  # static projects have no healthcheck
        last = p.get("last_healthy_at")
        if last is None:
            continue  # never been healthy — skip (new project, not a failure)
        if last < cutoff:
            unhealthy.append(p["slug"])

    # Filter out already-diagnosed
    diagnosed_slugs: set[str] = set()
    for d in existing_diagnoses:
        desc = d.get("description", "")
        created = d.get("created_at")
        if created and created >= dedup_cutoff:
            for slug in unhealthy:
                if slug in desc:
                    diagnosed_slugs.add(slug)

    return [s for s in unhealthy if s not in diagnosed_slugs]


async def _check_skill_failures() -> None:
    """Query DB for recent skill failures and enqueue self-diagnose if needed."""
    window = datetime.now(timezone.utc) - timedelta(minutes=SKILL_FAILURE_WINDOW_MINUTES)

    async with async_session() as s:
        # Recent failures
        result = await s.execute(
            select(Job.resolved_skill, Job.created_at)
            .where(Job.status == JobStatus.failed.value)
            .where(Job.created_at >= window)
            .where(Job.resolved_skill.isnot(None))
        )
        failures = [
            {"resolved_skill": row[0], "created_at": row[1]}
            for row in result.fetchall()
        ]

        # Recent self-diagnose jobs (for dedup).
        # Filter by Job.kind — set at INSERT time; Job.resolved_skill is NULL
        # while queued and would let 60-s cycles re-spawn duplicates for the
        # same target until the first one starts running (2026-08-21 incident:
        # six duplicate diagnoses for baseball-bingo + atlas).
        result = await s.execute(
            select(Job.description, Job.created_at)
            .where(Job.kind == "self-diagnose")
            .where(Job.created_at >= window)
        )
        existing = [
            {"description": row[0], "created_at": row[1]}
            for row in result.fetchall()
        ]

    skills = _should_trigger_skill_diagnose(failures, existing)
    if not skills:
        return

    # Multi-skill correlation: if 3+ different skills failed in a tight
    # window, likely a shared infrastructure issue. Enqueue one combined
    # diagnosis instead of N separate ones.
    corr_cutoff = datetime.now(timezone.utc) - timedelta(
        minutes=MULTI_SKILL_CORRELATION_WINDOW_MINUTES,
    )
    recent_skill_set = {
        f.get("resolved_skill")
        for f in failures
        if f.get("created_at") and f["created_at"] >= corr_cutoff
        and f.get("resolved_skill")
    }

    if len(recent_skill_set) >= MULTI_SKILL_CORRELATION_THRESHOLD:
        skill_list = sorted(recent_skill_set)
        desc = (
            f"Self-diagnose: {len(skill_list)} skills failed within "
            f"{MULTI_SKILL_CORRELATION_WINDOW_MINUTES} minutes "
            f"({', '.join(skill_list)}). Likely shared infrastructure issue. "
            f"Investigate root cause."
        )
        await enqueue_job(
            desc,
            kind="self-diagnose",
            payload={
                "target_kind": "multi-skill",
                "multi_skill_failures": skill_list,
            },
            created_by="event-trigger:correlated",
        )
        logger.warning(
            "event-triggered correlated self-diagnose for skills %s", skill_list
        )
        return  # skip individual diagnoses

    for skill in skills:
        desc = (
            f"Self-diagnose: skill '{skill}' failed {SKILL_FAILURE_THRESHOLD}+ times "
            f"in the last {SKILL_FAILURE_WINDOW_MINUTES} minutes. "
            f"Investigate root cause and apply fix if safe."
        )
        await enqueue_job(
            desc,
            kind="self-diagnose",
            payload={"target_kind": "skill", "target_id": skill},
            created_by="event-trigger",
        )
        logger.warning("event-triggered self-diagnose for skill %s", skill)


async def _check_project_health() -> None:
    """Query DB for unhealthy projects and enqueue self-diagnose if needed."""
    dedup_window = datetime.now(timezone.utc) - timedelta(minutes=PROJECT_UNHEALTHY_MINUTES)

    async with async_session() as s:
        result = await s.execute(
            select(Project.slug, Project.type, Project.last_healthy_at)
        )
        projects = [
            {"slug": row[0], "type": row[1], "last_healthy_at": row[2]}
            for row in result.fetchall()
        ]

        # Dedup by Job.kind — set at INSERT time; Job.resolved_skill is NULL
        # while queued (see _check_skill_failures for the same rationale).
        result = await s.execute(
            select(Job.description, Job.created_at)
            .where(Job.kind == "self-diagnose")
            .where(Job.created_at >= dedup_window)
        )
        existing = [
            {"description": row[0], "created_at": row[1]}
            for row in result.fetchall()
        ]

    slugs = _should_trigger_project_diagnose(projects, existing)
    for slug in slugs:
        desc = (
            f"Self-diagnose: project '{slug}' has been unhealthy for "
            f"{PROJECT_UNHEALTHY_MINUTES}+ minutes. "
            f"Investigate and fix if safe."
        )
        await enqueue_job(
            desc,
            kind="self-diagnose",
            payload={"target_kind": "project", "target_id": slug},
            created_by="event-trigger",
        )
        logger.warning("event-triggered self-diagnose for project %s", slug)


def _should_trigger_idle_review(
    queued_or_running: int,
    last_review_at: datetime | None,
    cooldown_hours: int = REVIEW_COOLDOWN_HOURS,
) -> bool:
    """
    Pure function: return True if the queue is idle and review-and-improve
    hasn't run recently enough. Maximizes subscription token usage during
    idle periods.
    """
    if queued_or_running > 0:
        return False
    if last_review_at is None:
        return True  # never run before
    cutoff = datetime.now(timezone.utc) - timedelta(hours=cooldown_hours)
    return last_review_at < cutoff


async def _check_idle_queue_review() -> None:
    """If queue is idle and review-and-improve hasn't run in 24h, enqueue one."""
    async with async_session() as s:
        # Count queued + running jobs (excluding review-and-improve itself)
        result = await s.execute(
            select(func.count())
            .select_from(Job)
            .where(Job.status.in_([JobStatus.queued.value, JobStatus.running.value]))
        )
        active_count = result.scalar() or 0

        # Last review-and-improve completion
        result = await s.execute(
            select(Job.completed_at)
            .where(Job.resolved_skill == "review-and-improve")
            .where(Job.status == JobStatus.completed.value)
            .order_by(Job.completed_at.desc())
            .limit(1)
        )
        row = result.first()
        last_review = row[0] if row else None

    if _should_trigger_idle_review(active_count, last_review):
        await enqueue_job(
            "Idle-queue retrospective: analyze recent job data and propose improvements",
            kind="review-and-improve",
            created_by="event-trigger:idle-queue",
        )
        logger.info("idle-queue review-and-improve enqueued")


async def event_loop(shutdown: asyncio.Event) -> None:
    """
    Fourth async task in the runner. Polls every 60 seconds for conditions
    that should trigger automatic self-diagnose jobs.
    """
    # NB: stdlib logger — %-style only. Structlog-style kwargs here raise
    # TypeError at log time and killed the runner at startup (2026-07-30).
    logger.info("event loop started (poll interval %ss)", POLL_INTERVAL_SECONDS)

    while not shutdown.is_set():
        # Circuit breaker first: when many recent failures share one error
        # signature, spawning more event-trigger jobs feeds the failure loop.
        # A crash here fails OPEN (breaker treated as inactive) — the check
        # must never take the loop down.
        breaker_active = False
        try:
            breaker_active = await _check_circuit_breaker()
        except Exception:
            logger.exception("event loop: circuit breaker check error (non-fatal)")

        if not breaker_active:
            try:
                await _check_skill_failures()
            except Exception:
                logger.exception("event loop: skill failure check error (non-fatal)")

            try:
                await _check_project_health()
            except Exception:
                logger.exception("event loop: project health check error (non-fatal)")

        # Idle-queue review is NOT gated by the breaker: it spawns on an idle
        # queue, not on failures, so it can't amplify a failure storm.
        try:
            await _check_idle_queue_review()
        except Exception:
            logger.exception("event loop: idle queue review check error (non-fatal)")

        try:
            await asyncio.wait_for(shutdown.wait(), timeout=POLL_INTERVAL_SECONDS)
            break  # shutdown signaled
        except asyncio.TimeoutError:
            pass  # poll again
