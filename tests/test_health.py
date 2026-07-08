"""
Tests for the /health liveness verdict (pure function).

Run: pipenv run pytest tests/test_health.py -v
"""

from __future__ import annotations

from src.gateway.web import health_verdict

STALE = 90.0


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
