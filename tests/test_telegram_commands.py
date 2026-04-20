"""Unit tests for Telegram command helpers."""

from __future__ import annotations

from src.gateway.telegram_bot import _esc_md, parse_flags


class TestEscMd:
    def test_no_special_chars(self):
        assert _esc_md("hello world") == "hello world"

    def test_underscores(self):
        assert _esc_md("foo_bar_baz") == "foo\\_bar\\_baz"

    def test_asterisks(self):
        assert _esc_md("**bold**") == "\\*\\*bold\\*\\*"

    def test_backticks(self):
        assert _esc_md("use `code` here") == "use \\`code\\` here"

    def test_brackets(self):
        assert _esc_md("[link](url)") == "\\[link](url)"

    def test_mixed(self):
        assert _esc_md("fix *bug* in `foo_bar`") == "fix \\*bug\\* in \\`foo\\_bar\\`"

    def test_empty(self):
        assert _esc_md("") == ""

    def test_real_task_description(self):
        desc = "update the baseball_bingo app to support user sign-in"
        result = _esc_md(desc)
        assert "\\_" in result
        # All underscores are escaped
        assert result.count("_") == result.count("\\_")


class TestParseFlags:
    """Verify parse_flags still works (regression after edits)."""

    def test_no_flags(self):
        desc, flags = parse_flags("fix the bug")
        assert desc == "fix the bug"
        assert flags == {}

    def test_model_flag(self):
        desc, flags = parse_flags("--model=opus fix the bug")
        assert desc == "fix the bug"
        assert flags["model"] == "claude-opus-4-7"

    def test_effort_flag(self):
        desc, flags = parse_flags("--effort=high fix the bug")
        assert desc == "fix the bug"
        assert flags["effort"] == "high"

    def test_multiple_flags(self):
        desc, flags = parse_flags("--model=sonnet --effort=low describe the weather")
        assert desc == "describe the weather"
        assert flags["model"] == "claude-sonnet-4-6"
        assert flags["effort"] == "low"

    def test_flags_only(self):
        desc, flags = parse_flags("--model=opus")
        assert desc == ""
        assert flags["model"] == "claude-opus-4-7"


import asyncio
from unittest.mock import AsyncMock, MagicMock


class TestErrorSafeDecorator:
    def test_successful_handler_passes_through(self):
        from src.gateway.telegram_bot import _error_safe
        calls = []
        @_error_safe
        async def handler(update, ctx):
            calls.append(1)
        update = MagicMock()
        update.effective_chat.id = 123
        update.message.reply_text = AsyncMock()
        asyncio.run(handler(update, None))
        assert calls == [1]
        update.message.reply_text.assert_not_called()

    def test_exception_retries_then_replies(self):
        from src.gateway.telegram_bot import _error_safe
        call_count = 0
        @_error_safe
        async def handler(update, ctx):
            nonlocal call_count
            call_count += 1
            raise ValueError("boom")
        update = MagicMock()
        update.effective_chat.id = 123
        update.message.reply_text = AsyncMock()
        asyncio.run(handler(update, None))
        assert call_count == 2  # original + 1 retry
        # Should have called reply_text at least twice (retry msg + final error msg)
        assert update.message.reply_text.call_count >= 2
