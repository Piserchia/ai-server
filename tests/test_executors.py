"""Tests for runner/executors.py — the container execution lane (P1).

Covers the pure parts: docker command construction and stream-json → audit
event mapping (the executor-parity contract). No docker, no network.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.runner.executors import (
    build_container_command,
    container_name_for_job,
    parse_stream_json_line,
)


def _cmd(**overrides):
    kwargs = dict(
        job_id="abcd1234-ffff",
        prompt="fix the bug",
        system_prompt="You are working inside the assistant server.",
        model="claude-opus-4-7",
        permission_mode="acceptEdits",
        allowed_tools=["Read", "Write", "Bash"],
        max_turns=60,
        workspace=Path("/srv/volumes/workspaces/abcd1234-ai-server"),
        context_dir=Path("/srv/.context"),
        image="ai-server-agent:latest",
        runtime="docker",
        memory="4g",
        cpus="2",
    )
    kwargs.update(overrides)
    return build_container_command(**kwargs)


class TestBuildContainerCommand:
    def test_basic_shape(self):
        cmd = _cmd()
        assert cmd[0] == "docker"
        assert "run" in cmd and "--rm" in cmd
        assert container_name_for_job("abcd1234-ffff") == "ai-job-abcd1234"
        assert "ai-job-abcd1234" in cmd

    def test_mounts(self):
        cmd = _cmd()
        joined = " ".join(cmd)
        assert "/srv/volumes/workspaces/abcd1234-ai-server:/work" in joined
        assert "/srv/.context:/ctx:ro" in joined      # context is read-only
        assert ["-w", "/work"] == cmd[cmd.index("-w"):cmd.index("-w") + 2]

    def test_oauth_env_passthrough_no_api_key(self):
        cmd = _cmd()
        assert "CLAUDE_CODE_OAUTH_TOKEN" in cmd
        assert not any("ANTHROPIC_API_KEY" in c for c in cmd)
        # token VALUE must never appear in argv (comes via env passthrough)
        assert not any(c.startswith("CLAUDE_CODE_OAUTH_TOKEN=") for c in cmd)

    def test_claude_invocation(self):
        cmd = _cmd()
        i = cmd.index("claude")
        assert cmd[i + 1 : i + 3] == ["-p", "fix the bug"]
        assert "stream-json" in cmd
        assert "--permission-mode" in cmd
        assert "acceptEdits" in cmd
        assert "--model" in cmd and "claude-opus-4-7" in cmd
        assert "--allowedTools" in cmd and "Read,Write,Bash" in cmd
        assert "--max-turns" in cmd and "60" in cmd

    def test_optional_fields_omitted(self):
        cmd = _cmd(model="", max_turns=None, allowed_tools=[])
        assert "--model" not in cmd
        assert "--max-turns" not in cmd
        assert "--allowedTools" not in cmd

    def test_resource_limits(self):
        cmd = _cmd(memory="8g", cpus="4")
        assert "--memory" in cmd and "8g" in cmd
        assert "--cpus" in cmd and "4" in cmd


class TestParseStreamJson:
    def test_assistant_text(self):
        line = json.dumps({
            "type": "assistant",
            "message": {"content": [{"type": "text", "text": "hello"}]},
        })
        events = parse_stream_json_line(line)
        assert events == [{"kind": "text", "text": "hello"}]

    def test_assistant_tool_use(self):
        line = json.dumps({
            "type": "assistant",
            "message": {"content": [
                {"type": "tool_use", "name": "Bash", "id": "tu_1",
                 "input": {"command": "ls"}},
            ]},
        })
        events = parse_stream_json_line(line)
        assert events[0]["kind"] == "tool_use"
        assert events[0]["tool_name"] == "Bash"
        assert events[0]["tool_use_id"] == "tu_1"
        assert events[0]["input"] == {"command": "ls"}

    def test_assistant_thinking(self):
        line = json.dumps({
            "type": "assistant",
            "message": {"content": [{"type": "thinking", "thinking": "hmm"}]},
        })
        assert parse_stream_json_line(line) == [{"kind": "thinking", "text": "hmm"}]

    def test_user_tool_result(self):
        line = json.dumps({
            "type": "user",
            "message": {"content": [
                {"type": "tool_result", "tool_use_id": "tu_1",
                 "content": "ok", "is_error": False},
            ]},
        })
        events = parse_stream_json_line(line)
        assert events[0]["kind"] == "tool_result"
        assert events[0]["tool_use_id"] == "tu_1"
        assert events[0]["is_error"] is False

    def test_result_event(self):
        line = json.dumps({
            "type": "result", "subtype": "success",
            "result": "final answer", "usage": {"input_tokens": 10},
            "is_error": False,
        })
        events = parse_stream_json_line(line)
        assert events[0]["kind"] == "result"
        assert events[0]["result"] == "final answer"
        assert events[0]["usage"] == {"input_tokens": 10}

    def test_multiple_blocks_one_line(self):
        line = json.dumps({
            "type": "assistant",
            "message": {"content": [
                {"type": "text", "text": "a"},
                {"type": "tool_use", "name": "Read", "id": "tu_2", "input": {}},
            ]},
        })
        events = parse_stream_json_line(line)
        assert [e["kind"] for e in events] == ["text", "tool_use"]

    def test_garbage_lines_ignored(self):
        assert parse_stream_json_line("") == []
        assert parse_stream_json_line("not json") == []
        assert parse_stream_json_line("{broken") == []
        assert parse_stream_json_line('{"type": "unknown_future_thing"}') == []
        assert parse_stream_json_line('{"type": "system", "subtype": "init"}') == []

    def test_empty_text_blocks_skipped(self):
        line = json.dumps({
            "type": "assistant",
            "message": {"content": [{"type": "text", "text": ""}]},
        })
        assert parse_stream_json_line(line) == []
