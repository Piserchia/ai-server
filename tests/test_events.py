"""Tests for src/runner/events.py — pure-function tests only (no DB)."""

import asyncio
from datetime import datetime, timedelta, timezone

from src.runner import events as events_mod
from src.runner.events import (
    BREAKER_FAILURE_THRESHOLD,
    BREAKER_SIGNATURE_LEN,
    _error_signature,
    _should_trigger_skill_diagnose,
    _should_trigger_project_diagnose,
    _should_trigger_idle_review,
    event_loop,
    should_trip_breaker,
)

NOW = datetime.now(timezone.utc)


class TestSkillDiagnose:
    def test_two_failures_triggers(self):
        failures = [
            {"resolved_skill": "research-report", "created_at": NOW - timedelta(minutes=2)},
            {"resolved_skill": "research-report", "created_at": NOW - timedelta(minutes=5)},
        ]
        result = _should_trigger_skill_diagnose(failures, [])
        assert "research-report" in result

    def test_one_failure_does_not_trigger(self):
        failures = [
            {"resolved_skill": "research-report", "created_at": NOW - timedelta(minutes=2)},
        ]
        result = _should_trigger_skill_diagnose(failures, [])
        assert result == []

    def test_old_failures_outside_window(self):
        failures = [
            {"resolved_skill": "research-report", "created_at": NOW - timedelta(minutes=15)},
            {"resolved_skill": "research-report", "created_at": NOW - timedelta(minutes=20)},
        ]
        result = _should_trigger_skill_diagnose(failures, [])
        assert result == []

    def test_existing_diagnose_prevents_duplicate(self):
        failures = [
            {"resolved_skill": "research-report", "created_at": NOW - timedelta(minutes=2)},
            {"resolved_skill": "research-report", "created_at": NOW - timedelta(minutes=5)},
        ]
        existing = [
            {"description": "Self-diagnose: skill 'research-report' failed", "created_at": NOW - timedelta(minutes=1)},
        ]
        result = _should_trigger_skill_diagnose(failures, existing)
        assert result == []

    def test_queued_diagnose_with_null_resolved_skill_still_dedups(self):
        # Regression (2026-08-21): the DB dedup query used to filter by
        # Job.resolved_skill=='self-diagnose', but resolved_skill is NULL until
        # the runner starts running the job. That meant queued self-diagnose
        # jobs were invisible to dedup, and each 60-s event cycle spawned
        # another duplicate for the same target. The pure function must not
        # reintroduce that reliance: it dedupes off description alone. This
        # test constructs the exact shape a queued Job produces
        # (resolved_skill=None) and confirms it still suppresses the trigger.
        failures = [
            {"resolved_skill": "research-report", "created_at": NOW - timedelta(minutes=2)},
            {"resolved_skill": "research-report", "created_at": NOW - timedelta(minutes=5)},
        ]
        existing = [
            {
                "description": "Self-diagnose: skill 'research-report' failed",
                "created_at": NOW - timedelta(minutes=1),
                "resolved_skill": None,  # queued, not yet picked up
            },
        ]
        result = _should_trigger_skill_diagnose(failures, existing)
        assert result == []

    def test_different_skills_independent(self):
        failures = [
            {"resolved_skill": "research-report", "created_at": NOW - timedelta(minutes=2)},
            {"resolved_skill": "research-report", "created_at": NOW - timedelta(minutes=5)},
            {"resolved_skill": "chat", "created_at": NOW - timedelta(minutes=3)},
        ]
        result = _should_trigger_skill_diagnose(failures, [])
        assert "research-report" in result
        assert "chat" not in result  # only 1 failure

    def test_empty_failures(self):
        result = _should_trigger_skill_diagnose([], [])
        assert result == []

    def test_none_skill_ignored(self):
        failures = [
            {"resolved_skill": None, "created_at": NOW - timedelta(minutes=2)},
            {"resolved_skill": None, "created_at": NOW - timedelta(minutes=5)},
        ]
        result = _should_trigger_skill_diagnose(failures, [])
        assert result == []


class TestProjectDiagnose:
    def test_unhealthy_project_triggers(self):
        projects = [
            {"slug": "market-tracker", "type": "service", "last_healthy_at": NOW - timedelta(minutes=25)},
        ]
        result = _should_trigger_project_diagnose(projects, [])
        assert "market-tracker" in result

    def test_healthy_project_no_trigger(self):
        projects = [
            {"slug": "market-tracker", "type": "service", "last_healthy_at": NOW - timedelta(minutes=3)},
        ]
        result = _should_trigger_project_diagnose(projects, [])
        assert result == []

    def test_static_project_skipped(self):
        projects = [
            {"slug": "bingo", "type": "static", "last_healthy_at": NOW - timedelta(minutes=30)},
        ]
        result = _should_trigger_project_diagnose(projects, [])
        assert result == []

    def test_never_healthy_skipped(self):
        # New project that hasn't been checked yet — not a failure
        projects = [
            {"slug": "new-app", "type": "service", "last_healthy_at": None},
        ]
        result = _should_trigger_project_diagnose(projects, [])
        assert result == []

    def test_existing_diagnose_prevents_duplicate(self):
        projects = [
            {"slug": "market-tracker", "type": "service", "last_healthy_at": NOW - timedelta(minutes=25)},
        ]
        existing = [
            {"description": "Self-diagnose: project 'market-tracker' has been unhealthy", "created_at": NOW - timedelta(minutes=5)},
        ]
        result = _should_trigger_project_diagnose(projects, existing)
        assert result == []

    def test_queued_diagnose_with_null_resolved_skill_still_dedups(self):
        # Regression (2026-08-21, recurrence #92 of the "project 'X'
        # unhealthy 20+ min but actually up" false positive): the DB dedup
        # query filtered by Job.resolved_skill=='self-diagnose', which is
        # NULL until the runner picks the job off the queue. Result: six
        # duplicate diagnoses (three per project) spawned for baseball-bingo
        # + atlas from a single cadence-slip event. The fix filters by
        # Job.kind (set at INSERT). This test locks in that a queued-shaped
        # dict (resolved_skill=None) still dedupes correctly at the pure
        # layer — if the DB query is ever narrowed again, the amplifier
        # returns.
        projects = [
            {"slug": "baseball-bingo", "type": "service", "last_healthy_at": NOW - timedelta(minutes=25)},
        ]
        existing = [
            {
                "description": "Self-diagnose: project 'baseball-bingo' has been unhealthy",
                "created_at": NOW - timedelta(minutes=1),
                "resolved_skill": None,  # queued, not yet picked up
            },
        ]
        result = _should_trigger_project_diagnose(projects, existing)
        assert result == []

    def test_empty_projects(self):
        result = _should_trigger_project_diagnose([], [])
        assert result == []


class TestIdleQueueReview:
    def test_idle_queue_no_prior_review(self):
        assert _should_trigger_idle_review(0, None) is True

    def test_idle_queue_old_review(self):
        assert _should_trigger_idle_review(0, NOW - timedelta(hours=25)) is True

    def test_idle_queue_recent_review(self):
        assert _should_trigger_idle_review(0, NOW - timedelta(hours=12)) is False

    def test_busy_queue_no_trigger(self):
        assert _should_trigger_idle_review(3, None) is False

    def test_busy_queue_old_review(self):
        assert _should_trigger_idle_review(1, NOW - timedelta(hours=30)) is False

    def test_exactly_at_cooldown_triggers(self):
        # Exactly 24h ago: the cooldown has elapsed, so trigger
        assert _should_trigger_idle_review(0, NOW - timedelta(hours=24)) is True

    def test_just_under_cooldown(self):
        assert _should_trigger_idle_review(0, NOW - timedelta(hours=23, minutes=59)) is False


class TestErrorSignature:
    def test_none_is_unknown(self):
        assert _error_signature(None) == "unknown"

    def test_blank_is_unknown(self):
        assert _error_signature("   \n\t ") == "unknown"

    def test_whitespace_collapsed(self):
        assert _error_signature("a   b\n\tc") == "a b c"

    def test_truncated_to_signature_len(self):
        assert _error_signature("x" * 200) == "x" * BREAKER_SIGNATURE_LEN

    def test_collapse_happens_before_truncation(self):
        # The length budget applies to the collapsed text, so messages that
        # differ only in whitespace layout share a signature.
        spread = "word  " * 40  # collapses to "word word word ..."
        tight = "word " * 40
        assert _error_signature(spread) == _error_signature(tight)
        assert len(_error_signature(spread)) == BREAKER_SIGNATURE_LEN

    def test_short_message_unchanged(self):
        assert _error_signature("boom") == "boom"


class TestShouldTripBreaker:
    def _failures(self, msg, n, minutes_ago=1):
        return [
            {"error_message": msg, "created_at": NOW - timedelta(minutes=minutes_ago)}
            for _ in range(n)
        ]

    def test_at_threshold_trips(self):
        fails = self._failures("'Server' object has no attribute 'list_tools'", 5)
        assert should_trip_breaker(fails) == "'Server' object has no attribute 'list_tools'"

    def test_below_threshold_does_not_trip(self):
        fails = self._failures("boom", 4)
        assert should_trip_breaker(fails) is None

    def test_default_threshold_is_five(self):
        assert BREAKER_FAILURE_THRESHOLD == 5

    def test_mixed_signatures_none_reach_threshold(self):
        # 9 total failures, but no single signature reaches 5
        fails = (self._failures("error A", 3)
                 + self._failures("error B", 3)
                 + self._failures("error C", 3))
        assert should_trip_breaker(fails) is None

    def test_mixed_signatures_one_trips(self):
        fails = self._failures("error A", 5) + self._failures("error B", 2)
        assert should_trip_breaker(fails) == "error A"

    def test_largest_cluster_wins(self):
        fails = self._failures("error A", 5) + self._failures("error B", 6)
        assert should_trip_breaker(fails) == "error B"

    def test_empty_failures(self):
        assert should_trip_breaker([]) is None

    def test_none_messages_group_as_unknown(self):
        fails = self._failures(None, 5)
        assert should_trip_breaker(fails) == "unknown"

    def test_missing_message_key_groups_as_unknown(self):
        fails = [{"created_at": NOW} for _ in range(5)]
        assert should_trip_breaker(fails) == "unknown"

    def test_whitespace_variants_group_together(self):
        fails = (self._failures("connect  timeout\nto db", 3)
                 + self._failures("connect timeout to db", 2))
        assert should_trip_breaker(fails) == "connect timeout to db"

    def test_long_messages_group_by_prefix(self):
        # Differ only past the signature length → same cluster
        base = "e" * BREAKER_SIGNATURE_LEN
        fails = [
            {"error_message": base + f" tail {i}", "created_at": NOW}
            for i in range(5)
        ]
        assert should_trip_breaker(fails) == base

    def test_custom_threshold(self):
        fails = self._failures("boom", 2)
        assert should_trip_breaker(fails, threshold=2) == "boom"
        assert should_trip_breaker(fails, threshold=3) is None

    def test_incident_shape_2026_07_30(self):
        # ~17 self-diagnose jobs event-spawned into a broken substrate, all
        # failing identically — must trip well past the threshold.
        fails = self._failures("'Server' object has no attribute 'list_tools'", 17)
        assert should_trip_breaker(fails) == "'Server' object has no attribute 'list_tools'"


class TestBreakerConstants:
    def test_redis_key_and_ttl(self):
        # Named constants in src.db per repo convention (never inline names)
        from src.db import KEY_EVENTS_BREAKER, TTL_EVENTS_BREAKER

        assert KEY_EVENTS_BREAKER == "events:breaker"
        assert TTL_EVENTS_BREAKER == 30 * 60


class TestEventLoopBreakerGating:
    """One-cycle event_loop runs with all four checks monkeypatched (no
    DB/Redis): the breaker must gate skill-failure + project-health spawning
    but never the idle-queue review, and a breaker crash must fail open."""

    def _run_cycle(self, monkeypatch, breaker):
        calls: list[str] = []
        shutdown = asyncio.Event()

        async def fake_skill():
            calls.append("skill")

        async def fake_project():
            calls.append("project")

        async def fake_idle():
            calls.append("idle")
            shutdown.set()  # end the loop after one full cycle

        monkeypatch.setattr(events_mod, "_check_circuit_breaker", breaker)
        monkeypatch.setattr(events_mod, "_check_skill_failures", fake_skill)
        monkeypatch.setattr(events_mod, "_check_project_health", fake_project)
        monkeypatch.setattr(events_mod, "_check_idle_queue_review", fake_idle)
        asyncio.run(event_loop(shutdown))
        return calls

    def test_breaker_active_skips_spawn_checks_not_idle_review(self, monkeypatch):
        async def breaker():
            return True

        assert self._run_cycle(monkeypatch, breaker) == ["idle"]

    def test_breaker_inactive_runs_all_checks(self, monkeypatch):
        async def breaker():
            return False

        assert self._run_cycle(monkeypatch, breaker) == ["skill", "project", "idle"]

    def test_breaker_crash_fails_open_and_loop_survives(self, monkeypatch):
        async def breaker():
            raise RuntimeError("redis down")

        assert self._run_cycle(monkeypatch, breaker) == ["skill", "project", "idle"]


class TestEventLoopStartup:
    def test_startup_logging_does_not_raise(self):
        """Regression (2026-07-30 runner-down incident): event_loop's startup
        log line used structlog-style kwargs on a stdlib logger — TypeError the
        moment the runner started, before the loop body ever ran. A pre-set
        shutdown event exercises exactly that line (loop body skipped, no DB).

        The level MUST be forced to INFO: `Logger.info` short-circuits on
        `isEnabledFor` before reaching `_log()`, and pytest's default level is
        WARNING — without this the buggy call never executes and the test
        passes on broken code (prod crashes because main() sets INFO)."""
        import logging

        ev_logger = logging.getLogger("src.runner.events")
        prior = ev_logger.level
        ev_logger.setLevel(logging.INFO)
        try:
            shutdown = asyncio.Event()
            shutdown.set()
            asyncio.run(event_loop(shutdown))
        finally:
            ev_logger.setLevel(prior)
