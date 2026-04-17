"""
Rollup queries for the auto-tuning retrospective.

Used by the review-and-improve skill to analyze job performance and propose
tuning changes. Can also be used by the dashboard for a "performance" view.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import case, cast, func, select, Integer
from src.db import async_session
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
