"""Schedule-adherence monitor — the missing-run axis of fleet telemetry.

schedule_rollup (src/gateway/web.py) grades runs that exist; nothing in the
system notices a schedule that silently stops producing runs at all. That is
the 08-17 governor-dark incident class (scheduler task dead / phase-shifted
after an outage / row hand-paused and forgotten) and the scout-never-ran
class. This module is the deterministic answer. It is invoked OUT-OF-BAND by
scripts/schedule-monitor.sh on a launchd timer — never by the scheduler it
watches (healthcheck-all.sh codifies the rationale).

Pure decision logic up top (dicts in, findings out, injected now) so the
tests need zero fixtures; the async collector + CLI main at the bottom are
thin I/O.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from croniter import croniter

#: Terminal statuses — same set schedule_rollup uses.
_TERMINAL = {"completed", "failed", "cancelled"}

#: Jobs may be stamped up to this many seconds before their cron slot
#: (clock skew safety); the scheduler itself fires <=30s after.
_SLOT_SLACK_S = 120


def adherence_report(
    schedules: list[dict],
    jobs: list[dict],
    now: datetime,
    window_days: int = 45,
    grace_seconds: int = 10800,
    streak_threshold: int = 3,
    stuck_hours: int = 24,
) -> dict[str, Any]:
    """Pure. Fold the fleet into adherence findings + per-schedule statuses.

    ``jobs`` must be pre-filtered to the window and ordered NEWEST FIRST and
    matched by schedule_id, never kind — the schedule_rollup contract.
    Finding kinds, in severity order: DARK (latest expected slot has no job
    after grace), NEVER_RAN (slots expected since creation, zero jobs ever),
    STUCK (non-terminal job older than stuck_hours), FAILURE_STREAK
    (>= streak_threshold consecutive terminal failures; cancelled ends a
    streak — operator action, not reliability signal).
    """
    by_schedule: dict[str, list[dict]] = {}
    for j in jobs:
        by_schedule.setdefault(str(j["schedule_id"]), []).append(j)

    findings: list[dict] = []
    rows: list[dict] = []
    for sch in schedules:
        name = sch["name"]
        sjobs = by_schedule.get(str(sch["id"]), [])
        newest = sjobs[0]["created_at"] if sjobs else None
        if sch.get("paused"):
            rows.append(_row(sch, "paused", None, newest))
            continue

        last_slot = croniter(sch["cron_expression"], now).get_prev(datetime)
        # Status is built by sequential overwrites in ASCENDING severity —
        # failing < stuck < dark/never_ran — so when several conditions
        # apply, the last (most severe) write wins, matching the severity
        # table used for sorting below (review 2026-09-01: the original
        # stuck-then-failing order let a streak clobber a hung job).
        status = "ok"

        terminal = [j for j in sjobs if j["status"] in _TERMINAL]
        streak = 0
        for j in terminal:  # newest first
            if j["status"] == "failed":
                streak += 1
            else:
                break
        if streak >= streak_threshold:
            status = "failing"
            findings.append({
                "kind": "FAILURE_STREAK", "schedule": name,
                "detail": f"{streak} consecutive failures",
            })

        stuck = [
            j for j in sjobs
            if j["status"] not in _TERMINAL
            and (now - j["created_at"]) > timedelta(hours=stuck_hours)
        ]
        if stuck:
            status = "stuck"
            findings.append({
                "kind": "STUCK", "schedule": name,
                "detail": f"{len(stuck)} non-terminal job(s) older than "
                          f"{stuck_hours}h (oldest status "
                          f"{stuck[-1]['status']!r})",
            })

        slot_covered = any(
            j["created_at"] >= last_slot - timedelta(seconds=_SLOT_SLACK_S)
            for j in sjobs
        )
        past_grace = (now - last_slot) > timedelta(seconds=grace_seconds)
        expected_since_creation = croniter(
            sch["cron_expression"], sch["created_at"]
        ).get_next(datetime) <= now

        if sch.get("total_jobs", 0) == 0:
            if expected_since_creation and past_grace:
                status = "never_ran"
                findings.append({
                    "kind": "NEVER_RAN", "schedule": name,
                    "detail": "zero jobs ever despite expected slots since "
                              f"{sch['created_at']:%Y-%m-%d}",
                })
        elif past_grace and not slot_covered:
            status = "dark"
            findings.append({
                "kind": "DARK", "schedule": name,
                "detail": f"no job since expected slot "
                          f"{last_slot:%Y-%m-%d %H:%M}Z "
                          f"(grace {grace_seconds // 3600}h exceeded)",
            })

        rows.append(_row(sch, status, last_slot, newest))

    severity = {"dark": 0, "never_ran": 1, "stuck": 2, "failing": 3,
                "ok": 4, "paused": 5}
    rows.sort(key=lambda r: (severity[r["status"]], r["name"]))
    order = {"DARK": 0, "NEVER_RAN": 1, "STUCK": 2, "FAILURE_STREAK": 3}
    findings.sort(key=lambda f: (order[f["kind"]], f["schedule"]))
    return {"findings": findings, "schedules": rows}


def _row(sch: dict, status: str, last_slot: datetime | None,
         observed: datetime | None) -> dict:
    return {
        "name": sch["name"],
        "cron": sch["cron_expression"],
        "paused": bool(sch.get("paused")),
        "status": status,
        "last_expected": last_slot.isoformat() if last_slot else None,
        "observed_job_at": observed.isoformat() if observed else None,
    }


# ── I/O below: thin, untested by design (pure-function-first suite) ─────────

async def _collect(window_days: int = 45) -> tuple[list[dict], list[dict]]:
    """Read schedules (+ per-schedule total job count) and windowed jobs."""
    from sqlalchemy import func, select

    from src.db import async_session
    from src.models import Job, Schedule

    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    async with async_session() as s:
        counts = dict(
            (await s.execute(
                select(Job.schedule_id, func.count())
                .where(Job.schedule_id.is_not(None))
                .group_by(Job.schedule_id)
            )).all()
        )
        scheds = [{
            "id": str(r.id), "name": r.name,
            "cron_expression": r.cron_expression,
            "paused": r.paused, "created_at": r.created_at,
            "total_jobs": int(counts.get(r.id, 0)),
        } for r in (await s.execute(select(Schedule))).scalars()]
        jobs = [{
            "schedule_id": str(r.schedule_id), "status": r.status,
            "created_at": r.created_at, "started_at": r.started_at,
            "completed_at": r.completed_at,
        } for r in (await s.execute(
            select(Job)
            .where(Job.schedule_id.is_not(None), Job.created_at >= cutoff)
            .order_by(Job.created_at.desc())
        )).scalars()]
    return scheds, jobs


def main() -> None:
    import asyncio
    import json
    from pathlib import Path

    now = datetime.now(timezone.utc)
    scheds, jobs = asyncio.run(_collect())
    rep = adherence_report(scheds, jobs, now)

    out = Path("volumes/telemetry")
    out.mkdir(parents=True, exist_ok=True)
    (out / "schedule_adherence.json").write_text(json.dumps({
        "generated_at": now.isoformat(),
        "findings": rep["findings"],
        "schedules": rep["schedules"],
    }, indent=2))

    for f in rep["findings"]:
        print(f"FINDING {f['kind']} {f['schedule']}: {f['detail']}")
    n_paused = sum(1 for r in rep["schedules"] if r["status"] == "paused")
    print(f"OK {len(scheds)} schedules ({n_paused} paused), "
          f"{len(rep['findings'])} finding(s)")


if __name__ == "__main__":
    main()
