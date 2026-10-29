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


class TestParseCallback:
    def test_simple_action(self):
        from src.gateway.telegram_bot import _parse_callback
        action, prefix, extra = _parse_callback("approve:abc12345")
        assert action == "approve"
        assert prefix == "abc12345"
        assert extra is None

    def test_action_with_extra(self):
        from src.gateway.telegram_bot import _parse_callback
        action, prefix, extra = _parse_callback("rate:abc12345:4")
        assert action == "rate"
        assert prefix == "abc12345"
        assert extra == "4"

    def test_no_prefix(self):
        from src.gateway.telegram_bot import _parse_callback
        action, prefix, extra = _parse_callback("garbage")
        assert action == "garbage"
        assert prefix is None
        assert extra is None

    def test_job_details_callback_parses(self):
        # A6: the FailedCard's [Details] button — the prefix is a JOB id.
        from src.gateway.telegram_bot import _parse_callback
        assert _parse_callback("jd:abcdef12") == ("jd", "abcdef12", None)


import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


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
        # Mock enqueue_job so the Level-3 self-diagnose branch doesn't insert
        # a real row into the jobs table (which would spawn a real self-diagnose
        # session investigating a synthetic test failure — see incident
        # 2026-07-28 in docs/Troubleshooting.md).
        with patch("src.gateway.telegram_bot.enqueue_job", new=AsyncMock()) as m:
            asyncio.run(handler(update, None))
            m.assert_awaited_once()
            # Sanity: the dispatched job is the self-diagnose kind, not a job
            # that would execute arbitrary work.
            assert m.await_args.kwargs.get("kind") == "self-diagnose"
        assert call_count == 2  # original + 1 retry
        # Should have called reply_text at least twice (retry msg + final error msg)
        assert update.message.reply_text.call_count >= 2


# ── T7 (2026-10-21): provider on every Telegram surface ────────────────────
#
# `--model=` parses THROUGH the models registry: an alias or a
# `[provider/]model_id` lands in `job.payload["model"]` in its canonical form
# (bare Anthropic id, `provider/model_id` otherwise), and anything the
# registry does not know is refused at parse time with the registry's reason
# — never passed through raw for the session to fail later. The handlers
# reply with that reason and create no task and no job. `/jobs` rows, the
# done/failed DM and the task "details" card name the lane
# (`provider/model`) the job ran on.

import uuid as _uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.config import settings
from src.gateway import telegram_bot as tg
from src.gateway.telegram_bot import ModelFlagRefused, _done_dm_text, _lane_label


class TestParseFlagsProviderIds:
    def test_qualified_codex_id_is_canonical(self):
        desc, flags = parse_flags("--model=codex/gpt-6-luna fix the flaky test")
        assert desc == "fix the flaky test"
        assert flags["model"] == "codex/gpt-6-luna"

    def test_explicit_anthropic_prefix_is_stored_bare(self):
        # `anthropic/opus` is accepted and lands bare, exactly what the
        # session's registry resolution and the Anthropic path already read.
        assert parse_flags("--model=anthropic/opus x")[1]["model"] == "claude-opus-4-7"
        assert parse_flags("--model=anthropic/claude-sonnet-4-6 x")[1]["model"] == "claude-sonnet-4-6"

    def test_case_insensitive(self):
        assert parse_flags("--model=CODEX/GPT-6-SOL x")[1]["model"] == "codex/gpt-6-sol"
        assert parse_flags("--model=OPUS x")[1]["model"] == "claude-opus-4-7"

    def test_retired_alias_still_maps_to_replacement(self):
        assert parse_flags("--model=haiku x")[1]["model"] == "claude-sonnet-4-6"

    def test_unknown_provider_refused_at_parse_time_with_reason(self):
        with pytest.raises(ModelFlagRefused) as ei:
            parse_flags("--model=gemini/flash fix it")
        assert ei.value.raw == "gemini/flash"
        assert "unknown provider 'gemini'" in ei.value.reason
        assert "gemini/flash" in str(ei.value)

    def test_unknown_model_refused_at_parse_time_with_reason(self):
        with pytest.raises(ModelFlagRefused) as ei:
            parse_flags("--model=codex/gpt-9 fix it")
        assert "unknown model 'gpt-9' for provider 'codex'" in ei.value.reason

    def test_bare_non_anthropic_id_is_refused(self):
        # C12: a bare id means anthropic/; `gpt-6-luna` is not an Anthropic
        # model, so it is refused rather than guessed to be Codex.
        with pytest.raises(ModelFlagRefused) as ei:
            parse_flags("--model=gpt-6-luna x")
        assert "anthropic" in ei.value.reason

    def test_bare_retired_id_is_refused(self):
        with pytest.raises(ModelFlagRefused):
            parse_flags("--model=claude-haiku-4-5-20251001 x")

    def test_refusal_is_a_value_error(self):
        assert issubclass(ModelFlagRefused, ValueError)

    def test_other_flags_still_parse_before_a_model_refusal(self):
        # The refusal is raised for the model flag alone; nothing else about
        # the grammar changed.
        desc, flags = parse_flags("--effort=high --model=codex/gpt-6-astra do it")
        assert desc == "do it"
        assert flags == {"effort": "high", "model": "codex/gpt-6-astra"}


class TestLaneLabel:
    def test_provider_and_model(self):
        assert _lane_label("codex", "gpt-6-luna") == "codex/gpt-6-luna"
        assert _lane_label("anthropic", "claude-opus-4-7") == "anthropic/claude-opus-4-7"

    def test_pre_007_row_has_model_only(self):
        assert _lane_label(None, "claude-opus-4-7") == "claude-opus-4-7"

    def test_queued_row_has_neither(self):
        assert _lane_label(None, None) == ""
        assert _lane_label("", "") == ""

    def test_terminal_reason_appended_when_not_ok(self):
        assert _lane_label("codex", "gpt-6-luna", "auth_expired") == "codex/gpt-6-luna · auth_expired"
        assert _lane_label("codex", "gpt-6-luna", "ok") == "codex/gpt-6-luna"
        assert _lane_label("codex", "gpt-6-luna", None) == "codex/gpt-6-luna"


class TestDoneDmText:
    def test_completed_names_lane_and_rate_hint(self):
        text = _done_dm_text("0123456789abcdef", "completed", "did the thing",
                             "codex/gpt-6-luna")
        assert text.startswith("Job `01234567` *completed* · `codex/gpt-6-luna`")
        assert "did the thing" in text
        assert "/rate" not in text                     # E3: /rate never existed as a command

    def test_failed_names_lane_and_reason(self):
        text = _done_dm_text("0123456789abcdef", "failed", "",
                             "codex/gpt-6-luna · rate_limited")
        assert text == "Job `01234567` *failed* · `codex/gpt-6-luna · rate_limited`"

    def test_no_lane_is_the_pre_t7_text(self):
        text = _done_dm_text("0123456789abcdef", "completed", "sum", "")
        assert text == "Job `01234567` *completed*\n\nsum"


# ── handler-level: refusal replies, no job; /jobs rows; done DM lookup ──────


def _tg_update(text: str) -> SimpleNamespace:
    msg = SimpleNamespace(text=text, reply_text=AsyncMock())
    return SimpleNamespace(effective_chat=SimpleNamespace(id=1), message=msg)


class _FakeDB:
    """Minimal `async_session()` stand-in: `execute(select)` returns the
    given rows via `.scalars().all()`, `get(Job, id)` returns the matching row."""

    def __init__(self, rows=()):
        self.rows = list(rows)
        self.added = []

    def __call__(self):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def execute(self, stmt):
        rows = self.rows
        return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: rows))

    async def get(self, model, ident):
        for r in self.rows:
            if r.id == ident:
                return r
        return None

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        pass

    async def refresh(self, obj):
        pass


def _job_row(**over):
    base = dict(
        id=_uuid.uuid4(), status="completed", kind="task", resolved_skill="app-patch",
        description="fix the flaky test", task_id=None,
        resolved_provider="codex", resolved_model="gpt-6-luna",
        terminal_reason="ok", error_message=None, result=None,
    )
    base.update(over)
    return SimpleNamespace(**base)


class TestHandlersRefuseUnknownModel:
    @pytest.fixture(autouse=True)
    def _auth(self, monkeypatch):
        monkeypatch.setattr(tg, "_is_authorized", lambda chat_id: True)
        self.db = _FakeDB()
        monkeypatch.setattr(tg, "async_session", self.db)
        self.enqueue = AsyncMock()
        monkeypatch.setattr(tg, "enqueue_job", self.enqueue)

    async def test_task_unknown_model_replies_reason_and_creates_nothing(self):
        upd = _tg_update("/task --model=gemini/flash fix it")
        await tg.cmd_task(upd, SimpleNamespace(args=["--model=gemini/flash", "fix", "it"]))
        upd.message.reply_text.assert_awaited_once()
        text = upd.message.reply_text.call_args.args[0]
        assert "gemini/flash" in text and "unknown provider 'gemini'" in text
        self.enqueue.assert_not_awaited()
        assert self.db.added == []            # no Task row either

    async def test_task_disabled_provider_replies_reason_and_creates_nothing(self, monkeypatch):
        # Known to the registry, but not in ROUTER_PROVIDERS_ENABLED (default
        # `anthropic`): refused at the command, same as the web's 422, instead
        # of a job that the session fails with provider_refused.
        monkeypatch.setattr(settings, "router_providers_enabled", "anthropic")
        upd = _tg_update("/task --model=codex/gpt-6-luna fix it")
        await tg.cmd_task(upd, SimpleNamespace(args=["--model=codex/gpt-6-luna", "fix", "it"]))
        text = upd.message.reply_text.call_args.args[0]
        assert "not enabled" in text and "codex" in text
        self.enqueue.assert_not_awaited()
        assert self.db.added == []

    async def test_refusal_reply_lists_what_is_accepted(self, monkeypatch):
        monkeypatch.setattr(settings, "router_providers_enabled", "anthropic,codex")
        upd = _tg_update("/task --model=nope fix it")
        await tg.cmd_task(upd, SimpleNamespace(args=["--model=nope", "fix", "it"]))
        text = upd.message.reply_text.call_args.args[0]
        assert "opus" in text and "sonnet" in text
        assert "codex/gpt-6-luna" in text
        # Never a Markdown reply: the raw value is user text.
        assert upd.message.reply_text.call_args.kwargs.get("parse_mode") is None

    async def test_chat_and_god_refuse_the_same_way(self):
        for handler in (tg.cmd_chat, tg.cmd_god):
            upd = _tg_update("--model=codex/gpt-9 hello")
            await handler(upd, SimpleNamespace(args=["--model=codex/gpt-9", "hello"]))
            text = upd.message.reply_text.call_args.args[0]
            assert "unknown model 'gpt-9'" in text
        self.enqueue.assert_not_awaited()
        assert self.db.added == []

    async def test_enabled_codex_model_enqueues_canonical(self, monkeypatch):
        monkeypatch.setattr(settings, "router_providers_enabled", "anthropic,codex")
        self.enqueue.return_value = SimpleNamespace(id=_uuid.uuid4())
        upd = _tg_update("/chat --model=codex/gpt-6-luna hello")
        await tg.cmd_chat(upd, SimpleNamespace(args=["--model=codex/gpt-6-luna", "hello"]))
        self.enqueue.assert_awaited_once()
        assert self.enqueue.await_args.kwargs["payload"] == {"model": "codex/gpt-6-luna"}


class TestJobsRowsShowLane:
    @pytest.fixture(autouse=True)
    def _auth(self, monkeypatch):
        monkeypatch.setattr(tg, "_is_authorized", lambda chat_id: True)

    async def test_rows_name_provider_slash_model(self, monkeypatch):
        rows = [
            _job_row(resolved_provider="codex", resolved_model="gpt-6-luna"),
            _job_row(resolved_provider="anthropic", resolved_model="claude-opus-4-7",
                     status="failed"),
            _job_row(resolved_provider=None, resolved_model=None, status="queued"),
        ]
        monkeypatch.setattr(tg, "async_session", _FakeDB(rows))
        upd = _tg_update("/jobs")
        await tg.cmd_jobs(upd, SimpleNamespace(args=[]))
        text = upd.message.reply_text.call_args.args[0]
        assert "`codex/gpt-6-luna`" in text
        assert "`anthropic/claude-opus-4-7`" in text
        # The queued row has no lane yet and gets no empty bracket.
        queued_line = [ln for ln in text.splitlines() if str(rows[2].id)[:8] in ln][0]
        assert "`/cancel" not in queued_line and "``" not in queued_line
        assert "⏳" in queued_line


class TestDoneDmLookup:
    async def test_deliver_done_reads_lane_from_the_job_row(self, monkeypatch):
        row = _job_row(resolved_provider="codex", resolved_model="gpt-6-luna",
                       status="failed", terminal_reason="auth_expired")
        monkeypatch.setattr(tg, "async_session", _FakeDB([row]))
        bot = SimpleNamespace(send_message=AsyncMock())
        await tg._deliver_done(SimpleNamespace(bot=bot), 1, str(row.id), {"status": "failed"})
        text = bot.send_message.await_args.args[1]
        assert text == f"Job `{str(row.id)[:8]}` *failed* · `codex/gpt-6-luna · auth_expired`"

    async def test_deliver_done_survives_a_db_error(self, monkeypatch):
        class _Boom:
            def __call__(self):
                raise RuntimeError("db down")
        monkeypatch.setattr(tg, "async_session", _Boom())
        bot = SimpleNamespace(send_message=AsyncMock())
        jid = str(_uuid.uuid4())
        await tg._deliver_done(SimpleNamespace(bot=bot), 1, jid,
                               {"status": "completed", "summary": "done"})
        text = bot.send_message.await_args.args[1]
        assert text.startswith(f"Job `{jid[:8]}` *completed*\n\ndone")

    async def test_deliver_done_unknown_row_has_no_lane(self, monkeypatch):
        monkeypatch.setattr(tg, "async_session", _FakeDB([]))
        bot = SimpleNamespace(send_message=AsyncMock())
        jid = str(_uuid.uuid4())
        await tg._deliver_done(SimpleNamespace(bot=bot), 1, jid, {"status": "completed"})
        assert bot.send_message.await_args.args[1] == f"Job `{jid[:8]}` *completed*"


# ── A2: every launch persists its origin ──────────────────────────────────
#
# Observability Phase 1 re-cut plan A2. A Telegram launch stamps
# origin_channel="telegram" / origin_ref=<chat id> on BOTH the Task row and
# the enqueue call, and the bot's root reply id as origin_thread on both rows
# once the reply exists; a web launch passes origin_channel="web" and no ref
# (NULL, matching migration 008's backfill CASE).

from sqlalchemy.dialects import postgresql


class _RecordingDB(_FakeDB):
    def __init__(self, rows=()):
        super().__init__(rows)
        self.executed = []

    async def execute(self, stmt):
        self.executed.append(stmt)
        return await super().execute(stmt)


def _update_params(stmt) -> tuple[str, dict]:
    return stmt.table.name, dict(stmt.compile(dialect=postgresql.dialect()).params)


def _tg_update_with_reply(text: str, *, chat_id: int = 1, message_id: int = 777) -> SimpleNamespace:
    reply = SimpleNamespace(message_id=message_id)
    msg = SimpleNamespace(text=text, reply_text=AsyncMock(return_value=reply))
    return SimpleNamespace(effective_chat=SimpleNamespace(id=chat_id), message=msg)


class TestLaunchOrigin:
    @pytest.fixture(autouse=True)
    def _auth(self, monkeypatch):
        monkeypatch.setattr(tg, "_is_authorized", lambda chat_id: True)
        self.db = _RecordingDB()
        monkeypatch.setattr(tg, "async_session", self.db)
        self.enqueue = AsyncMock(return_value=SimpleNamespace(id=_uuid.uuid4()))
        monkeypatch.setattr(tg, "enqueue_job", self.enqueue)

    async def test_web_and_telegram_launches_persist_origin(self, monkeypatch):
        # /task → Task row + enqueue both carry telegram/<chat>, then the root
        # reply's message id lands as origin_thread on the Task AND the Job.
        upd = _tg_update_with_reply("/task fix it", chat_id=424242, message_id=777)
        await tg.cmd_task(upd, SimpleNamespace(args=["fix", "it"]))
        task = next(o for o in self.db.added if isinstance(o, tg.Task))
        assert (task.origin_channel, task.origin_ref) == ("telegram", "424242")
        assert task.chat_id == 424242                      # kept (keep columns, stop depending)
        kw = self.enqueue.await_args.kwargs
        assert (kw["origin_channel"], kw["origin_ref"]) == ("telegram", "424242")
        assert kw["created_by"] == "telegram:424242"
        threads = {tbl: p.get("origin_thread") for tbl, p in map(_update_params, self.db.executed)
                   if "origin_thread" in p}
        assert threads == {"tasks": "777", "jobs": "777"}
        tasks_update = next(p for tbl, p in map(_update_params, self.db.executed) if tbl == "tasks")
        assert tasks_update["thread_message_id"] == 777    # the legacy column is still written

        # /chat (no Task row) carries the same origin on the enqueue.
        self.enqueue.reset_mock()
        upd = _tg_update_with_reply("/chat hello", chat_id=424242)
        await tg.cmd_chat(upd, SimpleNamespace(args=["hello"]))
        kw = self.enqueue.await_args.kwargs
        assert (kw["origin_channel"], kw["origin_ref"]) == ("telegram", "424242")

        # Web: POST /api/jobs passes origin_channel="web" and NO ref.
        from fastapi.testclient import TestClient
        from src.gateway import web
        web_enqueue = AsyncMock(return_value=SimpleNamespace(
            id=_uuid.uuid4(), kind="task", description="fix it", status="queued",
            resolved_skill=None, resolved_model=None, resolved_effort=None,
            user_rating=None, review_outcome=None, created_at=__import__("datetime").datetime.now(),
            started_at=None, completed_at=None, result=None, error_message=None,
            created_by="web", origin_channel="web", origin_ref=None))
        monkeypatch.setattr(web, "enqueue_job", web_enqueue)
        web.app.dependency_overrides[web._check_auth] = lambda: None
        try:
            body = TestClient(web.app).post("/api/jobs", json={"description": "fix it"}).json()
        finally:
            web.app.dependency_overrides.pop(web._check_auth, None)
        kw = web_enqueue.await_args.kwargs
        assert kw["created_by"] == "web" and kw["origin_channel"] == "web"
        assert kw.get("origin_ref") is None and kw.get("origin_thread") is None
        assert body["origin_channel"] == "web" and body["origin_ref"] is None

    async def test_god_launch_persists_origin_on_both_rows(self):
        upd = _tg_update_with_reply("/god do it", chat_id=7, message_id=901)
        await tg.cmd_god(upd, SimpleNamespace(args=["do", "it"]))
        task = next(o for o in self.db.added if isinstance(o, tg.Task))
        assert (task.origin_channel, task.origin_ref) == ("telegram", "7")
        kw = self.enqueue.await_args.kwargs
        assert kw["kind"] == "god" and (kw["origin_channel"], kw["origin_ref"]) == ("telegram", "7")
        threads = [(tbl, p["origin_thread"]) for tbl, p in map(_update_params, self.db.executed)
                   if "origin_thread" in p]
        assert sorted(threads) == [("jobs", "901"), ("tasks", "901")]

    async def test_plain_text_chat_carries_origin(self):
        upd = _tg_update_with_reply("what time is it?", chat_id=5)
        await tg._handle_plain_text(upd, None)
        kw = self.enqueue.await_args.kwargs
        assert kw["kind"] == "chat"
        assert (kw["origin_channel"], kw["origin_ref"]) == ("telegram", "5")


# ── E3: ghost commands become real; one cancel semantics; /rate leaves the copy ──

import uuid  # noqa: E402

class TestCancelReply:
    def test_replies(self):
        from src.gateway.telegram_bot import format_cancel_reply
        assert format_cancel_reply("cancelled_queued", "abcdef12") == "🚫 Job abcdef12 removed from the queue."
        assert format_cancel_reply("cancel_requested", "abcdef12") == "🚫 Cancel sent to the runner for running job abcdef12."
        assert format_cancel_reply("already_terminal", "abcdef12") == "Job abcdef12 is already finished — nothing to cancel."
        assert format_cancel_reply("not_found", "abcdef12") == "No job matches abcdef12 (need a unique 8-char prefix)."
        assert format_cancel_reply("???", "x") == format_cancel_reply("not_found", "x")


class TestCmdCancel:
    @pytest.fixture(autouse=True)
    def _auth(self, monkeypatch):
        monkeypatch.setattr(tg, "_is_authorized", lambda chat_id: True)

    async def test_usage_without_an_argument(self):
        upd = _tg_update("/cancel")
        await tg.cmd_cancel(upd, SimpleNamespace(args=[]))
        assert "Usage: /cancel <job prefix>" in upd.message.reply_text.call_args.args[0]

    async def test_resolves_the_prefix_and_routes_through_the_durable_path(self, monkeypatch):
        job = SimpleNamespace(id=uuid.uuid4(), status="queued")
        calls = []

        async def fake_find(prefix):
            return job if prefix == str(job.id)[:8] else None

        async def fake_durable(j, *, stage):
            calls.append((j.id, stage))
            return "cancelled_queued"
        monkeypatch.setattr(tg, "find_job_by_prefix", fake_find)
        monkeypatch.setattr(tg, "cancel_job_durable", fake_durable)
        upd = _tg_update("/cancel")
        await tg.cmd_cancel(upd, SimpleNamespace(args=[str(job.id)[:8]]))
        assert calls == [(job.id, "telegram")]
        assert upd.message.reply_text.call_args.args[0] == \
            f"🚫 Job {str(job.id)[:8]} removed from the queue."

    async def test_unknown_prefix(self, monkeypatch):
        async def fake_find(prefix):
            return None
        monkeypatch.setattr(tg, "find_job_by_prefix", fake_find)
        upd = _tg_update("/cancel")
        await tg.cmd_cancel(upd, SimpleNamespace(args=["zzzzzzzz"]))
        assert "No job matches zzzzzzzz" in upd.message.reply_text.call_args.args[0]


class TestCmdProposals:
    @pytest.fixture(autouse=True)
    def _auth(self, monkeypatch):
        monkeypatch.setattr(tg, "_is_authorized", lambda chat_id: True)

    async def test_empty(self, monkeypatch):
        from src.runner import proposals as proposals_mod

        async def none(limit=50):
            return []
        monkeypatch.setattr(proposals_mod, "list_pending_proposals", none)
        upd = _tg_update("/proposals")
        await tg.cmd_proposals(upd, SimpleNamespace(args=[]))
        assert upd.message.reply_text.call_args.args[0] == "No pending proposals."

    async def test_lists_pending_rows_as_plain_text(self, monkeypatch):
        from datetime import datetime, timezone
        from src.runner import proposals as proposals_mod
        rows = [SimpleNamespace(id=uuid.uuid4(), target_file="skills/x/SKILL.md",
                                change_type="edit", outcome="pending",
                                proposed_at=datetime(2026, 10, 29, tzinfo=timezone.utc))]

        async def some(limit=50):
            assert limit == 15
            return rows
        monkeypatch.setattr(proposals_mod, "list_pending_proposals", some)
        upd = _tg_update("/proposals")
        await tg.cmd_proposals(upd, SimpleNamespace(args=[]))
        args, kwargs = upd.message.reply_text.call_args
        assert args[0].startswith("Pending proposals (1):")
        assert "skills/x/SKILL.md" in args[0]
        assert "parse_mode" not in kwargs                 # plain text: paths carry `_`


class TestHelpCopy:
    def test_help_and_jobs_no_longer_advertise_rate(self):
        import inspect
        src = inspect.getsource(tg.cmd_help) + inspect.getsource(tg.cmd_jobs)
        assert "/rate" not in src
        help_src = inspect.getsource(tg.cmd_help)
        assert "/cancel <prefix>" in help_src and "/proposals" in help_src
        assert "/status <prefix>" in help_src

    def test_ghost_commands_are_registered(self):
        import inspect
        src = inspect.getsource(tg.main)
        for cmd in ('CommandHandler("cancel", cmd_cancel)', 'CommandHandler("proposals", cmd_proposals)'):
            assert cmd in src

    def test_done_dm_drops_the_rate_hint(self):
        text = _done_dm_text("0123456789abcdef", "completed", "did the thing", "codex/gpt-6-luna")
        assert "/rate" not in text and "did the thing" in text


class TestStatusPrefix:
    @pytest.fixture(autouse=True)
    def _auth(self, monkeypatch):
        monkeypatch.setattr(tg, "_is_authorized", lambda chat_id: True)

    async def test_status_prefix_renders_job(self, monkeypatch):
        # Routing only: the renderer itself is A6's (tests/test_notify_bot.py).
        row = _job_row(resolved_provider="anthropic", resolved_model="claude-opus-5",
                       status="completed")
        seen = []

        async def fake_find(prefix):
            seen.append(prefix)
            return row
        monkeypatch.setattr(tg, "find_job_by_prefix", fake_find)
        monkeypatch.setattr(tg, "format_job_status", lambda j: f"RENDERED {j.id}")
        upd = _tg_update("/status")
        await tg.cmd_status(upd, SimpleNamespace(args=[str(row.id)[:8]]))
        assert seen == [str(row.id)[:8]]
        args, kwargs = upd.message.reply_text.call_args
        assert args[0] == f"RENDERED {row.id}" and "parse_mode" not in kwargs


# ── E4: /clear requires a confirm button ────────────────────────────────────

class TestClearConfirm:
    def test_token_valid_within_ttl(self):
        from src.gateway.telegram_bot import clear_token_valid
        assert clear_token_valid(("abcd1234", 1000.0), "abcd1234", 1050.0)

    def test_token_expires(self):
        from src.gateway.telegram_bot import clear_token_valid
        assert not clear_token_valid(("abcd1234", 1000.0), "abcd1234", 1121.0)   # 121 s > 120
        assert not clear_token_valid(("abcd1234", 1000.0), "zzzz0000", 1001.0)
        assert not clear_token_valid(None, "abcd1234", 1001.0)
        assert not clear_token_valid(("abcd1234", 1000.0), "abcd1234", 999.0)    # clock went back

    def test_callbacks_fit_64_bytes(self):
        cb = "clear_confirm:" + "a" * 8
        assert len(cb.encode()) <= 64
        assert tg._parse_callback(cb) == ("clear_confirm", "a" * 8, None)
        assert tg._parse_callback("clear_abort:0") == ("clear_abort", "0", None)

    def test_cmd_clear_no_longer_clears_directly(self):
        import inspect
        src = inspect.getsource(tg.cmd_clear)
        assert "clear_confirm:" in src and "sql_update(Job)" not in src
        assert "clear_token" in src

    @pytest.fixture(autouse=True)
    def _auth(self, monkeypatch):
        monkeypatch.setattr(tg, "_is_authorized", lambda chat_id: True)

    async def test_cmd_clear_previews_counts_and_arms_a_token(self, monkeypatch):
        class _Counts:
            def __init__(self):
                self.n = iter([3, 2])

            def __call__(self):
                return self

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc):
                return False

            async def execute(self, stmt):
                v = next(self.n)
                return SimpleNamespace(scalar=lambda: v)
        monkeypatch.setattr(tg, "async_session", _Counts())
        upd = _tg_update("/clear")
        ctx = SimpleNamespace(args=[], bot_data={})
        await tg.cmd_clear(upd, ctx)
        args, kwargs = upd.message.reply_text.call_args
        assert "3" in args[0] and "2" in args[0] and "Confirm within 120 s" in args[0]
        token, issued = ctx.bot_data["clear_token"]
        assert len(token) == 8
        buttons = [b for row in kwargs["reply_markup"].inline_keyboard for b in row]
        assert buttons[0].callback_data == f"clear_confirm:{token}"
        assert buttons[1].callback_data == "clear_abort:0"
        assert "3 job(s), 2 task(s)" in buttons[0].text

    async def test_abort_leaves_queue(self, monkeypatch):
        calls = []

        async def fake_do_clear():
            calls.append(1)
            return (0, 0)
        monkeypatch.setattr(tg, "_do_clear", fake_do_clear)
        from tests.test_notify_bot import _button_update
        upd = _button_update("clear_abort:0")
        ctx = SimpleNamespace(bot_data={"clear_token": ("abcd1234", 0.0)})
        await tg._handle_button(upd, ctx)
        upd.callback_query.edit_message_text.assert_awaited_once_with("Clear aborted.")
        assert calls == []

    async def test_expired_confirm_does_not_clear(self, monkeypatch):
        import time as _time
        calls = []

        async def fake_do_clear():
            calls.append(1)
            return (0, 0)
        monkeypatch.setattr(tg, "_do_clear", fake_do_clear)
        from tests.test_notify_bot import _button_update
        upd = _button_update("clear_confirm:abcd1234")
        ctx = SimpleNamespace(bot_data={"clear_token": ("abcd1234", _time.time() - 200)})
        await tg._handle_button(upd, ctx)
        text = upd.callback_query.edit_message_text.await_args.args[0]
        assert "expired" in text and "/clear" in text
        assert calls == []
        # A wrong token is refused the same way, and a missing one too.
        upd2 = _button_update("clear_confirm:zzzz0000")
        ctx2 = SimpleNamespace(bot_data={"clear_token": ("abcd1234", _time.time())})
        await tg._handle_button(upd2, ctx2)
        assert "expired" in upd2.callback_query.edit_message_text.await_args.args[0]
        assert calls == []

    async def test_confirm_clears_through_the_durable_path(self, monkeypatch):
        import time as _time
        cancelled = []

        async def fake_do_clear():
            cancelled.append("ran")
            return (3, 2)
        monkeypatch.setattr(tg, "_do_clear", fake_do_clear)
        from tests.test_notify_bot import _button_update
        upd = _button_update("clear_confirm:abcd1234")
        ctx = SimpleNamespace(bot_data={"clear_token": ("abcd1234", _time.time() - 5)})
        await tg._handle_button(upd, ctx)
        assert cancelled == ["ran"]
        upd.callback_query.edit_message_text.assert_awaited_once_with("Cleared 3 job(s) and 2 task(s).")
        assert "clear_token" not in ctx.bot_data            # single use

    async def test_do_clear_cancels_queued_deferred_and_running_then_fails_tasks(self, monkeypatch, fake_redis):
        # _do_clear routes EVERY open job through cancel_job_durable(stage="cleared")
        # — queued and deferred flip, running gets the publish (the old body
        # flipped running rows in SQL with no publish, leaving live sessions
        # running into a suppressed finish) — then fails the open tasks and
        # flushes jobs:queue.
        q, d, r = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        rows = [SimpleNamespace(id=q, status="queued"), SimpleNamespace(id=d, status="deferred"),
                SimpleNamespace(id=r, status="running")]
        seen = []

        async def fake_durable(job, *, stage):
            seen.append((job.id, job.status, stage))
            return "cancel_requested" if job.status == "running" else "cancelled_queued"
        monkeypatch.setattr(tg, "cancel_job_durable", fake_durable)
        monkeypatch.setattr(tg, "redis", fake_redis)
        await fake_redis.rpush("jobs:queue", str(q))

        class _DB:
            def __init__(self):
                self.statements = []

            def __call__(self):
                return self

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc):
                return False

            async def execute(self, stmt):
                self.statements.append(stmt)
                if len(self.statements) == 1:                       # the open-jobs SELECT
                    return SimpleNamespace(scalars=lambda: rows, all=lambda: rows)
                return SimpleNamespace(rowcount=2)                  # the Task UPDATE

            async def commit(self):
                pass
        db = _DB()
        monkeypatch.setattr(tg, "async_session", db)
        jobs_cleared, tasks_cleared = await tg._do_clear()
        assert sorted(s for _, _, s in seen) == ["cleared"] * 3
        assert {st for _, st, _ in seen} == {"queued", "deferred", "running"}
        assert (jobs_cleared, tasks_cleared) == (3, 2)
        assert await fake_redis.llen("jobs:queue") == 0
        where = str(db.statements[0].compile(compile_kwargs={"literal_binds": True}))
        assert "deferred" in where and "queued" in where and "running" in where
        # No direct cancel UPDATE on jobs any more — the durable path owns that.
        assert len(db.statements) == 2 and "tasks" in str(db.statements[1]).lower()

    def test_deferred_job_is_cancelled_by_clear(self):
        # The semantic widening the P0 plan calls out: plan-DAG children parked
        # in `deferred` used to survive /clear; "clear everything" means them.
        import inspect
        src = inspect.getsource(tg._do_clear)
        assert "_CLEAR_JOB_STATUSES" in src and "cancel_job_durable(" in src
        assert 'stage="cleared"' in src
        assert set(tg._CLEAR_JOB_STATUSES) == {"queued", "deferred", "running"}
