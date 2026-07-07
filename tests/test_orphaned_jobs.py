"""
Tests for startup orphaned-job reconciliation logic (pure function).

Run: pipenv run pytest tests/test_orphaned_jobs.py -v
"""

from __future__ import annotations

import uuid

from src.models import JobStatus
from src.runner.reconcile import ORPHAN_CATEGORY, ORPHAN_ERROR, orphaned_job_ids


class TestOrphanedJobIds:
    def test_selects_only_running(self):
        a, b, c, d = (uuid.uuid4() for _ in range(4))
        rows = [
            (a, JobStatus.running.value),
            (b, JobStatus.queued.value),
            (c, JobStatus.completed.value),
            (d, JobStatus.running.value),
        ]
        assert orphaned_job_ids(rows) == [a, d]

    def test_empty_input(self):
        assert orphaned_job_ids([]) == []

    def test_no_running_jobs(self):
        rows = [
            (uuid.uuid4(), JobStatus.completed.value),
            (uuid.uuid4(), JobStatus.failed.value),
            (uuid.uuid4(), JobStatus.cancelled.value),
        ]
        assert orphaned_job_ids(rows) == []

    def test_preserves_order(self):
        ids = [uuid.uuid4() for _ in range(3)]
        rows = [(i, JobStatus.running.value) for i in ids]
        assert orphaned_job_ids(rows) == ids


class TestOrphanConstants:
    def test_category_is_orphaned(self):
        assert ORPHAN_CATEGORY == "orphaned"

    def test_error_message_is_categorizable(self):
        # The error message must classify back to 'orphaned' so aggregation and
        # self-diagnose group these consistently.
        from src.runner.audit_index import categorize_error

        assert categorize_error(ORPHAN_ERROR) == "orphaned"
