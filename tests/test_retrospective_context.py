"""Unit tests for context consumption helpers in src/runner/retrospective.py."""

from __future__ import annotations

import json

from src.runner.retrospective import parse_read_events, _normalize_path


class TestParseReadEvents:
    def test_empty_input(self):
        assert parse_read_events([]) == []

    def test_whitespace_lines_skipped(self):
        assert parse_read_events(["", "  ", "\n"]) == []

    def test_malformed_json_skipped(self):
        assert parse_read_events(["not json at all"]) == []

    def test_non_tool_use_skipped(self):
        line = json.dumps({"kind": "text", "job_id": "abc", "text": "hello"})
        assert parse_read_events([line]) == []

    def test_non_read_tool_skipped(self):
        line = json.dumps({
            "kind": "tool_use", "tool_name": "Bash",
            "job_id": "abc", "input": {"command": "ls"},
        })
        assert parse_read_events([line]) == []

    def test_read_event_extracted(self):
        line = json.dumps({
            "kind": "tool_use", "tool_name": "Read",
            "job_id": "job-1", "input": {"file_path": "/tmp/foo.py"},
        })
        result = parse_read_events([line])
        assert result == [("job-1", "/tmp/foo.py")]

    def test_multiple_reads_same_job_deduped(self):
        line = json.dumps({
            "kind": "tool_use", "tool_name": "Read",
            "job_id": "job-1", "input": {"file_path": "/tmp/foo.py"},
        })
        result = parse_read_events([line, line])
        assert result == [("job-1", "/tmp/foo.py")]

    def test_multiple_reads_different_files(self):
        lines = [
            json.dumps({
                "kind": "tool_use", "tool_name": "Read",
                "job_id": "job-1", "input": {"file_path": "/tmp/a.py"},
            }),
            json.dumps({
                "kind": "tool_use", "tool_name": "Read",
                "job_id": "job-1", "input": {"file_path": "/tmp/b.py"},
            }),
        ]
        result = parse_read_events(lines)
        assert result == [("job-1", "/tmp/a.py"), ("job-1", "/tmp/b.py")]

    def test_multiple_jobs(self):
        lines = [
            json.dumps({
                "kind": "tool_use", "tool_name": "Read",
                "job_id": "job-1", "input": {"file_path": "/tmp/a.py"},
            }),
            json.dumps({
                "kind": "tool_use", "tool_name": "Read",
                "job_id": "job-2", "input": {"file_path": "/tmp/a.py"},
            }),
        ]
        result = parse_read_events(lines)
        assert result == [("job-1", "/tmp/a.py"), ("job-2", "/tmp/a.py")]

    def test_missing_job_id_skipped(self):
        line = json.dumps({
            "kind": "tool_use", "tool_name": "Read",
            "input": {"file_path": "/tmp/a.py"},
        })
        assert parse_read_events([line]) == []

    def test_missing_file_path_skipped(self):
        line = json.dumps({
            "kind": "tool_use", "tool_name": "Read",
            "job_id": "job-1", "input": {},
        })
        assert parse_read_events([line]) == []

    def test_missing_input_skipped(self):
        line = json.dumps({
            "kind": "tool_use", "tool_name": "Read",
            "job_id": "job-1",
        })
        assert parse_read_events([line]) == []

    def test_mixed_events(self):
        lines = [
            json.dumps({"kind": "job_started", "job_id": "job-1"}),
            json.dumps({
                "kind": "tool_use", "tool_name": "Read",
                "job_id": "job-1", "input": {"file_path": "/tmp/a.py"},
            }),
            json.dumps({
                "kind": "tool_use", "tool_name": "Bash",
                "job_id": "job-1", "input": {"command": "ls"},
            }),
            json.dumps({
                "kind": "tool_use", "tool_name": "Read",
                "job_id": "job-1", "input": {"file_path": "/tmp/b.py"},
            }),
            json.dumps({"kind": "job_completed", "job_id": "job-1"}),
        ]
        result = parse_read_events(lines)
        assert result == [("job-1", "/tmp/a.py"), ("job-1", "/tmp/b.py")]

    def test_null_input_skipped(self):
        line = json.dumps({
            "kind": "tool_use", "tool_name": "Read",
            "job_id": "job-1", "input": None,
        })
        assert parse_read_events([line]) == []


class TestNormalizePath:
    def test_absolute_path_with_server_root(self):
        root = "/home/user/ai-server"
        assert _normalize_path("/home/user/ai-server/src/models.py", root) == "src/models.py"

    def test_absolute_path_without_server_root(self):
        root = "/home/user/ai-server"
        assert _normalize_path("/other/path/file.py", root) == "/other/path/file.py"

    def test_relative_path_unchanged(self):
        root = "/home/user/ai-server"
        assert _normalize_path("src/models.py", root) == "src/models.py"

    def test_server_root_with_trailing_slash(self):
        root = "/home/user/ai-server/"
        # Path starts with root (including slash), so prefix is stripped
        assert _normalize_path("/home/user/ai-server/src/models.py", root) == "src/models.py"

    def test_server_root_exact_match(self):
        root = "/home/user/ai-server"
        result = _normalize_path("/home/user/ai-server", root)
        assert result == ""

    def test_nested_deep_path(self):
        root = "/Users/user/Library/Application Support/ai-server"
        path = "/Users/user/Library/Application Support/ai-server/.context/modules/runner/CONTEXT.md"
        assert _normalize_path(path, root) == ".context/modules/runner/CONTEXT.md"
