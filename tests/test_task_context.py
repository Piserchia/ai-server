"""Unit tests for task context building helpers."""

from __future__ import annotations

from src.models import TaskStatus
from src.runner.session import format_task_turns


class TestTaskStatus:
    def test_active_not_terminal(self):
        assert TaskStatus.active.value == "active"

    def test_completed_value(self):
        assert TaskStatus.completed.value == "completed"

    def test_all_statuses_exist(self):
        assert len(TaskStatus) == 5  # active, awaiting_user, pending_approval, completed, failed


class TestFormatTaskTurns:
    def test_empty_turns(self):
        assert format_task_turns([]) == ""

    def test_single_user_turn(self):
        turns = [{"turn_number": 1, "role": "user", "content": "fix the bug", "job_id": None}]
        result = format_task_turns(turns)
        assert "Turn 1 (user)" in result
        assert "fix the bug" in result

    def test_assistant_turn_with_job_id(self):
        turns = [
            {"turn_number": 1, "role": "user", "content": "fix the bug", "job_id": None},
            {"turn_number": 2, "role": "assistant", "content": "Fixed it.", "job_id": "abcd1234-5678-90ef-1234-567890abcdef"},
        ]
        result = format_task_turns(turns)
        assert "Turn 2 (assistant, job abcd1234)" in result
        assert "Fixed it." in result

    def test_long_content_truncated(self):
        long_text = "x" * 1000
        turns = [{"turn_number": 1, "role": "user", "content": long_text, "job_id": None}]
        result = format_task_turns(turns)
        assert len(result) < 600  # truncated at 500 + overhead
        assert "..." in result

    def test_multiple_turns(self):
        turns = [
            {"turn_number": 1, "role": "user", "content": "question", "job_id": None},
            {"turn_number": 2, "role": "assistant", "content": "answer", "job_id": "abc12345-0000-0000-0000-000000000000"},
            {"turn_number": 3, "role": "user", "content": "follow up", "job_id": None},
        ]
        result = format_task_turns(turns)
        assert result.count("Turn") == 3

    def test_system_turn(self):
        turns = [{"turn_number": 1, "role": "system", "content": "User approved.", "job_id": None}]
        result = format_task_turns(turns)
        assert "system" in result
