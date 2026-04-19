"""
Rollup queries for the auto-tuning retrospective.

Used by the review-and-improve skill to analyze job performance and propose
tuning changes. Can also be used by the dashboard for a "performance" view.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import case, cast, func, select, Integer
from src.db import async_session
from src.config import settings
from src.models import Job, JobStatus

logger = logging.getLogger(__name__)


@dataclass
class SkillPerformance:
    skill: str
    model: str | None
    effort: str | None
    count: int
    success_rate: float
    avg_latency_s: float | None
    avg_rating: float | None
    review_lgtm_rate: float | None


async def skill_performance(
    since: datetime | None = None,
    until: datetime | None = None,
) -> list[SkillPerformance]:
    """Rollup of jobs by (resolved_skill, resolved_model, resolved_effort)."""
    since = since or (datetime.now(timezone.utc) - timedelta(days=30))
    until = until or datetime.now(timezone.utc)

    async with async_session() as s:
        completed_case = case(
            (Job.status == JobStatus.completed.value, 1),
            else_=0,
        )
        lgtm_case = case(
            (Job.review_outcome == "LGTM", 1),
            else_=0,
        )
        reviewed_case = case(
            (Job.review_outcome.isnot(None), 1),
            else_=0,
        )

        q = (
            select(
                Job.resolved_skill,
                Job.resolved_model,
                Job.resolved_effort,
                func.count(Job.id).label("total"),
                func.sum(cast(completed_case, Integer)).label("completed"),
                func.avg(
                    func.extract("epoch", Job.completed_at - Job.started_at)
                ).label("avg_latency"),
                func.avg(Job.user_rating).label("avg_rating"),
                func.sum(cast(lgtm_case, Integer)).label("lgtm_count"),
                func.sum(cast(reviewed_case, Integer)).label("reviewed_count"),
            )
            .where(Job.created_at >= since, Job.created_at <= until)
            .where(Job.resolved_skill.isnot(None))
            .group_by(Job.resolved_skill, Job.resolved_model, Job.resolved_effort)
        )
        result = await s.execute(q)
        rows = result.all()

    out: list[SkillPerformance] = []
    for r in rows:
        total = r.total or 1
        reviewed = r.reviewed_count or 0
        out.append(SkillPerformance(
            skill=r.resolved_skill,
            model=r.resolved_model,
            effort=r.resolved_effort,
            count=total,
            success_rate=(r.completed or 0) / total,
            avg_latency_s=float(r.avg_latency) if r.avg_latency else None,
            avg_rating=float(r.avg_rating) if r.avg_rating else None,
            review_lgtm_rate=(r.lgtm_count / reviewed) if reviewed > 0 else None,
        ))
    return out


async def writeback_frequency(
    since: datetime | None = None,
) -> list[dict[str, Any]]:
    """Count _writeback triggers per parent skill in the period."""
    since = since or (datetime.now(timezone.utc) - timedelta(days=30))

    async with async_session() as s:
        result = await s.execute(
            select(Job.description, func.count(Job.id))
            .where(Job.kind == "_writeback")
            .where(Job.created_at >= since)
            .group_by(Job.description)
            .order_by(func.count(Job.id).desc())
            .limit(20)
        )
        return [
            {"description": row[0], "count": row[1]}
            for row in result.fetchall()
        ]


async def escalation_frequency(
    since: datetime | None = None,
) -> list[dict[str, Any]]:
    """Count escalation jobs per original skill."""
    since = since or (datetime.now(timezone.utc) - timedelta(days=30))

    async with async_session() as s:
        result = await s.execute(
            select(Job.description, func.count(Job.id))
            .where(Job.created_by.like("escalation:%"))
            .where(Job.created_at >= since)
            .group_by(Job.description)
            .order_by(func.count(Job.id).desc())
            .limit(20)
        )
        return [
            {"description": row[0], "count": row[1]}
            for row in result.fetchall()
        ]


# ── Context consumption signal (Rec 2) ────────────────────────────────────


@dataclass
class ContextUsage:
    skill: str
    file_path: str
    read_count: int
    total_skill_jobs: int
    success_rate: float
    avg_rating: float | None


def parse_read_events(audit_log_lines: list[str]) -> list[tuple[str, str]]:
    """Pure. Parse audit log JSONL lines; return list of (job_id, file_path)
    for every Read tool_use event.

    Skips malformed lines silently. Deduplicates (job_id, file_path) pairs
    so a job that reads the same file twice counts once per job.
    """
    seen: set[tuple[str, str]] = set()
    results: list[tuple[str, str]] = []
    for line in audit_log_lines:
        line = line.strip()
        if not line:
            continue
        try:
            evt = json.loads(line)
        except json.JSONDecodeError:
            continue
        if evt.get("kind") != "tool_use" or evt.get("tool_name") != "Read":
            continue
        job_id = evt.get("job_id", "")
        file_path = (evt.get("input") or {}).get("file_path", "")
        if not job_id or not file_path:
            continue
        key = (job_id, file_path)
        if key not in seen:
            seen.add(key)
            results.append(key)
    return results


def _normalize_path(file_path: str, server_root: str) -> str:
    """Strip the server root prefix from absolute paths to get repo-relative paths.

    Pure function. If the path doesn't start with server_root, return as-is.
    """
    if file_path.startswith(server_root):
        rel = file_path[len(server_root):]
        if rel.startswith("/"):
            rel = rel[1:]
        return rel
    return file_path


async def context_consumption(
    since: datetime | None = None,
) -> list[ContextUsage]:
    """For each (skill, file_path) ever Read by any session in the window,
    return read_count + success_rate + avg_rating.

    Walks audit logs modified since `since`, extracts Read tool_use events,
    groups by (resolved_skill, file_path), joins against jobs table for
    status / rating.
    """
    since = since or (datetime.now(timezone.utc) - timedelta(days=30))
    log_dir = settings.audit_log_dir

    # 1. Collect (job_id, file_path) pairs from audit logs modified since `since`
    all_pairs: list[tuple[str, str]] = []
    if log_dir.exists():
        cutoff_ts = since.timestamp()
        for log_file in log_dir.glob("*.jsonl"):
            if log_file.stat().st_mtime < cutoff_ts:
                continue
            with log_file.open() as f:
                lines = f.readlines()
            all_pairs.extend(parse_read_events(lines))

    if not all_pairs:
        return []

    # 2. Get unique job_ids and fetch their metadata from the DB
    job_ids = list({jid for jid, _ in all_pairs})

    async with async_session() as s:
        result = await s.execute(
            select(
                Job.id,
                Job.resolved_skill,
                Job.status,
                Job.user_rating,
            )
            .where(Job.id.in_(job_ids))
            .where(Job.resolved_skill.isnot(None))
            .where(Job.created_at >= since)
        )
        job_meta = {
            str(row.id): {
                "skill": row.resolved_skill,
                "status": row.status,
                "rating": row.user_rating,
            }
            for row in result.all()
        }

    server_root = str(settings.server_root)

    # 3. Group by (skill, normalized_file_path) and compute metrics
    # skill -> set of job_ids (for total_skill_jobs)
    skill_jobs: dict[str, set[str]] = {}
    # (skill, file_path) -> list of job metadata dicts
    pair_jobs: dict[tuple[str, str], list[dict]] = {}

    for job_id, raw_path in all_pairs:
        meta = job_meta.get(job_id)
        if not meta:
            continue
        skill = meta["skill"]
        norm_path = _normalize_path(raw_path, server_root)

        skill_jobs.setdefault(skill, set()).add(job_id)

        key = (skill, norm_path)
        pair_jobs.setdefault(key, []).append(meta)

    # 4. Build output
    out: list[ContextUsage] = []
    for (skill, file_path), jobs in pair_jobs.items():
        read_count = len(jobs)
        total = len(skill_jobs.get(skill, set()))
        successes = sum(1 for j in jobs if j["status"] == JobStatus.completed.value)
        ratings = [j["rating"] for j in jobs if j["rating"] is not None]

        out.append(ContextUsage(
            skill=skill,
            file_path=file_path,
            read_count=read_count,
            total_skill_jobs=total,
            success_rate=successes / len(jobs) if jobs else 0.0,
            avg_rating=sum(ratings) / len(ratings) if ratings else None,
        ))

    out.sort(key=lambda x: (-x.read_count, x.skill, x.file_path))
    return out
