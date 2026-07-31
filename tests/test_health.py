"""
Tests for the /health liveness verdict + heartbeat parsing (pure functions).

Run: pipenv run pytest tests/test_health.py -v
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.gateway.web import health_verdict, parse_heartbeat_age

STALE = 90.0
NOW = datetime(2026, 7, 30, 12, 0, 0, tzinfo=timezone.utc)


class TestParseHeartbeatAge:
    """The runner writes epoch seconds (2026-07-30); ISO-8601 is the legacy
    format kept parseable for the mixed-version deploy window."""

    def test_epoch_fresh(self):
        raw = str(int(NOW.timestamp()) - 30)
        assert parse_heartbeat_age(raw, NOW) == 30.0

    def test_epoch_float_string(self):
        raw = str(NOW.timestamp() - 5.5)
        age = parse_heartbeat_age(raw, NOW)
        assert age is not None and abs(age - 5.5) < 0.001

    def test_iso_aware_fallback(self):
        raw = (NOW - timedelta(seconds=45)).isoformat()
        assert parse_heartbeat_age(raw, NOW) == 45.0

    def test_iso_naive_assumed_utc(self):
        raw = (NOW - timedelta(seconds=60)).replace(tzinfo=None).isoformat()
        assert parse_heartbeat_age(raw, NOW) == 60.0

    def test_none_and_empty_are_none(self):
        assert parse_heartbeat_age(None, NOW) is None
        assert parse_heartbeat_age("", NOW) is None

    def test_garbage_is_none(self):
        assert parse_heartbeat_age("not-a-timestamp", NOW) is None

    def test_future_epoch_clock_skew_is_negative_age(self):
        # Slight clock skew must read as a (very fresh) live runner, not a dead one.
        raw = str(int(NOW.timestamp()) + 3)
        assert parse_heartbeat_age(raw, NOW) == -3.0


class TestHealthVerdict:
    def test_all_good(self):
        runner_ok, healthy = health_verdict(5.0, True, True, STALE)
        assert runner_ok and healthy

    def test_stale_heartbeat_unhealthy(self):
        runner_ok, healthy = health_verdict(120.0, True, True, STALE)
        assert not runner_ok and not healthy

    def test_missing_heartbeat_unhealthy(self):
        runner_ok, healthy = health_verdict(None, True, True, STALE)
        assert not runner_ok and not healthy

    def test_boundary_is_ok(self):
        runner_ok, healthy = health_verdict(90.0, True, True, STALE)
        assert runner_ok and healthy

    def test_db_down_unhealthy_even_if_runner_fresh(self):
        runner_ok, healthy = health_verdict(1.0, False, True, STALE)
        assert runner_ok and not healthy

    def test_redis_down_unhealthy(self):
        runner_ok, healthy = health_verdict(1.0, True, False, STALE)
        assert runner_ok and not healthy
