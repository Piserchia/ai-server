"""
Tests for startup orphaned-job reconciliation logic (pure function).

Run: pipenv run pytest tests/test_orphaned_jobs.py -v
"""

from __future__ import annotations

import types
import uuid

from src.models import JobStatus
from src.runner import reconcile
from src.runner.reconcile import (
    ORPHAN_CATEGORY,
    ORPHAN_ERROR,
    _existing_terminal_status,
    orphaned_job_ids,
    stranded_queued_ids,
)


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


class TestExistingTerminalStatus:
    """Idempotency guard: reconcile must not write a second terminal event when
    the crash landed between the event write and the DB commit."""

    def _patch_dir(self, tmp_path, monkeypatch):
        # audit_log_dir is a @property on Settings, so swap the module-level
        # `settings` reference for a fake with a plain attribute.
        monkeypatch.setattr(
            reconcile, "settings", types.SimpleNamespace(audit_log_dir=tmp_path)
        )

    def _write(self, tmp_path, monkeypatch, job_id, lines):
        self._patch_dir(tmp_path, monkeypatch)
        (tmp_path / f"{job_id}.jsonl").write_text("\n".join(lines))

    def test_no_file_returns_none(self, tmp_path, monkeypatch):
        self._patch_dir(tmp_path, monkeypatch)
        assert _existing_terminal_status(uuid.uuid4()) is None

    def test_only_job_started_returns_none(self, tmp_path, monkeypatch):
        jid = uuid.uuid4()
        self._write(tmp_path, monkeypatch, jid, ['{"kind": "job_started"}'])
        assert _existing_terminal_status(jid) is None

    def test_detects_completed(self, tmp_path, monkeypatch):
        jid = uuid.uuid4()
        self._write(tmp_path, monkeypatch, jid,
                    ['{"kind": "job_started"}', '{"kind": "job_completed"}'])
        assert _existing_terminal_status(jid) is JobStatus.completed

    def test_detects_failed(self, tmp_path, monkeypatch):
        jid = uuid.uuid4()
        self._write(tmp_path, monkeypatch, jid,
                    ['{"kind": "job_started"}', '{"kind": "job_failed", "error": "x"}'])
        assert _existing_terminal_status(jid) is JobStatus.failed

    def test_ignores_malformed_lines(self, tmp_path, monkeypatch):
        jid = uuid.uuid4()
        self._write(tmp_path, monkeypatch, jid,
                    ['not json', '', '{"kind": "job_cancelled"}'])
        assert _existing_terminal_status(jid) is JobStatus.cancelled


def test_stranded_queued_ids_flags_missing_from_redis():
    rows = [("a", "queued"), ("b", "queued"), ("c", "running")]
    assert stranded_queued_ids(rows, {"b"}) == ["a"]


def test_stranded_queued_ids_empty_when_all_in_redis():
    assert stranded_queued_ids([("a", "queued")], {"a"}) == []
