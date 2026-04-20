"""Unit tests for src/runner/audit_index.py pure functions."""

from __future__ import annotations

import json

from src.runner.audit_index import (
    _extract_keywords,
    build_index_entry,
    search_index,
)


class TestExtractKeywords:
    def test_empty(self):
        assert _extract_keywords("") == []

    def test_short_words_filtered(self):
        assert _extract_keywords("a an is") == []

    def test_stop_words_filtered(self):
        assert _extract_keywords("the and for was") == []

    def test_meaningful_words(self):
        result = _extract_keywords("Fixed database connection timeout error")
        assert "fixed" in result
        assert "database" in result
        assert "connection" in result
        assert "timeout" in result
        assert "error" in result

    def test_max_keywords(self):
        text = " ".join(f"word{i}" for i in range(20))
        result = _extract_keywords(text, max_keywords=5)
        assert len(result) == 5

    def test_deduplication(self):
        result = _extract_keywords("error error error timeout timeout")
        assert result.count("error") == 1
        assert result.count("timeout") == 1

    def test_case_insensitive(self):
        result = _extract_keywords("Error ERROR error")
        assert len(result) == 1


class TestBuildIndexEntry:
    def test_empty_lines(self):
        assert build_index_entry("job-1", []) is None

    def test_basic_job(self):
        lines = [
            json.dumps({
                "kind": "job_started",
                "skill": "app-patch",
                "model": "claude-sonnet-4-6",
                "effort": "medium",
            }),
            json.dumps({"kind": "job_completed"}),
        ]
        entry = build_index_entry("job-1", lines, "Fixed the login bug")
        assert entry is not None
        assert entry.job_id == "job-1"
        assert entry.skill == "app-patch"
        assert entry.model == "claude-sonnet-4-6"
        assert entry.status == "completed"
        assert "login" in entry.keywords

    def test_failed_job(self):
        lines = [
            json.dumps({
                "kind": "job_started",
                "skill": "research-report",
                "model": "claude-opus-4-7",
                "effort": "high",
            }),
            json.dumps({
                "kind": "job_failed",
                "error": "QuotaExhausted: rate limit hit\nstack trace...",
            }),
        ]
        entry = build_index_entry("job-2", lines)
        assert entry is not None
        assert entry.status == "failed"
        assert entry.error_first_line == "QuotaExhausted: rate limit hit"

    def test_cancelled_job(self):
        lines = [
            json.dumps({"kind": "job_started", "skill": "chat", "model": "", "effort": ""}),
            json.dumps({"kind": "job_cancelled"}),
        ]
        entry = build_index_entry("job-3", lines)
        assert entry is not None
        assert entry.status == "cancelled"

    def test_malformed_lines_skipped(self):
        lines = ["not json", '{"kind": "job_started", "skill": "x", "model": "m", "effort": "e"}']
        entry = build_index_entry("job-4", lines)
        assert entry is not None
        assert entry.skill == "x"


class TestSearchIndex:
    def test_nonexistent_file(self, tmp_path):
        result = search_index(tmp_path / "nonexistent.jsonl")
        assert result == []

    def test_filter_by_skill(self, tmp_path):
        index_file = tmp_path / "INDEX.jsonl"
        index_file.write_text("\n".join([
            json.dumps({"skill": "app-patch", "status": "completed", "keywords": []}),
            json.dumps({"skill": "chat", "status": "completed", "keywords": []}),
        ]))
        result = search_index(index_file, skill="app-patch")
        assert len(result) == 1
        assert result[0]["skill"] == "app-patch"

    def test_filter_by_status(self, tmp_path):
        index_file = tmp_path / "INDEX.jsonl"
        index_file.write_text("\n".join([
            json.dumps({"skill": "x", "status": "completed", "keywords": []}),
            json.dumps({"skill": "x", "status": "failed", "keywords": [], "error_first_line": "boom"}),
        ]))
        result = search_index(index_file, status="failed")
        assert len(result) == 1
        assert result[0]["status"] == "failed"

    def test_filter_by_keyword(self, tmp_path):
        index_file = tmp_path / "INDEX.jsonl"
        index_file.write_text("\n".join([
            json.dumps({"skill": "x", "status": "completed", "keywords": ["database", "timeout"]}),
            json.dumps({"skill": "x", "status": "completed", "keywords": ["login", "auth"]}),
        ]))
        result = search_index(index_file, keyword="timeout")
        assert len(result) == 1
        assert "timeout" in result[0]["keywords"]

    def test_keyword_in_error_line(self, tmp_path):
        index_file = tmp_path / "INDEX.jsonl"
        index_file.write_text(json.dumps({
            "skill": "x", "status": "failed",
            "keywords": [], "error_first_line": "ConnectionRefused on port 5432",
        }))
        result = search_index(index_file, keyword="ConnectionRefused")
        assert len(result) == 1
