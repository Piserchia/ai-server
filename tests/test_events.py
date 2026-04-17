"""Tests for src/runner/events.py — pure-function tests only (no DB)."""

from datetime import datetime, timedelta, timezone

from src.runner.events import (
    _should_trigger_skill_diagnose,
    _should_trigger_project_diagnose,
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

    def test_empty_projects(self):
        result = _should_trigger_project_diagnose([], [])
        assert result == []
