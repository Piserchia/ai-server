"""
Tests for the enqueue visibility race handling in the runner's job loop
(BLPOP returns an id before the INSERTing transaction's commit is visible).

Covers the pure decision helper `note_missing_job` (retry exhausted → requeue
tail once → drop for good) and the retry-delay schedule contract.

Run: pipenv run pytest tests/test_job_visibility.py -v
"""

from __future__ import annotations

from src.runner.main import _JOB_FETCH_DELAYS, note_missing_job


class TestNoteMissingJob:
    def test_first_miss_requeues_and_records(self):
        requeued: set[str] = set()
        assert note_missing_job("job-a", requeued) == "requeue"
        assert "job-a" in requeued

    def test_second_miss_drops_and_clears(self):
        requeued = {"job-a"}
        assert note_missing_job("job-a", requeued) == "drop"
        assert "job-a" not in requeued  # cleared — set stays bounded

    def test_ids_tracked_independently(self):
        requeued: set[str] = set()
        assert note_missing_job("job-a", requeued) == "requeue"
        assert note_missing_job("job-b", requeued) == "requeue"
        assert note_missing_job("job-a", requeued) == "drop"
        # job-b still awaiting its second chance; job-a fully forgotten
        assert requeued == {"job-b"}

    def test_no_infinite_ping_pong(self):
        """A truly-deleted row gets exactly one requeue, then the drop clears
        state. A THIRD appearance can only come from an external manual RPUSH,
        which deserves a fresh requeue cycle — not a permanent blacklist."""
        requeued: set[str] = set()
        assert note_missing_job("job-a", requeued) == "requeue"
        assert note_missing_job("job-a", requeued) == "drop"
        assert note_missing_job("job-a", requeued) == "requeue"

    def test_found_row_clears_via_discard(self):
        """The found path in _process_job discards the id so a requeued job
        whose row appeared leaves no residue behind."""
        requeued: set[str] = set()
        note_missing_job("job-a", requeued)
        requeued.discard("job-a")  # what _process_job does on found
        assert note_missing_job("job-a", requeued) == "requeue"


class TestFetchRetrySchedule:
    def test_first_attempt_is_immediate(self):
        assert _JOB_FETCH_DELAYS[0] == 0.0

    def test_retries_span_about_two_seconds(self):
        # The race window is sub-ms; ~2s of retries is orders of magnitude of
        # slack without stalling the semaphore slot noticeably.
        assert 1.5 <= sum(_JOB_FETCH_DELAYS) <= 2.5

    def test_a_few_retries(self):
        # "retry a few times": at least 3 delayed attempts after the immediate one.
        assert len([d for d in _JOB_FETCH_DELAYS if d > 0]) >= 3


def test_job_completed_carries_cost_and_turns():
    """B3: the `job_completed` audit event keeps its C14 fields byte-for-byte
    (`duration_seconds`, `usage`, + T4's `provider`/`model_served`/
    `terminal_reason`) and gains `num_turns, duration_api_ms, cost_usd_list,
    sdk_cost_usd, stop_reason` — the reconcile script reads both cost figures
    from the JSONL. Source pin on the one `job_completed` append in
    `run_session` (behaviour is covered in tests/test_result_capture.py)."""
    import ast
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1] / "src" / "runner" / "session.py").read_text()
    run_session = next(n for n in ast.walk(ast.parse(src))
                       if isinstance(n, ast.AsyncFunctionDef) and n.name == "run_session")
    calls = [n for n in ast.walk(run_session) if isinstance(n, ast.Call)
             and ast.unparse(n.func) == "audit_log.append"
             and len(n.args) >= 2 and ast.unparse(n.args[1]) == "'job_completed'"]
    assert len(calls) == 1
    keywords = {k.arg for k in calls[0].keywords}
    assert {"duration_seconds", "usage", "provider", "model_served", "terminal_reason"} <= keywords
    assert {"num_turns", "duration_api_ms", "cost_usd_list", "sdk_cost_usd", "stop_reason"} <= keywords
