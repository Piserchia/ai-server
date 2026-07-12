"""Tests for runner/plans.py (P2) + text-marker event extraction +
plain-text triage + LLM-router response parsing. Pure functions only —
no DB/Redis/SDK."""

from __future__ import annotations

import json

from src.runner.plans import (
    MAX_SUBTASKS,
    deps_satisfied,
    topo_order,
    validate_plan,
)
from src.runner.session import extract_text_events
from src.runner.llm_router import parse_route_response


def _plan(**overrides):
    base = {
        "goal": "Add dark mode to bingo",
        "acceptance_criteria": ["/ returns 200 with dark-mode toggle"],
        "subtasks": [
            {"id": "s1", "kind": "app-patch", "description": "add css vars",
             "project_slug": "baseball-bingo", "depends_on": []},
            {"id": "s2", "kind": "app-patch", "description": "add toggle",
             "project_slug": "baseball-bingo", "depends_on": ["s1"]},
        ],
        "verification": "curl the page",
    }
    base.update(overrides)
    return base


class TestValidatePlan:
    def test_valid_plan(self):
        assert validate_plan(_plan(), {"app-patch"}) == []

    def test_not_a_dict(self):
        assert validate_plan("nope") == ["plan must be a JSON object"]

    def test_missing_goal(self):
        errors = validate_plan(_plan(goal=""), {"app-patch"})
        assert any("goal" in e for e in errors)

    def test_empty_criteria(self):
        errors = validate_plan(_plan(acceptance_criteria=[]), {"app-patch"})
        assert any("acceptance_criteria" in e for e in errors)

    def test_unknown_kind(self):
        errors = validate_plan(_plan(), {"research-report"})
        assert any("not an installed skill" in e for e in errors)

    def test_kind_check_skipped_when_none(self):
        assert validate_plan(_plan(), None) == []

    def test_duplicate_ids(self):
        p = _plan()
        p["subtasks"][1]["id"] = "s1"
        errors = validate_plan(p, {"app-patch"})
        assert any("duplicate" in e for e in errors)

    def test_unknown_dependency(self):
        p = _plan()
        p["subtasks"][1]["depends_on"] = ["s99"]
        errors = validate_plan(p, {"app-patch"})
        assert any("unknown id" in e for e in errors)

    def test_cycle_detected(self):
        p = _plan()
        p["subtasks"][0]["depends_on"] = ["s2"]
        errors = validate_plan(p, {"app-patch"})
        assert any("cycle" in e for e in errors)

    def test_too_many_subtasks(self):
        p = _plan()
        p["subtasks"] = [
            {"id": f"s{i}", "kind": "app-patch", "description": "x", "depends_on": []}
            for i in range(MAX_SUBTASKS + 1)
        ]
        errors = validate_plan(p, {"app-patch"})
        assert any("too many" in e for e in errors)


class TestTopoOrder:
    def test_linear_chain(self):
        subtasks = [
            {"id": "s2", "depends_on": ["s1"]},
            {"id": "s1", "depends_on": []},
            {"id": "s3", "depends_on": ["s2"]},
        ]
        assert topo_order(subtasks) == ["s1", "s2", "s3"]

    def test_parallel_roots(self):
        subtasks = [
            {"id": "b", "depends_on": []},
            {"id": "a", "depends_on": []},
            {"id": "c", "depends_on": ["a", "b"]},
        ]
        assert topo_order(subtasks) == ["a", "b", "c"]

    def test_cycle_returns_none(self):
        subtasks = [
            {"id": "a", "depends_on": ["b"]},
            {"id": "b", "depends_on": ["a"]},
        ]
        assert topo_order(subtasks) is None


class TestDepsSatisfied:
    def test_all_completed(self):
        assert deps_satisfied(["j1", "j2"], {"j1", "j2"}, {})

    def test_missing_dep(self):
        assert not deps_satisfied(["j1", "j2"], {"j1"}, {})

    def test_escalation_retry_counts(self):
        # j2 failed but its escalation retry completed
        assert deps_satisfied(["j1", "j2"], {"j1"}, {"j2": "j9"})

    def test_no_deps(self):
        assert deps_satisfied([], set(), {})


class TestExtractTextEvents:
    def test_task_complete_marker(self):
        events = extract_text_events("did the thing\nTASK_COMPLETE: pushed 2 commits, healthcheck 200")
        assert events == [{"kind": "task_complete", "summary": "pushed 2 commits, healthcheck 200"}]

    def test_task_question_marker(self):
        events = extract_text_events("TASK_QUESTION: which login form?")
        assert events == [{"kind": "task_question", "question": "which login form?"}]

    def test_eval_markers(self):
        assert extract_text_events("EVAL_PASS: all 3 criteria verified")[0]["kind"] == "eval_pass"
        assert extract_text_events("EVAL_FAIL: /stats still 404")[0]["kind"] == "eval_fail"

    def test_plan_block(self):
        plan = _plan()
        text = f"Here's my plan.\n<<<TASK_PLAN\n{json.dumps(plan)}\nTASK_PLAN>>>\n"
        events = extract_text_events(text)
        assert events[0]["kind"] == "task_plan"
        assert events[0]["plan"]["goal"] == plan["goal"]

    def test_malformed_plan_block_ignored(self):
        text = "<<<TASK_PLAN\n{not json\nTASK_PLAN>>>"
        assert extract_text_events(text) == []

    def test_no_markers(self):
        assert extract_text_events("just a normal summary") == []
        assert extract_text_events("") == []

    def test_marker_must_start_line(self):
        # Mid-line mentions (e.g. a session quoting the protocol) don't fire
        events = extract_text_events("I will emit TASK_COMPLETE: later")
        assert events == []

    def test_indented_marker_fires(self):
        events = extract_text_events("   TASK_COMPLETE: done")
        assert events[0]["kind"] == "task_complete"


class TestParseRouteResponse:
    def test_valid(self):
        skill, conf = parse_route_response(
            '{"skill": "app-patch", "confidence": 0.9}', {"app-patch"})
        assert skill == "app-patch" and conf == 0.9

    def test_plan_allowed(self):
        skill, _ = parse_route_response(
            '{"skill": "plan", "confidence": 0.8}', {"plan", "app-patch"})
        assert skill == "plan"

    def test_empty_means_generic(self):
        skill, conf = parse_route_response('{"skill": "", "confidence": 0.2}', {"app-patch"})
        assert skill == "" and conf == 0.2

    def test_unknown_skill_rejected(self):
        skill, conf = parse_route_response(
            '{"skill": "made-up", "confidence": 0.99}', {"app-patch"})
        assert skill == "" and conf == 0.0

    def test_surrounding_prose_tolerated(self):
        skill, _ = parse_route_response(
            'Sure! {"skill": "app-patch", "confidence": 0.7} hope that helps',
            {"app-patch"})
        assert skill == "app-patch"

    def test_garbage(self):
        assert parse_route_response("no json here", {"a"}) == ("", 0.0)
        assert parse_route_response("", {"a"}) == ("", 0.0)
        assert parse_route_response('{"skill": 5}', {"a"}) == ("", 0.0)

    def test_confidence_clamped(self):
        _, conf = parse_route_response('{"skill": "a", "confidence": 7}', {"a"})
        assert conf == 1.0


class TestTriagePlainText:
    def _triage(self, text):
        from src.gateway.telegram_bot import triage_plain_text
        return triage_plain_text(text)

    def test_router_match_is_task(self):
        assert self._triage("update the bingo app to add dark mode") == "task"

    def test_short_question_is_chat(self):
        assert self._triage("what's the capital of France?") == "chat"
        assert self._triage("how do subscriptions renew") == "chat"

    def test_imperative_is_task(self):
        assert self._triage("make me a spreadsheet of all projects and email it") == "task"

    def test_question_matching_router_is_task(self):
        # "why is X broken" matches the self-diagnose rule → task, not chat
        assert self._triage("why is the bingo app broken?") == "task"

    def test_long_question_is_task(self):
        long_q = ("can you " + "x" * 250 + "?")
        assert self._triage(long_q) == "task"
