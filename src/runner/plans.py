"""
Plan orchestration (P2). Turns a `task_plan` audit event (emitted by the
`plan` skill) into a dependency-ordered set of jobs, and drives the deferred
→ queued promotion as dependencies complete.

Plan shape (stored on tasks.plan):

{
  "goal": "one sentence",
  "acceptance_criteria": ["observable check", ...],
  "subtasks": [
    {"id": "s1", "kind": "app-patch", "description": "...",
     "project_slug": "bingo",          # optional
     "depends_on": []},                 # local ids
    {"id": "s2", "kind": "app-patch", "description": "...",
     "depends_on": ["s1"]}
  ],
  "verification": "how to verify overall"
}

Jobs carry plan bookkeeping in payload:
  plan_subtask: <local id>
  depends_on:   [<job uuid str>, ...]   (resolved from local ids at spawn)

Deferred jobs are Job rows with status="deferred" and NO Redis queue entry;
`promote_deferred_for(job)` queues them once every dependency has completed
(a dependency also counts as satisfied when a completed escalation retry of
it exists). `fail_dependents_of(job)` cascades failures so a broken foundation
never silently strands its dependents.
"""

from __future__ import annotations

import logging
import uuid as uuid_mod
from typing import Any

from sqlalchemy import select, update

from src import audit_log
from src.config import settings
from src.db import QUEUE_JOBS, async_session, redis, session_scope
from src.models import Job, JobStatus

logger = logging.getLogger(__name__)

MAX_SUBTASKS = 12


# ── Pure helpers (unit-tested) ──────────────────────────────────────────────


def validate_plan(plan: Any, known_kinds: set[str] | None = None) -> list[str]:
    """Return a list of problems (empty = valid). Pure function."""
    errors: list[str] = []
    if not isinstance(plan, dict):
        return ["plan must be a JSON object"]
    if not str(plan.get("goal", "")).strip():
        errors.append("plan.goal is required")
    criteria = plan.get("acceptance_criteria")
    if not isinstance(criteria, list) or not criteria:
        errors.append("plan.acceptance_criteria must be a non-empty list")
    subtasks = plan.get("subtasks")
    if not isinstance(subtasks, list) or not subtasks:
        return errors + ["plan.subtasks must be a non-empty list"]
    if len(subtasks) > MAX_SUBTASKS:
        errors.append(f"too many subtasks ({len(subtasks)} > {MAX_SUBTASKS})")

    ids: set[str] = set()
    for i, st in enumerate(subtasks):
        if not isinstance(st, dict):
            errors.append(f"subtask[{i}] must be an object")
            continue
        sid = str(st.get("id", "")).strip()
        if not sid:
            errors.append(f"subtask[{i}].id is required")
        elif sid in ids:
            errors.append(f"duplicate subtask id {sid!r}")
        ids.add(sid)
        if not str(st.get("description", "")).strip():
            errors.append(f"subtask[{i}].description is required")
        kind = str(st.get("kind", "")).strip()
        if not kind:
            errors.append(f"subtask[{i}].kind is required")
        elif known_kinds is not None and kind not in known_kinds:
            errors.append(f"subtask[{i}].kind {kind!r} is not an installed skill")
        deps = st.get("depends_on", [])
        if not isinstance(deps, list):
            errors.append(f"subtask[{i}].depends_on must be a list")

    for st in subtasks:
        if isinstance(st, dict):
            for dep in st.get("depends_on", []) or []:
                if str(dep) not in ids:
                    errors.append(f"subtask {st.get('id')!r} depends on unknown id {dep!r}")

    if not errors:
        order = topo_order(subtasks)
        if order is None:
            errors.append("subtask dependency graph has a cycle")
    return errors


def topo_order(subtasks: list[dict]) -> list[str] | None:
    """Kahn's algorithm over local subtask ids. Returns None on cycle. Pure."""
    ids = [str(st["id"]) for st in subtasks]
    deps: dict[str, set[str]] = {
        str(st["id"]): {str(d) for d in (st.get("depends_on") or [])} for st in subtasks
    }
    order: list[str] = []
    remaining = set(ids)
    while remaining:
        ready = sorted(i for i in remaining if not (deps[i] & remaining))
        if not ready:
            return None  # cycle
        order.extend(ready)
        remaining -= set(ready)
    return order


def deps_satisfied(dep_ids: list[str], completed: set[str], escalation_map: dict[str, str]) -> bool:
    """A dependency is satisfied if it completed, or a completed escalation
    retry of it exists (escalation_map: failed_job_id → completed retry id).
    Pure function."""
    return all(d in completed or d in escalation_map for d in dep_ids)


# ── Spawn ───────────────────────────────────────────────────────────────────


async def spawn_plan_jobs(task_id, plan: dict, created_by: str) -> dict[str, str]:
    """Create one job per subtask. Roots are queued; dependents deferred.
    Returns {local_id: job_uuid_str}. Caller stores plan on the Task."""
    subtasks: list[dict] = plan["subtasks"]
    order = topo_order(subtasks) or [str(st["id"]) for st in subtasks]
    by_id = {str(st["id"]): st for st in subtasks}
    local_to_job: dict[str, str] = {}

    async with session_scope() as s:
        for lid in order:
            st = by_id[lid]
            deps_local = [str(d) for d in (st.get("depends_on") or [])]
            dep_job_ids = [local_to_job[d] for d in deps_local if d in local_to_job]
            payload: dict[str, Any] = {"plan_subtask": lid}
            if st.get("project_slug"):
                payload["project_slug"] = str(st["project_slug"])
            if dep_job_ids:
                payload["depends_on"] = dep_job_ids
            job = Job(
                kind=str(st["kind"]),
                description=str(st["description"]),
                payload=payload,
                status=(JobStatus.deferred.value if dep_job_ids else JobStatus.queued.value),
                created_by=created_by,
                task_id=task_id,
            )
            s.add(job)
            await s.flush()
            local_to_job[lid] = str(job.id)

    # Queue the roots (after commit so the runner can load the rows)
    for lid in order:
        st = by_id[lid]
        if not (st.get("depends_on") or []):
            await redis.rpush(QUEUE_JOBS, local_to_job[lid])

    logger.info("plan spawned %d subtask jobs for task %s",
                len(local_to_job), str(task_id)[:8])
    return local_to_job


# ── Promotion / cascade ─────────────────────────────────────────────────────


async def _task_job_state(task_id) -> tuple[set[str], dict[str, str], list[Job]]:
    """(completed job ids, escalation_map failed→completed-retry, deferred jobs)
    for one task."""
    async with async_session() as s:
        result = await s.execute(select(Job).where(Job.task_id == task_id))
        jobs = list(result.scalars())
    completed = {str(j.id) for j in jobs if j.status == JobStatus.completed.value}
    escalation_map: dict[str, str] = {}
    for j in jobs:
        src = (j.payload or {}).get("escalated_from")
        if src and j.status == JobStatus.completed.value:
            escalation_map[str(src)] = str(j.id)
    deferred = [j for j in jobs if j.status == JobStatus.deferred.value]
    return completed, escalation_map, deferred


async def promote_deferred_for(job: Job) -> int:
    """After `job` completed: queue any deferred sibling whose dependencies
    are now satisfied. Returns number promoted. Never raises."""
    if not job.task_id:
        return 0
    try:
        completed, escalation_map, deferred = await _task_job_state(job.task_id)
        promoted = 0
        for d in deferred:
            deps = [str(x) for x in ((d.payload or {}).get("depends_on") or [])]
            if deps_satisfied(deps, completed, escalation_map):
                async with session_scope() as s:
                    await s.execute(
                        update(Job).where(Job.id == d.id)
                        .where(Job.status == JobStatus.deferred.value)
                        .values(status=JobStatus.queued.value)
                    )
                await redis.rpush(QUEUE_JOBS, str(d.id))
                audit_log.append(str(d.id), "job_promoted",
                                 satisfied_by=str(job.id))
                promoted += 1
        return promoted
    except Exception:
        logger.exception("deferred promotion failed for job %s", str(job.id)[:8])
        return 0


async def fail_dependents_of(job: Job) -> int:
    """After `job` failed terminally (escalations exhausted): fail every
    deferred sibling that transitively depends on it. Returns count."""
    if not job.task_id:
        return 0
    try:
        _, _, deferred = await _task_job_state(job.task_id)
        failed_ids = {str(job.id)}
        changed = True
        to_fail: list[Job] = []
        while changed:
            changed = False
            for d in deferred:
                if d in to_fail:
                    continue
                deps = {str(x) for x in ((d.payload or {}).get("depends_on") or [])}
                if deps & failed_ids:
                    to_fail.append(d)
                    failed_ids.add(str(d.id))
                    changed = True
        for d in to_fail:
            async with session_scope() as s:
                await s.execute(
                    update(Job).where(Job.id == d.id)
                    .where(Job.status == JobStatus.deferred.value)
                    .values(status=JobStatus.failed.value,
                            error_message=f"dependency {str(job.id)[:8]} failed")
                )
            audit_log.append(str(d.id), "job_failed",
                             error=f"dependency {str(job.id)[:8]} failed",
                             error_category="dependency")
        return len(to_fail)
    except Exception:
        logger.exception("dependency cascade failed for job %s", str(job.id)[:8])
        return 0


async def plan_jobs_remaining(task_id, exclude_job_id=None) -> int:
    """Non-terminal jobs still in flight for a task (excluding one job,
    usually the one whose completion we're processing)."""
    async with async_session() as s:
        result = await s.execute(
            select(Job.id, Job.status).where(Job.task_id == task_id)
        )
        rows = result.all()
    active = {JobStatus.queued.value, JobStatus.deferred.value, JobStatus.running.value}
    n = 0
    for jid, status in rows:
        if exclude_job_id is not None and str(jid) == str(exclude_job_id):
            continue
        if status in active:
            n += 1
    return n
