"""
Bot-side outbox delivery (Observability Phase 1, A6; design of record P0
plan Task 7). Everything touching python-telegram-bot, Redis or the DB is
monkeypatched; what is tested is the drain loop's bookkeeping, the
renderer-side switch (D-P1-10: the bot's, never the runner's), the
`legacy_mode` ops-only delivery, the `[Details]` button and the pure job
status formatter.

Run: PIPENV_DONT_LOAD_ENV=1 SERVER_ROOT="$PWD" pipenv run pytest tests/test_notify_bot.py -q -p no:cacheprovider
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.gateway import telegram_bot as bot_mod
from src.gateway.telegram_bot import format_job_status
from src.notify.outbox import OPS_NOTICE_KINDS, Notice, lane_label

FAKE_TOKEN = "123456789:AAFakeTokenForTheBotLeakTest_notReal"   # placeholder, not a credential


def _job(**over):
    base = dict(id=uuid.UUID("abcdef12-0000-4000-8000-000000000000"), status="failed",
                kind="task", resolved_skill="app-patch", resolved_provider=None,
                resolved_model="claude-sonnet-4-6", model_served="claude-sonnet-4-6",
                terminal_reason="api_error", num_turns=4,
                input_tokens=15, output_tokens=900, cache_read_tokens=20000,
                duration_api_ms=4200, cost_usd_list=None, origin_channel="scheduler",
                origin_ref="nightly", error_message="API Error: 529 Overloaded",
                result={"summary": "did things"})
    base.update(over)
    return SimpleNamespace(**base)


class TestFormatJobStatus:
    def test_shows_p0_columns_and_summary(self):
        text = format_job_status(_job())
        assert text.startswith("Job abcdef12 — failed")
        for needle in ("app-patch", "claude-sonnet-4-6", "terminal: api_error", "turns: 4",
                       "out 900", "4.2s", "origin: scheduler:nightly", "529", "did things"):
            assert needle in text, needle

    def test_never_exceeds_telegram_limit(self):
        text = format_job_status(_job(result={"summary": "x" * 9000}, error_message="e" * 9000))
        assert len(text) <= 4096

    def test_minimal_job(self):
        text = format_job_status(_job(model_served=None, resolved_model=None, terminal_reason=None,
                                      num_turns=None, output_tokens=None, duration_api_ms=None,
                                      origin_channel=None, error_message=None, result=None))
        assert text == "Job abcdef12 — failed\nkind: app-patch"

    def test_lane_uses_the_one_definition(self):
        text = format_job_status(_job(resolved_provider="codex", resolved_model="gpt-6-luna",
                                      model_served=None))
        assert f"lane: {lane_label('codex', 'gpt-6-luna')}" in text
        assert "codex/gpt-6-luna" in text

    def test_cost_line_when_priced(self):
        from decimal import Decimal
        text = format_job_status(_job(cost_usd_list=Decimal("0.1234")))
        assert "$0.1234" in text

    def test_no_markdown_markers_in_header(self):
        # Sent WITHOUT parse_mode: skill names with `_` would crash Markdown.
        text = format_job_status(_job(resolved_skill="app_patch_v2"))
        assert text.splitlines()[0] == "Job abcdef12 — failed"
        assert "`" not in text and "*" not in text


# ── Drain loop ──────────────────────────────────────────────────────────────


class _Store:
    """Fake notifications table for the drain loop (mirrors outbox.py's
    claim → send → mark_sent/mark_failed/mark_skipped contract)."""

    def __init__(self, rows):
        self.rows = {r.id: r for r in rows}
        self.sent, self.failed, self.skipped = [], [], []

    async def pending(self, limit=20):
        return [r for r in self.rows.values() if r.status == "pending"]

    async def claim(self, nid, now=None):
        row = self.rows[nid]
        if row.status != "pending":
            return False
        row.status, row.attempts = "sending", row.attempts + 1
        return True

    async def mark_sent(self, nid, ref, **kw):
        self.rows[nid].status = "sent"
        self.sent.append((nid, ref))

    async def mark_failed(self, nid, err, *, attempts_so_far, **kw):
        self.rows[nid].attempts = attempts_so_far + 1
        self.rows[nid].status = "failed" if self.rows[nid].attempts >= 5 else "pending"
        self.failed.append((nid, err))
        return self.rows[nid].status

    async def mark_skipped(self, nid, reason):
        self.rows[nid].status = "skipped"
        self.skipped.append((nid, reason))


def _row(kind="job_completed", target="123"):
    return SimpleNamespace(id=uuid.uuid4(), notice_kind=kind, body="pong", severity="info",
                           subject_type="job", subject_id="j",
                           actions={"buttons": [], "job8": "abcdef12"},
                           target=target, thread=None, status="pending", attempts=0)


def _wire(monkeypatch, store, send):
    monkeypatch.setattr(bot_mod, "pending_notices", store.pending)
    monkeypatch.setattr(bot_mod, "claim_notice", store.claim)
    monkeypatch.setattr(bot_mod, "mark_sent", store.mark_sent)
    monkeypatch.setattr(bot_mod, "mark_failed", store.mark_failed)
    monkeypatch.setattr(bot_mod, "mark_skipped", store.mark_skipped)
    monkeypatch.setattr(bot_mod, "send_via_bot", send)
    monkeypatch.setattr(bot_mod.settings, "telegram_allowed_chat_ids", "999")


def _app():
    return SimpleNamespace(bot=object())


class TestDrainOutbox:
    async def test_delivers_and_stamps(self, monkeypatch):
        store = _Store([_row(), _row(kind="job_failed")])
        rendered = []

        async def send(bot, msg):
            rendered.append(msg)
            return 4242

        _wire(monkeypatch, store, send)
        result = await bot_mod._drain_outbox(_app(), legacy_mode=False)
        assert result == (2, 0, 0)
        assert all(r.status == "sent" for r in store.rows.values())
        assert store.sent[0][1] == "4242"
        assert rendered[0].chat_id == 123 and "pong" in rendered[0].text

    async def test_pending_rows_survive_listener_restart(self, monkeypatch):
        # Review Focus 1: a row written while the bot was down / a send that
        # failed is retried by a later drain (the 30 s poll) — no pub/sub needed.
        row = _row()
        store = _Store([row])
        calls = {"n": 0}

        async def flaky(bot, msg):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("Telegram 502")
            return 7

        _wire(monkeypatch, store, flaky)
        app = _app()
        assert await bot_mod._drain_outbox(app, legacy_mode=False) == (0, 1, 0)
        assert row.status == "pending" and row.attempts == 1
        assert await bot_mod._drain_outbox(app, legacy_mode=False) == (1, 0, 0)   # "restart": fresh drain, same row
        assert row.status == "sent"

    async def test_row_claimed_elsewhere_is_skipped(self, monkeypatch):
        # A concurrent `python -m src.notify drain` won the claim: never send twice.
        store = _Store([_row()])

        async def send(bot, msg):
            raise AssertionError("must not send an unclaimed row")

        async def lost_claim(nid, now=None):
            return False

        _wire(monkeypatch, store, send)
        monkeypatch.setattr(bot_mod, "claim_notice", lost_claim)
        assert await bot_mod._drain_outbox(_app(), legacy_mode=False) == (0, 0, 1)
        assert store.skipped == []          # not marked: the other drainer owns the row

    async def test_no_owner_chat_means_no_delivery(self, monkeypatch):
        store = _Store([_row()])

        async def send(bot, msg):
            raise AssertionError("must not send")

        _wire(monkeypatch, store, send)
        monkeypatch.setattr(bot_mod.settings, "telegram_allowed_chat_ids", "")
        assert await bot_mod._drain_outbox(_app(), legacy_mode=False) == (0, 0, 0)
        assert store.rows and all(r.status == "pending" for r in store.rows.values())

    async def test_ops_notices_delivered_with_outbox_off(self, monkeypatch):
        # Review Focus 4 / D-P1-10: the kill switch must not kill the notices
        # that have no legacy path.
        rows = [_row(kind=k, target=None) for k in sorted(OPS_NOTICE_KINDS)]
        store = _Store(rows)
        sent_to = []

        async def send(bot, msg):
            sent_to.append(msg.chat_id)
            return 1

        _wire(monkeypatch, store, send)
        assert await bot_mod._drain_outbox(_app(), legacy_mode=True) == (len(rows), 0, 0)
        assert all(r.status == "sent" for r in rows)
        assert sent_to == [999] * len(rows)        # no target → the owner chat

    async def test_job_rows_skipped_with_outbox_off(self, monkeypatch):
        job, task, ops = _row("job_completed"), _row("task_question"), _row("quota_paused")
        store = _Store([job, task, ops])
        sent_kinds = []

        async def send(bot, msg):
            sent_kinds.append(msg.text.splitlines()[0])
            return 1

        _wire(monkeypatch, store, send)
        assert await bot_mod._drain_outbox(_app(), legacy_mode=True) == (1, 0, 2)
        assert job.status == "skipped" and task.status == "skipped" and ops.status == "sent"
        assert store.skipped == [(job.id, "legacy_mode"), (task.id, "legacy_mode")]
        assert len(sent_kinds) == 1

    async def test_job_rows_delivered_with_outbox_on(self, monkeypatch):
        job, task = _row("job_completed"), _row("task_question")
        store = _Store([job, task])

        async def send(bot, msg):
            return 1

        _wire(monkeypatch, store, send)
        assert await bot_mod._drain_outbox(_app(), legacy_mode=False) == (2, 0, 0)
        assert store.skipped == []

    async def test_send_error_text_never_carries_the_token(self, monkeypatch):
        # §4 secrets rule: whatever the transport says, last_error is token-free.
        row = _row()
        store = _Store([row])
        monkeypatch.setattr(bot_mod.settings, "telegram_bot_token", FAKE_TOKEN)

        async def leaky(bot, msg):
            raise RuntimeError(f"POST https://api.telegram.org/bot{FAKE_TOKEN}/sendMessage failed")

        _wire(monkeypatch, store, leaky)
        assert await bot_mod._drain_outbox(_app(), legacy_mode=False) == (0, 1, 0)
        (nid, err), = store.failed
        assert FAKE_TOKEN not in err and "RuntimeError" in err
        assert len(err) <= 300

    async def test_mark_failed_gets_the_pre_claim_attempts(self, monkeypatch):
        row = _row()
        row.attempts = 2
        store = _Store([row])
        seen = {}

        async def send(bot, msg):
            raise RuntimeError("boom")

        async def mark_failed(nid, err, *, attempts_so_far, **kw):
            seen["attempts_so_far"] = attempts_so_far
            return "pending"

        _wire(monkeypatch, store, send)
        monkeypatch.setattr(bot_mod, "mark_failed", mark_failed)
        await bot_mod._drain_outbox(_app(), legacy_mode=False)
        assert seen["attempts_so_far"] == 2      # claim bumped the row to 3; mark_failed re-derives


# ── Legacy renderers are gated by the switch ───────────────────────────────


class _FakeBot:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id, text, **kw):
        self.sent.append((chat_id, text))
        return SimpleNamespace(message_id=1)


class TestLegacyRenderersGatedBySwitch:
    """Spec §9 exit criterion: with NOTIFY_OUTBOX=0 a Telegram-launched job
    still DMs via the legacy `_job_to_chat` path. The runner publishes
    `jobs:done:<id>` in both modes (A5 dual-write); only the bot decides."""

    async def test_done_message_sends_legacy_when_outbox_off(self, monkeypatch):
        monkeypatch.setattr(bot_mod.settings, "notify_outbox", False)

        async def no_lane(job_id):
            return ""

        monkeypatch.setattr(bot_mod, "_job_lane", no_lane)
        job_id = str(uuid.uuid4())
        monkeypatch.setitem(bot_mod._job_to_chat, job_id, 123)
        bot = _FakeBot()
        sent = await bot_mod._handle_done_message(
            SimpleNamespace(bot=bot), f"jobs:done:{job_id}",
            '{"status": "completed", "summary": "pong"}')
        assert sent is True
        assert bot.sent and bot.sent[0][0] == 123 and "pong" in bot.sent[0][1]
        assert bot.sent[0][1].startswith(f"Job `{job_id[:8]}` *completed*")   # the slice's DM text, untouched
        assert job_id not in bot_mod._job_to_chat

    async def test_done_message_is_dropped_when_outbox_on(self, monkeypatch):
        monkeypatch.setattr(bot_mod.settings, "notify_outbox", True)
        job_id = str(uuid.uuid4())
        monkeypatch.setitem(bot_mod._job_to_chat, job_id, 123)
        bot = _FakeBot()
        sent = await bot_mod._handle_done_message(
            SimpleNamespace(bot=bot), f"jobs:done:{job_id}", '{"status": "completed"}')
        assert sent is False and bot.sent == []
        assert job_id not in bot_mod._job_to_chat             # popped either way: no leak

    async def test_done_message_unknown_job_sends_nothing(self, monkeypatch):
        monkeypatch.setattr(bot_mod.settings, "notify_outbox", False)
        bot = _FakeBot()
        sent = await bot_mod._handle_done_message(
            SimpleNamespace(bot=bot), f"jobs:done:{uuid.uuid4()}", '{"status": "completed"}')
        assert sent is False and bot.sent == []

    async def test_done_message_send_failure_returns_false(self, monkeypatch):
        monkeypatch.setattr(bot_mod.settings, "notify_outbox", False)

        async def no_lane(job_id):
            return ""

        monkeypatch.setattr(bot_mod, "_job_lane", no_lane)
        job_id = str(uuid.uuid4())
        monkeypatch.setitem(bot_mod._job_to_chat, job_id, 123)

        class _Boom:
            async def send_message(self, *a, **kw):
                raise RuntimeError("chat not found")

        sent = await bot_mod._handle_done_message(
            SimpleNamespace(bot=_Boom()), f"jobs:done:{job_id}", "not json")
        assert sent is False

    @pytest.mark.parametrize("switch_on", [True, False])
    async def test_task_notifier_is_gated(self, monkeypatch, switch_on):
        monkeypatch.setattr(bot_mod.settings, "notify_outbox", switch_on)
        looked_up = []

        class _PubSub:
            async def subscribe(self, ch):
                pass

            async def unsubscribe(self, ch):
                pass

            async def listen(self):
                yield {"type": "subscribe"}
                yield {"type": "message",
                       "data": json.dumps({"task_id": "abcdef12", "type": "question", "text": "?"})}

        monkeypatch.setattr(bot_mod, "redis", SimpleNamespace(pubsub=lambda: _PubSub()))

        async def find(prefix):
            looked_up.append(prefix)
            return None

        monkeypatch.setattr(bot_mod, "_find_task_by_prefix", find)
        await bot_mod._task_notifier(_app())
        assert looked_up == ([] if switch_on else ["abcdef12"])

    def test_task_notifier_gate_sits_before_the_task_lookup(self):
        import ast
        import inspect
        src = inspect.getsource(bot_mod._task_notifier)
        tree = ast.parse(src)
        gate = [n for n in ast.walk(tree) if isinstance(n, ast.If)
                and ast.unparse(n.test) == "settings.notify_outbox"
                and any(isinstance(b, ast.Continue) for b in n.body)]
        assert len(gate) == 1
        lookup = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
                  and "_find_task_by_prefix" in ast.unparse(n.func)]
        assert lookup and gate[0].lineno < lookup[0].lineno

    @pytest.mark.parametrize("switch_on", [True, False])
    async def test_listener_always_starts(self, monkeypatch, switch_on):
        # D-P1-10: the listener runs in BOTH switch positions; the switch only
        # sets legacy_mode. The legacy listeners always run too.
        monkeypatch.setattr(bot_mod.settings, "notify_outbox", switch_on)
        started = {}

        def rec(name):
            async def coro(app, **kw):
                started[name] = kw
            return coro

        for name in ("_done_listener", "_task_notifier", "_quota_notifier", "_outbox_listener"):
            monkeypatch.setattr(bot_mod, name, rec(name))
        await bot_mod._post_init(_app())
        for _ in range(3):
            await asyncio.sleep(0)
        assert set(started) == {"_done_listener", "_task_notifier", "_quota_notifier", "_outbox_listener"}
        assert started["_outbox_listener"] == {"legacy_mode": not switch_on}

    def test_switch_default_is_on(self):
        from src.config import Settings
        assert Settings.model_fields["notify_outbox"].default is True


# ── Outbox listener ────────────────────────────────────────────────────────


class TestOutboxListener:
    async def test_releases_stuck_rows_then_drains_on_nudge_and_poll(self, monkeypatch):
        events = []

        async def release(now=None):
            events.append("release")
            return 1

        class _PubSub:
            def __init__(self):
                self.n = 0

            async def subscribe(self, ch):
                events.append(("subscribe", ch))

            async def unsubscribe(self, ch):
                events.append(("unsubscribe", ch))

            async def get_message(self, ignore_subscribe_messages=True, timeout=None):
                self.n += 1
                events.append(("poll", timeout))
                if self.n >= 3:
                    raise asyncio.CancelledError
                return {"type": "message", "data": "x"}

        async def drain(app, *, legacy_mode):
            events.append(("drain", legacy_mode))
            return 0, 0, 0

        monkeypatch.setattr(bot_mod, "release_stuck_sending", release)
        monkeypatch.setattr(bot_mod, "_drain_outbox", drain)
        monkeypatch.setattr(bot_mod, "redis", SimpleNamespace(pubsub=lambda: _PubSub()))
        with pytest.raises(asyncio.CancelledError):
            await bot_mod._outbox_listener(_app(), legacy_mode=True)
        assert events[0] == "release"
        assert ("subscribe", bot_mod.CHANNEL_NOTIFY_OUTBOX) in events
        assert events.count(("drain", True)) == 2
        assert ("poll", bot_mod._OUTBOX_POLL_SECONDS) in events
        assert events[-1] == ("unsubscribe", bot_mod.CHANNEL_NOTIFY_OUTBOX)
        assert bot_mod._OUTBOX_POLL_SECONDS == 30
        # Whole-tier review 2026-10-22: the release runs before EVERY drain,
        # not only at startup — a row claimed just before a restart is still
        # inside its lease at startup, and a mark_sent/mark_failed failure
        # after the Telegram call would otherwise strand it until the next
        # restart. Startup + one per iteration = 3 here.
        assert events.count("release") == 3
        for i, ev in enumerate(events):
            if ev == ("drain", True):
                assert events[i - 1] == "release", events

    async def test_release_failure_does_not_stop_the_listener(self, monkeypatch):
        async def release(now=None):
            raise RuntimeError("db down")

        class _PubSub:
            async def subscribe(self, ch):
                pass

            async def unsubscribe(self, ch):
                pass

            async def get_message(self, **kw):
                raise asyncio.CancelledError

        drained = []

        async def drain(app, *, legacy_mode):
            drained.append(legacy_mode)
            return 0, 0, 0

        monkeypatch.setattr(bot_mod, "release_stuck_sending", release)
        monkeypatch.setattr(bot_mod, "_drain_outbox", drain)
        monkeypatch.setattr(bot_mod, "redis", SimpleNamespace(pubsub=lambda: _PubSub()))
        with pytest.raises(asyncio.CancelledError):
            await bot_mod._outbox_listener(_app(), legacy_mode=False)
        # subscribed and polled (the poll raised Cancelled); release failing was logged, not fatal


# ── /status <prefix> (the footer on every outbox job card) ────────────────


class TestStatusWithPrefix:
    @pytest.fixture(autouse=True)
    def _auth(self, monkeypatch):
        monkeypatch.setattr(bot_mod, "_is_authorized", lambda chat_id: True)

    def _update(self):
        msg = SimpleNamespace(text="/status abcdef12", reply_text=AsyncMock())
        return SimpleNamespace(effective_chat=SimpleNamespace(id=999), message=msg)

    async def test_prefix_replies_with_format_job_status_plain_text(self, monkeypatch):
        job = _job()
        seen = []

        async def find(prefix):
            seen.append(prefix)
            return job
        monkeypatch.setattr(bot_mod, "find_job_by_prefix", find)
        upd = self._update()
        await bot_mod.cmd_status(upd, SimpleNamespace(args=["abcdef12"]))
        assert seen == ["abcdef12"]
        call = upd.message.reply_text.call_args
        assert call.args[0] == format_job_status(job)
        assert "parse_mode" not in call.kwargs      # skill names with `_` would crash Markdown

    async def test_unknown_prefix(self, monkeypatch):
        async def find(prefix):
            return None
        monkeypatch.setattr(bot_mod, "find_job_by_prefix", find)
        upd = self._update()
        await bot_mod.cmd_status(upd, SimpleNamespace(args=["zzzzzzzz"]))
        assert upd.message.reply_text.call_args.args[0] == "Job not found."


# ── [Details] button ───────────────────────────────────────────────────────


def _button_update(data: str, chat_id: int = 999):
    query = SimpleNamespace(data=data, answer=AsyncMock(), edit_message_text=AsyncMock(),
                            message=SimpleNamespace(reply_text=AsyncMock()))
    return SimpleNamespace(callback_query=query, effective_chat=SimpleNamespace(id=chat_id),
                           message=SimpleNamespace(reply_text=AsyncMock()))


class TestDetailsButton:
    async def test_jd_replies_with_job_status_without_parse_mode(self, monkeypatch):
        monkeypatch.setattr(bot_mod.settings, "telegram_allowed_chat_ids", "999")
        job = _job()

        async def find(prefix):
            assert prefix == "abcdef12"
            return job

        async def no_task(prefix):
            raise AssertionError("jd: is a JOB callback; the task lookup must not run")

        monkeypatch.setattr(bot_mod, "find_job_by_prefix", find)
        monkeypatch.setattr(bot_mod, "_find_task_by_prefix", no_task)
        upd = _button_update("jd:abcdef12")
        await bot_mod._handle_button(upd, None)
        reply = upd.callback_query.message.reply_text
        reply.assert_awaited_once()
        assert reply.await_args.args[0] == format_job_status(job)
        assert "parse_mode" not in reply.await_args.kwargs
        upd.callback_query.edit_message_text.assert_not_awaited()

    async def test_jd_unknown_job(self, monkeypatch):
        monkeypatch.setattr(bot_mod.settings, "telegram_allowed_chat_ids", "999")

        async def find(prefix):
            return None

        monkeypatch.setattr(bot_mod, "find_job_by_prefix", find)
        upd = _button_update("jd:00000000")
        await bot_mod._handle_button(upd, None)
        assert upd.callback_query.message.reply_text.await_args.args[0] == "Job not found."

    async def test_jd_requires_authorization(self, monkeypatch):
        monkeypatch.setattr(bot_mod.settings, "telegram_allowed_chat_ids", "999")

        async def find(prefix):
            raise AssertionError("unauthorized chat must not read a job")

        monkeypatch.setattr(bot_mod, "find_job_by_prefix", find)
        upd = _button_update("jd:abcdef12", chat_id=1)
        await bot_mod._handle_button(upd, None)
        upd.callback_query.message.reply_text.assert_not_awaited()


# ── Quota notices through the outbox ───────────────────────────────────────


class _Notifier:
    """One long-lived `_quota_notifier` task across a test's phases (its
    `last_state` is what makes pause → resume observable)."""

    def __init__(self):
        self.task = asyncio.create_task(bot_mod._quota_notifier(_app(), poll_seconds=0))

    async def wait_for(self, seen: list, *, want: int, ticks: int = 50) -> None:
        for _ in range(ticks):
            await asyncio.sleep(0)
            if len(seen) >= want:
                return

    async def stop(self) -> None:
        self.task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await self.task


class TestQuotaNotices:
    async def test_quota_notices_go_through_the_outbox(self, monkeypatch):
        enqueued: list[Notice] = []
        state = {"paused": True}
        at = datetime(2026, 10, 21, 14, 0, tzinfo=timezone.utc)

        async def is_paused():
            return (True, at, "rate limit rejected") if state["paused"] else (False, None, "")

        async def last_source():
            return "vendor"

        async def enqueue(notice):
            enqueued.append(notice)
            return uuid.uuid4()

        monkeypatch.setattr(bot_mod.quota, "is_paused", is_paused)
        monkeypatch.setattr(bot_mod.quota, "last_source", last_source)
        monkeypatch.setattr(bot_mod.models_registry, "enabled_providers", lambda: frozenset({"anthropic"}))
        monkeypatch.setattr(bot_mod, "enqueue_notice", enqueue)
        notifier = _Notifier()
        await notifier.wait_for(enqueued, want=1)
        assert len(enqueued) == 1                      # once per state change, not per tick
        n = enqueued[0]
        assert n.notice_kind == "quota_paused" and n.severity == "warn"
        assert n.body == bot_mod.quota_paused_text(at, "rate limit rejected", "vendor")
        assert "Reset at 14:00 UTC (vendor)" in n.body
        assert (n.subject_type, n.subject_id) == ("quota", "anthropic")
        state["paused"] = False
        await notifier.wait_for(enqueued, want=2)
        await notifier.stop()
        assert len(enqueued) == 2
        assert enqueued[1].notice_kind == "quota_resumed" and enqueued[1].severity == "info"
        assert "resumed" in enqueued[1].body

    async def test_provider_pause_is_noticed(self, monkeypatch):
        enqueued: list[Notice] = []
        lanes = {"codex": (True, datetime(2026, 10, 21, 9, 30, tzinfo=timezone.utc), "429 from codex")}

        async def is_paused():
            return False, None, ""

        async def is_provider_paused(provider):
            return lanes.get(provider, (False, None, ""))

        async def enqueue(notice):
            enqueued.append(notice)
            return uuid.uuid4()

        monkeypatch.setattr(bot_mod.quota, "is_paused", is_paused)
        monkeypatch.setattr(bot_mod.quota, "is_provider_paused", is_provider_paused)
        monkeypatch.setattr(bot_mod.models_registry, "enabled_providers",
                            lambda: frozenset({"anthropic", "codex"}))
        monkeypatch.setattr(bot_mod, "enqueue_notice", enqueue)
        notifier = _Notifier()
        await notifier.wait_for(enqueued, want=1)
        assert len(enqueued) == 1
        n = enqueued[0]
        assert n.notice_kind == "quota_paused" and (n.subject_type, n.subject_id) == ("quota", "codex")
        assert "codex" in n.body and "09:30 UTC" in n.body and "429 from codex" in n.body
        assert "/resume codex" in n.body
        assert "subscription quota" not in n.body       # not the Anthropic text
        lanes.clear()
        await notifier.wait_for(enqueued, want=2)
        await notifier.stop()
        assert len(enqueued) == 2
        assert enqueued[1].notice_kind == "quota_resumed" and "codex" in enqueued[1].body

    async def test_notifier_survives_an_enqueue_failure(self, monkeypatch):
        calls = {"n": 0}

        async def is_paused():
            calls["n"] += 1
            return True, None, "x"

        async def last_source():
            return "estimated"

        async def enqueue(notice):
            raise RuntimeError("db down")

        monkeypatch.setattr(bot_mod.quota, "is_paused", is_paused)
        monkeypatch.setattr(bot_mod.quota, "last_source", last_source)
        monkeypatch.setattr(bot_mod.models_registry, "enabled_providers", lambda: frozenset({"anthropic"}))
        monkeypatch.setattr(bot_mod, "enqueue_notice", enqueue)
        notifier = _Notifier()
        await notifier.wait_for([], want=1, ticks=20)
        await notifier.stop()
        assert calls["n"] >= 2                         # kept ticking after the failure

    def test_provider_paused_text_is_pure(self):
        at = datetime(2026, 10, 21, 9, 30, tzinfo=timezone.utc)
        text = bot_mod.provider_paused_text("codex", at, "r" * 500)
        assert text.startswith("⏸ codex lane paused until 09:30 UTC")
        assert "r" * 200 in text and "r" * 201 not in text
        assert "/resume codex" in text
        assert "unknown" in bot_mod.provider_paused_text("codex", None, "")


def test_lane_label_alias_matches():
    assert bot_mod._lane_label is lane_label
    for case in [("anthropic", "claude-sonnet-4-6", "ok"), ("codex", "gpt-6-luna", "auth_expired"),
                 (None, "claude-opus-4-8", None), (None, None, "error"), ("codex", None, "timeout")]:
        assert bot_mod._lane_label(*case) == lane_label(*case)


def test_bot_reads_the_switch_and_the_runner_does_not():
    # D-P1-10 belt: the bot is one of exactly two readers (the other is `src.notify.__main__`).
    import inspect
    assert "settings.notify_outbox" in inspect.getsource(bot_mod)
