"""Unit tests for context budget helpers."""

from __future__ import annotations

import json

from src.runner.retrospective import (
    aggregate_context_budgets,
    parse_budget_events,
)
from src.runner.session import context_budget_fraction, estimate_context_tokens


class TestEstimateContextTokens:
    def test_empty(self):
        assert estimate_context_tokens("") == 0

    def test_short_text(self):
        assert estimate_context_tokens("hello world") == 2  # 11 chars // 4

    def test_longer_text(self):
        text = "a" * 400
        assert estimate_context_tokens(text) == 100


class TestContextBudgetFraction:
    def test_basic(self):
        tokens, budget, frac = context_budget_fraction("x" * 800, "claude-sonnet-4-6")
        assert tokens == 200
        assert budget == 200_000
        assert abs(frac - 0.001) < 0.0001

    def test_unknown_model(self):
        tokens, budget, frac = context_budget_fraction("x" * 400, "unknown-model")
        assert budget == 200_000  # default

    def test_empty_prompt(self):
        tokens, budget, frac = context_budget_fraction("", "claude-sonnet-4-6")
        assert tokens == 0
        assert frac == 0.0


class TestParseBudgetEvents:
    def test_empty(self):
        assert parse_budget_events([]) == []

    def test_non_budget_events_skipped(self):
        line = json.dumps({"kind": "tool_use", "tool_name": "Read"})
        assert parse_budget_events([line]) == []

    def test_budget_event_extracted(self):
        line = json.dumps({
            "kind": "context_budget_used",
            "skill": "app-patch",
            "estimated_tokens": 500,
            "fraction": 0.0025,
        })
        result = parse_budget_events([line])
        assert len(result) == 1
        assert result[0]["skill"] == "app-patch"
        assert result[0]["tokens"] == 500

    def test_missing_skill_skipped(self):
        line = json.dumps({
            "kind": "context_budget_used",
            "skill": "",
            "estimated_tokens": 500,
            "fraction": 0.0025,
        })
        assert parse_budget_events([line]) == []


class TestAggregateBudgets:
    def test_empty(self):
        assert aggregate_context_budgets([]) == []

    def test_single_skill(self):
        events = [
            {"skill": "app-patch", "tokens": 100, "fraction": 0.05},
            {"skill": "app-patch", "tokens": 200, "fraction": 0.10},
        ]
        result = aggregate_context_budgets(events)
        assert len(result) == 1
        assert result[0].skill == "app-patch"
        assert result[0].avg_tokens == 150
        assert abs(result[0].avg_fraction - 0.075) < 0.001
        assert result[0].max_fraction == 0.10
        assert result[0].sample_count == 2

    def test_multiple_skills_sorted(self):
        events = [
            {"skill": "z-skill", "tokens": 100, "fraction": 0.05},
            {"skill": "a-skill", "tokens": 200, "fraction": 0.10},
        ]
        result = aggregate_context_budgets(events)
        assert len(result) == 2
        assert result[0].skill == "a-skill"
        assert result[1].skill == "z-skill"
