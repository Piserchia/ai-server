"""Schedule-adherence monitor decision logic — the missing-run axis.

schedule_rollup (src/gateway/web.py) answers "did runs fail?"; this module
answers "did runs happen at all?" — the 08-17 governor-dark incident class
(and the scout-never-ran class) that no existing telemetry covers.

Run: pipenv run pytest tests/test_schedule_adherence.py -v
"""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from src.runner.schedule_adherence import adherence_report

NOW = datetime(2026, 9, 2, 18, 0, tzinfo=timezone.utc)  # Wednesday


def _sched(name="s", cron="0 11 * * 1", paused=False, created_days_ago=120,
           total_jobs=10, sid=None):
    return {
        "id": sid or str(uuid4()),
        "name": name,
        "cron_expression": cron,
        "paused": paused,
        "created_at": NOW - timedelta(days=created_days_ago),
        "total_jobs": total_jobs,
    }


def _job(sid, status="completed", created_hours_ago=1.0):
    created = NOW - timedelta(hours=created_hours_ago)
    terminal = status in {"completed", "failed", "cancelled"}
    return {
        "schedule_id": sid,
        "status": status,
        "created_at": created,
        "started_at": created,
        "completed_at": created + timedelta(minutes=5) if terminal else None,
    }


class TestDark:
    def test_governor_dark_incident_shape(self):
        # Weekly Mon 11:00 UTC; last slot Mon 2026-08-31 11:00 — 55h before
        # NOW, no job since. The 08-17 incident: scheduler alive-looking,
        # governor silently not running.
        s = _sched(name="atlas-evaluate", cron="0 11 * * 1")
        jobs = [_job(s["id"], created_hours_ago=24 * 9)]  # last week's run only
        rep = adherence_report([s], jobs, NOW)
        assert [f["kind"] for f in rep["findings"]] == ["DARK"]
        assert rep["schedules"][0]["status"] == "dark"

    def test_job_covering_latest_slot_is_healthy(self):
        s = _sched(cron="0 11 * * 1")
        jobs = [_job(s["id"], created_hours_ago=54.9)]  # fired right at Mon slot
        rep = adherence_report([s], jobs, NOW)
        assert rep["findings"] == []
        assert rep["schedules"][0]["status"] == "ok"

    def test_within_grace_not_dark(self):
        # Slot 2h ago, grace 3h — too early to judge.
        s = _sched(cron="0 16 * * *")
        rep = adherence_report([s], [], NOW)
        assert all(f["kind"] != "DARK" for f in rep["findings"])

    def test_slot_clock_slack(self):
        # Job created 90s BEFORE the slot timestamp still counts (clock skew).
        s = _sched(cron="0 11 * * 1")
        slot = datetime(2026, 8, 31, 11, 0, tzinfo=timezone.utc)
        j = _job(s["id"])
        j["created_at"] = slot - timedelta(seconds=90)
        rep = adherence_report([s], [j], NOW)
        assert rep["findings"] == []

    def test_paused_schedule_skipped(self):
        s = _sched(cron="0 11 * * 1", paused=True)
        rep = adherence_report([s], [], NOW)
        assert rep["findings"] == []
        assert rep["schedules"][0]["status"] == "paused"


class TestNeverRan:
    def test_scout_never_ran(self):
        # Enabled for months, slots expected, zero jobs EVER.
        s = _sched(name="atlas-scout", cron="0 12 * * 3", total_jobs=0)
        rep = adherence_report([s], [], NOW)
        kinds = {f["kind"] for f in rep["findings"]}
        assert "NEVER_RAN" in kinds
        assert rep["schedules"][0]["status"] == "never_ran"

    def test_new_schedule_no_slot_yet_is_ok(self):
        # Created an hour ago, first slot tomorrow: nothing expected yet.
        s = _sched(cron="0 11 * * 1", created_days_ago=0, total_jobs=0)
        s["created_at"] = NOW - timedelta(hours=1)
        rep = adherence_report([s], [], NOW)
        assert rep["findings"] == []


class TestFailureStreak:
    def test_three_consecutive_failures_flagged(self):
        s = _sched(cron="0 16 * * *")
        jobs = [_job(s["id"], "failed", 2), _job(s["id"], "failed", 26),
                _job(s["id"], "failed", 50), _job(s["id"], "completed", 74)]
        rep = adherence_report([s], jobs, NOW)
        assert any(f["kind"] == "FAILURE_STREAK" for f in rep["findings"])
        assert rep["schedules"][0]["status"] == "failing"

    def test_cancelled_ends_streak(self):
        s = _sched(cron="0 16 * * *")
        jobs = [_job(s["id"], "failed", 2), _job(s["id"], "failed", 26),
                _job(s["id"], "cancelled", 50), _job(s["id"], "failed", 74)]
        rep = adherence_report([s], jobs, NOW)
        assert all(f["kind"] != "FAILURE_STREAK" for f in rep["findings"])


class TestStuck:
    def test_old_nonterminal_job_flagged(self):
        s = _sched(cron="0 16 * * *")
        jobs = [_job(s["id"], "awaiting_user", 30), _job(s["id"], "completed", 2)]
        rep = adherence_report([s], jobs, NOW)
        assert any(f["kind"] == "STUCK" for f in rep["findings"])

    def test_stuck_beats_failure_streak_status(self):
        # Both conditions apply: a hung >24h job AND a 3-failure streak.
        # Both findings must appear, and the per-schedule status must be
        # the more severe "stuck" (review 2026-09-01 precedence fix).
        s = _sched(cron="0 16 * * *")
        jobs = [_job(s["id"], "running", 25), _job(s["id"], "failed", 50),
                _job(s["id"], "failed", 74), _job(s["id"], "failed", 98)]
        rep = adherence_report([s], jobs, NOW)
        kinds = {f["kind"] for f in rep["findings"]}
        assert {"STUCK", "FAILURE_STREAK"} <= kinds
        assert rep["schedules"][0]["status"] == "stuck"

    def test_recent_running_job_ok(self):
        s = _sched(cron="0 16 * * *")
        jobs = [_job(s["id"], "running", 1), _job(s["id"], "completed", 26)]
        rep = adherence_report([s], jobs, NOW)
        assert all(f["kind"] != "STUCK" for f in rep["findings"])


class TestReportShape:
    def test_dark_sorts_first_and_healthy_fleet_summary(self):
        dark = _sched(name="z-dark", cron="0 11 * * 1")
        ok = _sched(name="a-ok", cron="0 16 * * *")
        jobs = [_job(ok["id"], created_hours_ago=2)]
        rep = adherence_report([dark, ok], jobs, NOW)
        assert rep["schedules"][0]["name"] == "z-dark"
        assert {"findings", "schedules"} <= set(rep)
