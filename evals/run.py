"""
Behavioural skill-eval runner (on-demand, NOT part of pytest / CI).

For each eval case it: enqueues the skill as a real job, waits for the runner to
finish it, reads the job's summary, and asks an Opus LLM-judge to score the output
against the case's rubric. Scores are compared to each case's stored baseline; a
drop of >= REGRESSION_THRESHOLD is flagged and makes the process exit non-zero, so
`review-and-improve` (or a human) can gate a skill change on "no regressions".

Requires the full stack up (runner consuming the queue, Postgres, Redis) and the
same subscription auth the runner uses — hence it is a manual/local gate, not CI.

Usage:
    python -m evals.run --skill chat
    python -m evals.run --all
    python -m evals.run --skill chat --update-baseline   # write current scores as new baselines
"""

from __future__ import annotations

import argparse
import asyncio
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import yaml

from src import audit_log
from src.config import settings
from src.db import async_session
from src.gateway.jobs import enqueue_job
from src.models import Job

from evals.harness import (
    CaseResult,
    EvalCase,
    build_judge_prompt,
    format_results_markdown,
    is_regression,
    load_cases,
    parse_judge_response,
)

CASES_DIR = Path(__file__).parent / "cases"
RESULTS_DIR = Path(__file__).parent / "results"
TERMINAL = {"completed", "failed", "cancelled"}
JUDGE_MODEL = "claude-opus-4-7"


async def _wait_for_job(job_id: uuid.UUID, timeout_s: int) -> Job:
    """Poll the Job row until it reaches a terminal status or the timeout elapses."""
    deadline = asyncio.get_event_loop().time() + timeout_s
    while True:
        async with async_session() as s:
            job = await s.get(Job, job_id)
        if job is not None and job.status in TERMINAL:
            return job
        if asyncio.get_event_loop().time() > deadline:
            raise TimeoutError(f"job {job_id} did not finish within {timeout_s}s")
        await asyncio.sleep(3)


def _read_output(job: Job) -> str:
    """Best output text for the job: summary file → result.summary → error_message."""
    sp = audit_log.summary_path(job.id)
    if sp.exists():
        return sp.read_text()
    if job.result and isinstance(job.result, dict) and job.result.get("summary"):
        return str(job.result["summary"])
    return job.error_message or ""


def _run_judge(prompt: str, timeout_s: int = 120) -> str:
    """Invoke the LLM judge via the subscription-auth `claude` CLI (headless)."""
    proc = subprocess.run(
        ["claude", "-p", prompt, "--model", JUDGE_MODEL],
        capture_output=True,
        text=True,
        timeout=timeout_s,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"judge CLI failed: {proc.stderr[:300]}")
    return proc.stdout


async def _run_case(case: EvalCase, job_timeout_s: int) -> CaseResult:
    try:
        job = await enqueue_job(case.input, kind=case.skill, created_by="eval")
        finished = await _wait_for_job(job.id, job_timeout_s)
        output = _read_output(finished)
        judged = parse_judge_response(_run_judge(build_judge_prompt(case, output)))
        return CaseResult(
            skill=case.skill,
            case=case.name,
            score=judged.score,
            verdict=judged.verdict,
            notes=judged.notes,
            baseline=case.baseline_score,
            is_regression=is_regression(case.baseline_score, judged.score),
        )
    except Exception as exc:  # noqa: BLE001 — one bad case shouldn't abort the run
        return CaseResult(
            skill=case.skill, case=case.name, score=None, verdict="error",
            notes="", baseline=case.baseline_score, is_regression=False,
            error=str(exc)[:200],
        )


def _update_baselines(case_file: Path, results: list[CaseResult]) -> None:
    """Rewrite baseline_score in the case file to the freshly measured scores."""
    data = yaml.safe_load(case_file.read_text()) or {}
    by_name = {r.case: r for r in results if r.score is not None}
    for raw in data.get("cases", []):
        r = by_name.get(raw["name"])
        if r is not None:
            raw["baseline_score"] = r.score
    case_file.write_text(yaml.safe_dump(data, sort_keys=False))


async def _run_skill(skill: str, job_timeout_s: int, update_baseline: bool) -> list[CaseResult]:
    case_file = CASES_DIR / f"{skill}.yml"
    if not case_file.exists():
        print(f"no eval cases for skill {skill!r} ({case_file})", file=sys.stderr)
        return []
    cases = load_cases(case_file)
    results = [await _run_case(c, job_timeout_s) for c in cases]

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    when = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    md = format_results_markdown(skill, results, when)
    out_path = RESULTS_DIR / f"{when[:10]}-{skill}.md"
    out_path.write_text(md)
    print(md)
    print(f"→ {out_path}")

    if update_baseline:
        _update_baselines(case_file, results)
        print(f"updated baselines in {case_file}")
    return results


def _discover_skills() -> list[str]:
    return sorted(p.stem for p in CASES_DIR.glob("*.yml"))


async def _main_async(args) -> int:
    skills = _discover_skills() if args.all else [args.skill]
    all_results: list[CaseResult] = []
    for skill in skills:
        all_results += await _run_skill(skill, args.timeout, args.update_baseline)
    regressions = [r for r in all_results if r.is_regression]
    if regressions:
        print(f"\n⚠️  {len(regressions)} regression(s): "
              + ", ".join(f"{r.skill}/{r.case}" for r in regressions))
        return 1
    print("\n✅ no regressions")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Run behavioural skill evals.")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--skill", help="skill name (matches evals/cases/<skill>.yml)")
    g.add_argument("--all", action="store_true", help="run every skill with a case file")
    p.add_argument("--timeout", type=int, default=900, help="per-job timeout seconds")
    p.add_argument("--update-baseline", action="store_true",
                   help="write the measured scores back as the new baselines")
    args = p.parse_args()
    return asyncio.run(_main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
