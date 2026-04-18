"""
Unit tests for src/runner/learning.py pure functions.

Tests only the pure helpers (should_extract, parse_learning_response,
format_audit_excerpt, list_installed_modules). The SDK call in
extract_learning is not tested here; it's integration-tested when the
runner actually executes jobs.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from src.runner.learning import (
    VALID_CATEGORIES,
    format_audit_excerpt,
    list_installed_modules,
    parse_learning_response,
    should_extract,
)


# ── should_extract ──────────────────────────────────────────────────────────


class TestShouldExtract:
    def test_empty_audit(self):
        assert should_extract([]) is False

    def test_only_text_events(self):
        entries = [
            {"kind": "text", "text": "hello"},
            {"kind": "text", "text": "world"},
        ]
        assert should_extract(entries) is False

    def test_only_reads(self):
        entries = [
            {"kind": "tool_use", "tool_name": "Read", "input": {"file_path": "a.py"}},
            {"kind": "tool_use", "tool_name": "Grep", "input": {"pattern": "x"}},
        ]
        assert should_extract(entries) is False

    def test_write_event_triggers(self):
        entries = [
            {"kind": "tool_use", "tool_name": "Read", "input": {}},
            {"kind": "tool_use", "tool_name": "Write", "input": {"file_path": "new.py"}},
        ]
        assert should_extract(entries) is True

    def test_edit_event_triggers(self):
        entries = [
            {"kind": "tool_use", "tool_name": "Edit", "input": {"file_path": "x.py"}},
        ]
        assert should_extract(entries) is True

    def test_bash_alone_does_not_trigger(self):
        # Bash can modify files but we don't treat it as a signal (could be
        # just running tests / grepping). Conservative: only Write/Edit.
        entries = [
            {"kind": "tool_use", "tool_name": "Bash", "input": {"command": "ls"}},
        ]
        assert should_extract(entries) is False

    def test_ignores_non_tool_use_events(self):
        entries = [
            {"kind": "thinking", "text": "writing code"},
            {"kind": "text", "text": "Write the function"},
        ]
        assert should_extract(entries) is False

    def test_missing_tool_name_key(self):
        entries = [
            {"kind": "tool_use"},
        ]
        assert should_extract(entries) is False


# ── parse_learning_response ────────────────────────────────────────────────


class TestParseLearningResponse:
    def test_empty_input(self):
        p = parse_learning_response("")
        assert p.had_learning is False

    def test_whitespace_only(self):
        p = parse_learning_response("   \n  \t  ")
        assert p.had_learning is False

    def test_clean_json_positive(self):
        text = """{
            "had_learning": true,
            "module": "runner",
            "category": "GOTCHA",
            "title": "Example trap",
            "content": "Body content here.",
            "evidence_job_id": "abc12345"
        }"""
        p = parse_learning_response(text)
        assert p.had_learning is True
        assert p.module == "runner"
        assert p.category == "GOTCHA"
        assert p.title == "Example trap"
        assert p.content == "Body content here."
        assert p.evidence_job_id == "abc12345"

    def test_clean_json_negative(self):
        p = parse_learning_response('{"had_learning": false}')
        assert p.had_learning is False

    def test_json_with_markdown_fences(self):
        text = '```json\n{"had_learning": true, "module": "gateway", "category": "DEBUG", "title": "Log location", "content": "Logs at /var/log/x"}\n```'
        p = parse_learning_response(text)
        assert p.had_learning is True
        assert p.module == "gateway"
        assert p.category == "DEBUG"

    def test_json_with_preamble(self):
        text = 'Here is my analysis:\n\n{"had_learning": true, "module": "db", "category": "PATTERN", "title": "Use async_session", "content": "Always use async_session context manager."}\n\nHope that helps!'
        p = parse_learning_response(text)
        assert p.had_learning is True
        assert p.module == "db"

    def test_invalid_json_garbage(self):
        p = parse_learning_response("this is not json at all")
        assert p.had_learning is False

    def test_invalid_json_malformed(self):
        p = parse_learning_response('{"had_learning": true, "module": "r')
        assert p.had_learning is False

    def test_invalid_category_discarded(self):
        text = '{"had_learning": true, "module": "runner", "category": "RANDOM", "title": "X", "content": "Y"}'
        p = parse_learning_response(text)
        assert p.had_learning is False

    def test_missing_had_learning_key_treated_as_false(self):
        text = '{"module": "runner", "category": "GOTCHA", "title": "X", "content": "Y"}'
        p = parse_learning_response(text)
        assert p.had_learning is False

    def test_empty_title_discarded(self):
        text = '{"had_learning": true, "module": "runner", "category": "GOTCHA", "title": "", "content": "Y"}'
        p = parse_learning_response(text)
        assert p.had_learning is False

    def test_empty_content_discarded(self):
        text = '{"had_learning": true, "module": "runner", "category": "GOTCHA", "title": "X", "content": ""}'
        p = parse_learning_response(text)
        assert p.had_learning is False

    def test_category_uppercased(self):
        text = '{"had_learning": true, "module": "runner", "category": "gotcha", "title": "X", "content": "Y"}'
        p = parse_learning_response(text)
        assert p.had_learning is True
        assert p.category == "GOTCHA"

    def test_title_truncated(self):
        long_title = "x" * 300
        text = f'{{"had_learning": true, "module": "runner", "category": "GOTCHA", "title": "{long_title}", "content": "Y"}}'
        p = parse_learning_response(text)
        assert p.had_learning is True
        assert len(p.title) == 200

    def test_all_valid_categories(self):
        for cat in VALID_CATEGORIES:
            text = (
                f'{{"had_learning": true, "module": "runner", "category": "{cat}", '
                f'"title": "X", "content": "Y"}}'
            )
            p = parse_learning_response(text)
            assert p.had_learning is True
            assert p.category == cat


# ── format_audit_excerpt ────────────────────────────────────────────────────


class TestFormatAuditExcerpt:
    def test_empty_returns_placeholder(self):
        assert format_audit_excerpt([]) == "(empty audit log)"

    def test_tool_use_with_file_path(self):
        entries = [
            {"kind": "tool_use", "tool_name": "Write", "input": {"file_path": "src/x.py"}},
        ]
        out = format_audit_excerpt(entries)
        assert "tool_use" in out
        assert "Write" in out
        assert "src/x.py" in out

    def test_tool_use_with_bash_command(self):
        entries = [
            {"kind": "tool_use", "tool_name": "Bash", "input": {"command": "pytest tests/"}},
        ]
        out = format_audit_excerpt(entries)
        assert "Bash" in out
        assert "pytest" in out

    def test_tool_result_redacts_body(self):
        entries = [
            {"kind": "tool_result", "is_error": False, "content": "x" * 1000},
        ]
        out = format_audit_excerpt(entries)
        assert "tool_result" in out
        assert "error=False" in out
        # Body should not leak through
        assert "x" * 500 not in out

    def test_text_truncated(self):
        entries = [
            {"kind": "text", "text": "a" * 1000},
        ]
        out = format_audit_excerpt(entries)
        assert "text" in out
        assert len(out) < 500

    def test_job_failed_included(self):
        entries = [
            {"kind": "job_failed", "error": "Connection refused"},
        ]
        out = format_audit_excerpt(entries)
        assert "job_failed" in out
        assert "Connection refused" in out

    def test_respects_max_entries(self):
        entries = [
            {"kind": "text", "text": f"line{i}"} for i in range(100)
        ]
        out = format_audit_excerpt(entries, max_entries=5)
        # Should include last 5 (line95..line99), not line0
        assert "line99" in out
        assert "line0" not in out


# ── list_installed_modules ──────────────────────────────────────────────────


class TestListInstalledModules:
    def test_missing_dir_returns_empty(self):
        with tempfile.TemporaryDirectory() as td:
            non_existent = Path(td) / "nope"
            assert list_installed_modules(non_existent) == []

    def test_empty_dir_returns_empty(self):
        with tempfile.TemporaryDirectory() as td:
            assert list_installed_modules(Path(td)) == []

    def test_modules_without_context_ignored(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            (base / "alpha").mkdir()
            # No CONTEXT.md
            (base / "beta").mkdir()
            (base / "beta" / "CONTEXT.md").write_text("# beta")
            assert list_installed_modules(base) == ["beta"]

    def test_returns_sorted(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            for name in ("zeta", "alpha", "mu"):
                d = base / name
                d.mkdir()
                (d / "CONTEXT.md").write_text("#")
            assert list_installed_modules(base) == ["alpha", "mu", "zeta"]

    def test_ignores_non_directories(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            (base / "regular_file").write_text("not a module")
            (base / "alpha").mkdir()
            (base / "alpha" / "CONTEXT.md").write_text("#")
            assert list_installed_modules(base) == ["alpha"]
