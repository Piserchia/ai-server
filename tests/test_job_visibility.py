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
