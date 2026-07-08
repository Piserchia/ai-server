"""
Behavioural skill-eval harness — pure logic (no I/O, no LLM, no DB).

The orchestration lives in ``evals/run.py``; everything here is deterministic and
unit-tested (``tests/test_evals.py``): loading eval cases, building the LLM-judge
prompt, parsing the judge's verdict, and deciding whether a score is a regression
against a stored baseline.

An eval *case* is one input to a skill plus a rubric describing what a good output
looks like. The judge (an Opus session) scores the skill's actual output against
the rubric 1–5; a drop of ``REGRESSION_THRESHOLD`` or more below the case's baseline
is flagged as a regression.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

REGRESSION_THRESHOLD = 1  # a current score <= baseline - this is a regression


@dataclass
class EvalCase:
    skill: str
    name: str
    input: str
    rubric: list[str]
    baseline_score: float | None = None


@dataclass
class JudgeResult:
    score: int
    verdict: str          # "pass" | "fail"
    notes: str


@dataclass
class CaseResult:
    skill: str
    case: str
    score: int | None
    verdict: str
    notes: str
    baseline: float | None
    is_regression: bool
    error: str | None = None


def load_cases(path: str | Path) -> list[EvalCase]:
    """Parse an ``evals/cases/<skill>.yml`` file into EvalCase objects.

    File shape::

        skill: chat
        cases:
          - name: factual-answer
            input: "What is the capital of France?"
            rubric:
              - "Names Paris"
            baseline_score: 5
    """
    data = yaml.safe_load(Path(path).read_text()) or {}
    skill = data.get("skill") or Path(path).stem
    cases: list[EvalCase] = []
    for raw in data.get("cases", []):
        cases.append(
            EvalCase(
                skill=skill,
                name=raw["name"],
                input=raw["input"],
                rubric=list(raw.get("rubric", [])),
                baseline_score=raw.get("baseline_score"),
            )
        )
    return cases


def build_judge_prompt(case: EvalCase, output: str) -> str:
    """Construct the rubric-scoring prompt for the LLM judge."""
    rubric_lines = "\n".join(f"- {c}" for c in case.rubric) or "- (no explicit criteria)"
    return f"""You are grading the output of an AI skill named "{case.skill}" against a rubric.

## The input the skill was given
{case.input}

## The skill's actual output
{output or "(the skill produced no output)"}

## Rubric — what a good output must satisfy
{rubric_lines}

Grade how well the output satisfies the rubric. Judge substance against the
criteria, not exact wording. Then end your reply with EXACTLY these three lines
and nothing after them:

SCORE: <integer 1-5>
VERDICT: <pass|fail>
NOTES: <one short line explaining the score>
"""


_SCORE_RE = re.compile(r"^\s*SCORE:\s*([1-5])\b", re.IGNORECASE | re.MULTILINE)
_VERDICT_RE = re.compile(r"^\s*VERDICT:\s*(pass|fail)\b", re.IGNORECASE | re.MULTILINE)
_NOTES_RE = re.compile(r"^\s*NOTES:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)


def parse_judge_response(text: str) -> JudgeResult:
    """Extract SCORE/VERDICT/NOTES from the judge's reply.

    Raises ValueError if a score cannot be found (a malformed judge response should
    surface loudly, not be silently scored 0).
    """
    score_m = _SCORE_RE.search(text or "")
    if not score_m:
        raise ValueError("judge response missing SCORE line")
    score = int(score_m.group(1))
    verdict_m = _VERDICT_RE.search(text or "")
    verdict = verdict_m.group(1).lower() if verdict_m else ("pass" if score >= 3 else "fail")
    notes_m = _NOTES_RE.search(text or "")
    notes = notes_m.group(1).strip() if notes_m else ""
    return JudgeResult(score=score, verdict=verdict, notes=notes)


def is_regression(baseline: float | None, current: int, threshold: int = REGRESSION_THRESHOLD) -> bool:
    """True when there is a baseline and the current score dropped by >= threshold."""
    if baseline is None:
        return False
    return current <= baseline - threshold


def format_results_markdown(skill: str, results: list[CaseResult], when: str) -> str:
    """Render a results report. ``when`` is a caller-supplied timestamp string."""
    lines = [f"# Eval results — {skill} — {when}", ""]
    regressions = [r for r in results if r.is_regression]
    errored = [r for r in results if r.error]
    lines.append(
        f"**{len(results)} cases** · "
        f"{len(regressions)} regression(s) · {len(errored)} error(s)"
    )
    lines.append("")
    lines.append("| case | score | baseline | verdict | Δ | notes |")
    lines.append("|---|---|---|---|---|---|")
    for r in results:
        if r.error:
            lines.append(f"| {r.case} | — | {_fmt(r.baseline)} | ERROR | — | {r.error} |")
            continue
        delta = "" if r.baseline is None else f"{r.score - r.baseline:+g}"
        flag = " ⚠️" if r.is_regression else ""
        lines.append(
            f"| {r.case} | {r.score} | {_fmt(r.baseline)} | {r.verdict} | "
            f"{delta}{flag} | {r.notes} |"
        )
    return "\n".join(lines) + "\n"


def _fmt(v: float | None) -> str:
    return "—" if v is None else f"{v:g}"
