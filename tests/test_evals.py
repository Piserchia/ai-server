"""
Unit tests for the behavioural eval harness pure logic (evals/harness.py).

The orchestration in evals/run.py needs a live stack + subscription auth and is
not tested here; this covers the deterministic parts that decide pass/fail.

Run: pipenv run pytest tests/test_evals.py -v
"""

from __future__ import annotations

from pathlib import Path

import pytest

from evals.harness import (
    CaseResult,
    EvalCase,
    build_judge_prompt,
    format_results_markdown,
    is_regression,
    load_cases,
    parse_judge_response,
)

CASES_DIR = Path(__file__).parent.parent / "evals" / "cases"


class TestLoadCases:
    def test_loads_shipped_chat_cases(self):
        cases = load_cases(CASES_DIR / "chat.yml")
        assert len(cases) >= 1
        assert all(c.skill == "chat" for c in cases)
        assert all(c.input and c.rubric for c in cases)

    def test_all_shipped_case_files_parse(self):
        for f in CASES_DIR.glob("*.yml"):
            cases = load_cases(f)
            assert cases, f"{f.name} produced no cases"
            for c in cases:
                assert c.name and c.input
                assert isinstance(c.rubric, list)


class TestParseJudgeResponse:
    def test_well_formed(self):
        text = "Some reasoning.\nSCORE: 4\nVERDICT: pass\nNOTES: solid, minor nit"
        r = parse_judge_response(text)
        assert r.score == 4 and r.verdict == "pass" and "solid" in r.notes

    def test_case_insensitive_and_whitespace(self):
        r = parse_judge_response("score: 2\nverdict: FAIL\nnotes:   missed the bug")
        assert r.score == 2 and r.verdict == "fail" and r.notes == "missed the bug"

    def test_missing_verdict_infers_from_score(self):
        assert parse_judge_response("SCORE: 5").verdict == "pass"
        assert parse_judge_response("SCORE: 1").verdict == "fail"

    def test_missing_score_raises(self):
        with pytest.raises(ValueError):
            parse_judge_response("VERDICT: pass\nNOTES: no score here")


class TestIsRegression:
    def test_no_baseline_never_regresses(self):
        assert is_regression(None, 1) is False

    def test_drop_of_one_is_regression(self):
        assert is_regression(5, 4) is True

    def test_equal_is_not_regression(self):
        assert is_regression(4, 4) is False

    def test_improvement_is_not_regression(self):
        assert is_regression(3, 5) is False

    def test_custom_threshold(self):
        assert is_regression(5, 4, threshold=2) is False
        assert is_regression(5, 3, threshold=2) is True


class TestBuildJudgePrompt:
    def test_includes_input_output_and_rubric(self):
        case = EvalCase(skill="chat", name="x", input="ping?", rubric=["says pong"])
        prompt = build_judge_prompt(case, "pong")
        assert "ping?" in prompt and "pong" in prompt and "says pong" in prompt
        assert "SCORE:" in prompt and "VERDICT:" in prompt


class TestFormatResults:
    def test_marks_regressions_and_errors(self):
        results = [
            CaseResult("chat", "a", 5, "pass", "great", 5, False),
            CaseResult("chat", "b", 3, "fail", "worse", 5, True),
            CaseResult("chat", "c", None, "error", "", None, False, error="boom"),
        ]
        md = format_results_markdown("chat", results, "2026-07-06T00:00:00Z")
        assert "1 regression(s)" in md and "1 error(s)" in md
        assert "⚠️" in md and "boom" in md
