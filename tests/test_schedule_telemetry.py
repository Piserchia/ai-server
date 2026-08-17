"""
Tests for schedule_rollup — the pure fold behind /api/telemetry/schedules.

Run: pipenv run pytest tests/test_schedule_telemetry.py -v

No DB, no Redis: the endpoint is a thin query wrapper; the semantics live
here. The fold answers the owner's question "is the machine that runs the
lab healthy?" — so the tests pin the semantics that question depends on:
in-flight runs are not evidence, streaks read newest-first, and absent
timestamps yield absent durations rather than zeros.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.gateway.web import schedule_rollup

NOW = datetime(2026, 8, 17, 12, 0, 0, tzinfo=timezone.utc)


def _sched(name="atlas-momo-drift", sid="s1", paused=False):
    return {
        "id": sid,
        "name": name,
        "cron_expression": "30 13 1 * *",
        "paused": paused,
        "next_run_at": "2026-09-01T13:30:00+00:00",
    }


def _job(sid="s1", status="completed", age_h=1.0, dur_s=120.0):
    created = NOW - timedelta(hours=age_h)
    started = created + timedelta(seconds=5)
    completed = started + timedelta(seconds=dur_s) if status in ("completed", "failed") else None
    return {
        "schedule_id": sid,
        "status": status,
        "created_at": created,
        "started_at": started if status != "queued" else None,
        "completed_at": completed,
    }


class TestRollupBasics:
    def test_empty_inputs_yield_empty(self):
        assert schedule_rollup([], []) == []

    def test_schedule_with_no_jobs_reports_no_runs_not_zeros_dressed_as_health(self):
        [row] = schedule_rollup([_sched()], [])
        assert row["runs"] == 0
        assert row["success_rate"] is None, "no runs is 'no evidence', not 0% or 100%"
        assert row["last_status"] is None
        assert row["avg_duration_s"] is None

    def test_counts_and_success_rate(self):
        jobs = [
            _job(age_h=1), _job(age_h=2), _job(age_h=3, status="failed"),
            _job(age_h=4),
        ]
        [row] = schedule_rollup([_sched()], jobs)
        assert row["runs"] == 4
        assert row["completed"] == 3
        assert row["failed"] == 1
        assert row["success_rate"] == 0.75

    def test_jobs_of_other_schedules_do_not_bleed_in(self):
        jobs = [_job(sid="other-schedule", age_h=1)]
        [row] = schedule_rollup([_sched(sid="s1")], jobs)
        assert row["runs"] == 0

    def test_manual_jobs_without_a_schedule_id_are_excluded(self):
        """Review 2026-08-17 finding: kinds are dispatchable by hand, so a
        manual re-run (schedule_id NULL) must not touch the schedule's stats —
        a manually-cancelled retry resetting a failing streak would hide
        exactly the breakage the section exists to show."""
        jobs = [
            _job(sid="s1", status="failed", age_h=2),
            _job(sid=None, status="cancelled", age_h=1),  # manual re-run+cancel
        ]
        [row] = schedule_rollup([_sched(sid="s1")], jobs)
        assert row["consecutive_failures"] == 1, "the manual cancel must not reset it"
        assert row["runs"] == 1


class TestInFlightIsNotEvidence:
    def test_running_job_is_excluded_from_runs_and_last(self):
        jobs = [_job(status="running", age_h=0.1), _job(age_h=2)]
        [row] = schedule_rollup([_sched()], jobs)
        assert row["runs"] == 1
        assert row["last_status"] == "completed"
        assert row["in_flight"] == 1

    def test_awaiting_user_is_visible_as_in_flight(self):
        """Review 2026-08-17 finding: a run parked in awaiting_user for days is
        the stuck state this section exists to surface — counting only
        'running' would render the schedule healthy and idle."""
        jobs = [_job(status="awaiting_user", age_h=48)]
        [row] = schedule_rollup([_sched()], jobs)
        assert row["runs"] == 0
        assert row["in_flight"] == 1

    def test_queued_job_counts_as_in_flight_not_as_a_run(self):
        jobs = [_job(status="queued", age_h=0.1)]
        [row] = schedule_rollup([_sched()], jobs)
        assert row["runs"] == 0
        assert row["in_flight"] == 1


class TestFailureStreak:
    def test_streak_counts_from_newest_terminal_backwards(self):
        jobs = [
            _job(status="failed", age_h=1),
            _job(status="failed", age_h=2),
            _job(status="completed", age_h=3),
            _job(status="failed", age_h=4),
        ]
        [row] = schedule_rollup([_sched()], jobs)
        assert row["consecutive_failures"] == 2, "the old failure is behind a success"

    def test_streak_zero_when_latest_run_succeeded(self):
        jobs = [_job(age_h=1), _job(status="failed", age_h=2)]
        [row] = schedule_rollup([_sched()], jobs)
        assert row["consecutive_failures"] == 0

    def test_cancelled_ends_a_streak_without_being_a_failure(self):
        """A cancel is an operator action. It must not extend a failing streak
        (that would page on human intervention) and must not count as success."""
        jobs = [
            _job(status="failed", age_h=1),
            _job(status="cancelled", age_h=2),
            _job(status="failed", age_h=3),
        ]
        [row] = schedule_rollup([_sched()], jobs)
        assert row["consecutive_failures"] == 1
        assert row["completed"] == 0
        assert row["runs"] == 3

    def test_running_job_does_not_interrupt_the_streak_read(self):
        """A retry in flight must not mask a failing schedule — the streak is
        over TERMINAL runs, so 'failed, failed, (running)' still reads 2."""
        jobs = [
            _job(status="running", age_h=0.1),
            _job(status="failed", age_h=1),
            _job(status="failed", age_h=2),
        ]
        [row] = schedule_rollup([_sched()], jobs)
        assert row["consecutive_failures"] == 2


class TestDurations:
    def test_last_and_avg_durations(self):
        jobs = [_job(age_h=1, dur_s=100.0), _job(age_h=2, dur_s=200.0)]
        [row] = schedule_rollup([_sched()], jobs)
        assert row["last_duration_s"] == 100.0
        assert row["avg_duration_s"] == 150.0

    def test_job_without_timestamps_has_no_duration_not_zero(self):
        j = _job(status="failed", age_h=1)
        j["started_at"] = None
        j["completed_at"] = None
        [row] = schedule_rollup([_sched()], [j])
        assert row["last_duration_s"] is None
        assert row["avg_duration_s"] is None
        assert row["runs"] == 1, "it still counts as a run — it just has no duration"


class TestOrdering:
    def test_failing_schedules_sort_first_paused_last(self):
        schedules = [
            _sched(name="healthy", sid="k1"),
            _sched(name="broken", sid="k2"),
            _sched(name="parked", sid="k3", paused=True),
        ]
        jobs = [
            _job(sid="k1", age_h=1),
            _job(sid="k2", status="failed", age_h=1),
            _job(sid="k2", status="failed", age_h=2),
        ]
        rows = schedule_rollup(schedules, jobs)
        assert [r["name"] for r in rows] == ["broken", "healthy", "parked"]
