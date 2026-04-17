"""
Tests for MCP tool pure functions. No DB, no Redis, no SDK -- just logic.

Run: pipenv run pytest tests/test_mcp_tools.py -v
"""

from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.runner.mcp_dispatch import _validate_enqueue_args
from src.runner.mcp_projects import _format_project, _read_log_tail


# ── _format_project tests ─────────────────────────────────────────────────


class TestFormatProject:
    def test_basic_format(self) -> None:
        row = {
            "slug": "my-app",
            "subdomain": "my-app.example.com",
            "type": "service",
            "port": 3000,
            "last_healthy_at": None,
        }
        result = _format_project(row)
        assert result == {
            "slug": "my-app",
            "subdomain": "my-app.example.com",
            "type": "service",
            "port": 3000,
            "last_healthy_at": None,
        }

    def test_datetime_formatted_as_iso(self) -> None:
        dt = datetime(2026, 4, 17, 12, 30, 0, tzinfo=timezone.utc)
        row = {
            "slug": "test",
            "subdomain": "test.example.com",
            "type": "static",
            "port": None,
            "last_healthy_at": dt,
        }
        result = _format_project(row)
        assert result["last_healthy_at"] == "2026-04-17T12:30:00+00:00"

    def test_none_last_healthy_at(self) -> None:
        row = {
            "slug": "test",
            "subdomain": "test.example.com",
            "type": "api",
            "port": 8080,
            "last_healthy_at": None,
        }
        result = _format_project(row)
        assert result["last_healthy_at"] is None

    def test_port_none_preserved(self) -> None:
        row = {
            "slug": "static-site",
            "subdomain": "blog.example.com",
            "type": "static",
            "port": None,
            "last_healthy_at": None,
        }
        result = _format_project(row)
        assert result["port"] is None

    def test_empty_row_defaults(self) -> None:
        result = _format_project({})
        assert result["slug"] == ""
        assert result["subdomain"] == ""
        assert result["type"] == ""
        assert result["port"] is None
        assert result["last_healthy_at"] is None

    def test_string_fields_coerced(self) -> None:
        row = {
            "slug": 123,
            "subdomain": 456,
            "type": 789,
            "port": 3000,
            "last_healthy_at": None,
        }
        result = _format_project(row)
        assert result["slug"] == "123"
        assert result["subdomain"] == "456"
        assert result["type"] == "789"


# ── _read_log_tail tests ──────────────────────────────────────────────────


class TestReadLogTail:
    def test_file_not_found(self) -> None:
        result = _read_log_tail(Path("/nonexistent/path/to/log"))
        assert result == "No log file found."

    def test_read_full_file(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            f.write("line1\nline2\nline3\n")
            f.flush()
            result = _read_log_tail(Path(f.name), n=100)
        assert "line1" in result
        assert "line2" in result
        assert "line3" in result

    def test_read_tail_only(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            for i in range(20):
                f.write(f"line-{i}\n")
            f.flush()
            result = _read_log_tail(Path(f.name), n=5)
        lines = result.strip().splitlines()
        assert len(lines) == 5
        assert lines[0] == "line-15"
        assert lines[-1] == "line-19"

    def test_n_larger_than_file(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            f.write("only-line\n")
            f.flush()
            result = _read_log_tail(Path(f.name), n=1000)
        assert "only-line" in result

    def test_empty_file(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            f.flush()
            result = _read_log_tail(Path(f.name), n=10)
        assert result == ""

    def test_n_equals_one(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            f.write("first\nsecond\nthird\n")
            f.flush()
            result = _read_log_tail(Path(f.name), n=1)
        lines = result.strip().splitlines()
        assert len(lines) == 1
        assert lines[0] == "third"


# ── _validate_enqueue_args tests ──────────────────────────────────────────


class TestValidateEnqueueArgs:
    def test_valid_args(self) -> None:
        errors = _validate_enqueue_args("task", "do the thing")
        assert errors == []

    def test_empty_kind(self) -> None:
        errors = _validate_enqueue_args("", "do the thing")
        assert len(errors) == 1
        assert "kind" in errors[0]

    def test_empty_description(self) -> None:
        errors = _validate_enqueue_args("task", "")
        assert len(errors) == 1
        assert "description" in errors[0]

    def test_both_empty(self) -> None:
        errors = _validate_enqueue_args("", "")
        assert len(errors) == 2

    def test_whitespace_only_kind(self) -> None:
        errors = _validate_enqueue_args("   ", "valid description")
        assert len(errors) == 1
        assert "kind" in errors[0]

    def test_whitespace_only_description(self) -> None:
        errors = _validate_enqueue_args("task", "   ")
        assert len(errors) == 1
        assert "description" in errors[0]

    def test_non_string_kind(self) -> None:
        errors = _validate_enqueue_args(123, "valid description")  # type: ignore[arg-type]
        assert len(errors) == 1
        assert "kind" in errors[0]

    def test_non_string_description(self) -> None:
        errors = _validate_enqueue_args("task", None)  # type: ignore[arg-type]
        assert len(errors) == 1
        assert "description" in errors[0]

    def test_valid_real_kinds(self) -> None:
        for kind in ("task", "research_report", "app_patch", "self_diagnose"):
            assert _validate_enqueue_args(kind, "do something") == []
