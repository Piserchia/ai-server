"""
Telegram renderer — the ONLY code that knows the 4096-char / 64-byte callback
/ 8-button limits. Pure, plus `send_via_http` driven through an
`httpx.MockTransport` (no network) and the `python -m src.notify` CLI driven
with the sender and the row writer stubbed.

Design of record: P0 plan Task 5, re-cut by A4 of
docs/superpowers/plans/2026-10-21-observability-phase1-recut.md.

Run: PIPENV_DONT_LOAD_ENV=1 SERVER_ROOT="$PWD" pipenv run pytest tests/test_notify_telegram.py -q -p no:cacheprovider
"""

from __future__ import annotations

import json
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from src.notify.outbox import Notice
from src.notify.telegram import (
    CALLBACK_LIMIT_BYTES,
    MAX_BUTTONS,
    TELEGRAM_TEXT_LIMIT,
    TelegramMessage,
    TelegramSendError,
    build_buttons,
    fit_text,
    keyboard_markup,
    render_telegram,
    send_via_bot,
    send_via_http,
    validate_callback,
)

OWNER = 999
TOKEN = "123456789:AAFakeTokenForTheLeakTest_notReal"


def _n(**over):
    base = dict(notice_kind="job_completed", body="pong", severity="info",
                subject_type="job", subject_id="abcdef12-0000", actions={"buttons": [], "job8": "abcdef12"},
                target="123", thread="777")
    base.update(over)
    return Notice(**base)


class TestLimits:
    def test_constants(self):
        assert (TELEGRAM_TEXT_LIMIT, CALLBACK_LIMIT_BYTES, MAX_BUTTONS) == (4096, 64, 8)

    def test_fit_text_never_exceeds_limit(self):
        text = fit_text("✅ done", "x" * 10_000, footer="\n/status abcdef12")
        assert len(text) <= 4096
        assert text.startswith("✅ done") and text.endswith("/status abcdef12")
        assert "… (truncated)" in text

    def test_fit_text_short_untouched(self):
        assert fit_text("h", "body", footer="") == "h\nbody"

    def test_callback_over_64_bytes_rejected(self):
        with pytest.raises(ValueError):
            validate_callback("choice:" + "é" * 40)     # 87 bytes
        assert validate_callback("jd:abcdef12") == "jd:abcdef12"

    def test_buttons_capped_at_8_total(self):
        rows = [[[f"b{i}", f"choice:abcdef12:{i}"]] for i in range(12)]
        out = build_buttons({"buttons": rows})
        assert sum(len(r) for r in out) == 8

    def test_buttons_none_or_missing(self):
        assert build_buttons(None) == () and build_buttons({}) == ()


class TestRender:
    def test_job_completed_targets_chat_and_thread(self):
        msg = render_telegram(_n(), owner_chat_id=OWNER)
        assert isinstance(msg, TelegramMessage)
        assert msg.chat_id == 123 and msg.reply_to_message_id == 777
        assert msg.text.startswith("✅ done") and "/status abcdef12" in msg.text
        assert msg.buttons == ()

    def test_owner_fallback_when_no_target(self):
        msg = render_telegram(_n(target=None, thread=None), owner_chat_id=OWNER)
        assert msg.chat_id == OWNER and msg.reply_to_message_id is None

    def test_non_numeric_target_falls_back_to_owner(self):
        assert render_telegram(_n(target="dashboard"), owner_chat_id=OWNER).chat_id == OWNER

    def test_failed_job_has_details_button(self):
        msg = render_telegram(_n(notice_kind="job_failed", severity="warn",
                                 actions={"buttons": [[["Details", "jd:abcdef12"]]], "job8": "abcdef12"}),
                              owner_chat_id=OWNER)
        assert msg.text.startswith("❌ failed")
        assert msg.buttons == ((("Details", "jd:abcdef12"),),)

    def test_every_notice_kind_renders(self):
        from src.notify.outbox import NOTICE_KINDS
        for kind in sorted(NOTICE_KINDS):
            msg = render_telegram(_n(notice_kind=kind, actions=None), owner_chat_id=OWNER)
            assert msg.text and len(msg.text) <= 4096
            assert not msg.text.startswith(kind), f"{kind} has no header"

    @pytest.mark.parametrize("kind,expected", [
        ("task_approval_request", "✋ task abcdef12 needs your approval"),
        ("task_question", "❓ task abcdef12 needs your input — reply to this message"),
        ("task_choices", "\U0001f500 task abcdef12 — pick one"),
        ("task_progress", "\U0001f504 progress · task abcdef12"),
        ("task_plan", "\U0001f4cb plan (executing now) · task abcdef12"),
    ])
    def test_task_cards_name_the_task(self, kind, expected):
        # whole-tier review 2026-10-22: the legacy renderer wrote `Task <prefix>`
        # on every card; a card without a thread is otherwise unattributable.
        msg = render_telegram(_n(notice_kind=kind, actions={"prefix": "abcdef12", "buttons": []}),
                              owner_chat_id=OWNER)
        assert msg.text.startswith(expected), msg.text

    def test_task_card_without_prefix_keeps_the_plain_header(self):
        msg = render_telegram(_n(notice_kind="task_failed", actions=None), owner_chat_id=OWNER)
        assert msg.text.startswith("❌ task failed")

    def test_renders_a_row_object_too(self):
        row = SimpleNamespace(notice_kind="ops_alert", body="runner down", severity="critical",
                              subject_type="ops", subject_id=None, actions=None, target=None, thread=None)
        assert render_telegram(row, owner_chat_id=OWNER).text.startswith("🚨 ops")

    def test_keyboard_markup_is_lazy_and_none_when_empty(self):
        assert keyboard_markup(()) is None
        markup = keyboard_markup(((("Details", "jd:abcdef12"),),))
        assert type(markup).__name__ == "InlineKeyboardMarkup"
        assert markup.inline_keyboard[0][0].callback_data == "jd:abcdef12"


class TestSendViaBot:
    async def test_sends_and_returns_message_id(self):
        bot = SimpleNamespace(send_message=AsyncMock(return_value=SimpleNamespace(message_id=55)))
        msg = TelegramMessage(chat_id=1, text="hi", buttons=(), reply_to_message_id=7)
        assert await send_via_bot(bot, msg) == 55
        kwargs = bot.send_message.await_args.kwargs
        assert kwargs["chat_id"] == 1 and kwargs["reply_to_message_id"] == 7 and "parse_mode" not in kwargs

    async def test_missing_reply_target_is_retried_without_it(self):
        bot = SimpleNamespace(send_message=AsyncMock(
            side_effect=[RuntimeError("Bad Request: message to be replied not found"),
                         SimpleNamespace(message_id=56)]))
        msg = TelegramMessage(chat_id=1, text="hi", reply_to_message_id=7)
        assert await send_via_bot(bot, msg) == 56
        assert "reply_to_message_id" not in bot.send_message.await_args.kwargs


def _mock_transport(status: int, body: dict | None = None, *, raise_exc: Exception | None = None,
                    seen: list | None = None) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        if raise_exc is not None:
            raise raise_exc
        return httpx.Response(status, json=body if body is not None else {})
    return httpx.MockTransport(handler)


class TestSendViaHttp:
    async def test_posts_and_returns_the_message_id(self):
        seen: list = []
        transport = _mock_transport(200, {"ok": True, "result": {"message_id": 77}}, seen=seen)
        msg = TelegramMessage(chat_id=5, text="hi", buttons=((("Details", "jd:abcdef12"),),),
                              reply_to_message_id=9)
        assert await send_via_http(TOKEN, msg, transport=transport) == 77
        req = seen[0]
        assert req.url.path.endswith("/sendMessage") and TOKEN in str(req.url)
        form = dict(httpx.QueryParams(req.content.decode()))
        assert form["chat_id"] == "5" and form["reply_to_message_id"] == "9" and "parse_mode" not in form
        assert json.loads(form["reply_markup"])["inline_keyboard"][0][0]["callback_data"] == "jd:abcdef12"

    async def test_send_failure_never_leaks_the_token(self):
        # Review Focus 8: a Telegram error must not persist the bot token.
        # httpx's own messages carry the request URL (with the token in it);
        # TelegramSendError is the chokepoint that keeps it out of rows/logs.
        transport = _mock_transport(400, {"ok": False, "description": "Bad Request: chat not found"})
        with pytest.raises(TelegramSendError) as ei:
            await send_via_http(TOKEN, TelegramMessage(chat_id=5, text="hi"), transport=transport)
        text = str(ei.value)
        assert text == "telegram 400: Bad Request: chat not found"
        assert TOKEN not in text and "api.telegram.org" not in text and "http" not in text

    async def test_non_json_error_uses_the_reason_phrase(self):
        transport = httpx.MockTransport(lambda r: httpx.Response(502, text="<html>bad gateway</html>"))
        with pytest.raises(TelegramSendError, match=r"^telegram 502: Bad Gateway$"):
            await send_via_http(TOKEN, TelegramMessage(chat_id=5, text="hi"), transport=transport)

    async def test_transport_errors_are_wrapped_by_type_name_only(self):
        transport = _mock_transport(200, raise_exc=httpx.ConnectError(
            "All connection attempts failed", request=httpx.Request("POST", f"https://api.telegram.org/bot{TOKEN}/x")))
        with pytest.raises(TelegramSendError) as ei:
            await send_via_http(TOKEN, TelegramMessage(chat_id=5, text="hi"), transport=transport)
        assert str(ei.value) == "ConnectError" and TOKEN not in str(ei.value)

    async def test_malformed_success_body_is_wrapped_too(self):
        transport = _mock_transport(200, {"ok": True})
        with pytest.raises(TelegramSendError) as ei:
            await send_via_http(TOKEN, TelegramMessage(chat_id=5, text="hi"), transport=transport)
        assert TOKEN not in str(ei.value)


class TestCli:
    """`python -m src.notify send|drain` with the HTTP sender routed through a
    MockTransport and the row writer recorded."""

    @pytest.fixture(autouse=True)
    def _cli(self, monkeypatch):
        from src.config import settings
        from src.notify import __main__ as cli
        self.cli = cli
        monkeypatch.setattr(settings, "telegram_bot_token", TOKEN)
        monkeypatch.setattr(settings, "telegram_allowed_chat_ids", "999")
        self.recorded: list[dict] = []
        self.row_id = uuid.uuid4()

        async def _record(notice, *, status, external_ref=None, last_error=None):
            self.recorded.append(dict(notice=notice, status=status, external_ref=external_ref,
                                      last_error=last_error))
            return self.row_id
        monkeypatch.setattr(cli, "record_notice", _record)
        # `drain` releases stuck `sending` rows before selecting (whole-tier
        # review 2026-10-22); default it to "nothing stuck" so the drain tests
        # never touch a database.
        self.released: list = []

        async def _release(now=None):
            self.released.append("release")
            return 0
        monkeypatch.setattr(cli, "release_stuck_sending", _release)

    def _route(self, monkeypatch, transport):
        real = self.cli.send_via_http

        async def _send(token, msg, **kw):
            return await real(token, msg, transport=transport)
        monkeypatch.setattr(self.cli, "send_via_http", _send)

    def test_send_delivers_then_records_sent(self, monkeypatch, capsys):
        self._route(monkeypatch, _mock_transport(200, {"ok": True, "result": {"message_id": 31}}))
        rc = self.cli.main(["send", "--kind", "ops_alert", "--severity", "warn", "--text", "runner down",
                            "--subject", f"job:{uuid.uuid4()}"])
        assert rc == 0
        assert self.recorded[0]["status"] == "sent" and self.recorded[0]["external_ref"] == "31"
        assert self.recorded[0]["notice"].notice_kind == "ops_alert"
        assert f"notice {self.row_id} sent" in capsys.readouterr().out

    def test_send_failure_records_failed_and_exits_1_for_the_curl_fallback(self, monkeypatch, capsys):
        # Review Focus 8, CLI half: the recorded last_error and stdout carry
        # neither the token nor the URL.
        self._route(monkeypatch, _mock_transport(400, {"ok": False, "description": "Bad Request: chat not found"}))
        rc = self.cli.main(["send", "--kind", "ops_alert", "--text", "runner down"])
        assert rc == 1
        rec = self.recorded[0]
        assert rec["status"] == "failed" and rec["external_ref"] is None
        assert rec["last_error"] == "telegram 400: Bad Request: chat not found"
        out = capsys.readouterr()
        for blob in (rec["last_error"], out.out, out.err):
            assert TOKEN not in blob and "api.telegram.org" not in blob
        assert "chat not found" in out.out

    def test_send_redacts_the_token_defensively(self, monkeypatch, capsys):
        async def _leaky(token, msg, **kw):
            raise TelegramSendError(f"boom https://api.telegram.org/bot{token}/sendMessage")
        monkeypatch.setattr(self.cli, "send_via_http", _leaky)
        rc = self.cli.main(["send", "--kind", "ops_alert", "--text", "x"])
        assert rc == 1
        assert TOKEN not in self.recorded[0]["last_error"] and "[REDACTED]" in self.recorded[0]["last_error"]
        assert TOKEN not in capsys.readouterr().out

    def test_send_exits_1_when_neither_sent_nor_recorded(self, monkeypatch, capsys):
        self._route(monkeypatch, _mock_transport(400, {"ok": False, "description": "nope"}))

        async def _broken(notice, **kw):
            raise RuntimeError(f"db down https://api.telegram.org/bot{TOKEN}/x")
        monkeypatch.setattr(self.cli, "record_notice", _broken)
        assert self.cli.main(["send", "--kind", "ops_alert", "--text", "x"]) == 1
        err = capsys.readouterr().err
        assert "row not recorded" in err and TOKEN not in err

    def test_send_unknown_kind_is_refused(self, monkeypatch):
        with pytest.raises(ValueError):
            self.cli.main(["send", "--kind", "bogus", "--text", "x"])

    def test_send_without_telegram_configured_records_failed(self, monkeypatch):
        from src.config import settings
        monkeypatch.setattr(settings, "telegram_bot_token", "")
        assert self.cli.main(["send", "--kind", "ops_alert", "--text", "x"]) == 1
        assert self.recorded[0]["status"] == "failed" and "not configured" in self.recorded[0]["last_error"]

    def test_drain_claims_renders_sends_and_stamps(self, monkeypatch, capsys):
        from src.config import settings
        monkeypatch.setattr(settings, "notify_outbox", True)
        self._route(monkeypatch, _mock_transport(200, {"ok": True, "result": {"message_id": 41}}))
        rows = [SimpleNamespace(id=uuid.uuid4(), notice_kind="job_failed", body="b", severity="warn",
                                subject_type="job", subject_id="j", actions=None, target=None, thread=None,
                                attempts=0),
                SimpleNamespace(id=uuid.uuid4(), notice_kind="ops_alert", body="b", severity="warn",
                                subject_type=None, subject_id=None, actions=None, target=None, thread=None,
                                attempts=2)]
        claims = iter([True, False])
        sent: list = []
        monkeypatch.setattr(self.cli, "pending_notices", AsyncMock(return_value=rows))
        monkeypatch.setattr(self.cli, "claim_notice", AsyncMock(side_effect=lambda *_a, **_k: next(claims)))
        monkeypatch.setattr(self.cli, "mark_sent",
                            AsyncMock(side_effect=lambda nid, ref, **kw: sent.append((nid, ref, kw))))
        monkeypatch.setattr(self.cli, "mark_failed", AsyncMock())
        assert self.cli.main(["drain", "--limit", "5"]) == 0
        assert sent == [(rows[0].id, "41", {"subject_type": "job", "subject_id": "j"})]
        assert "drained sent=1 failed=0 skipped=1 pending_before=2" in capsys.readouterr().out

    def test_drain_releases_stuck_sending_rows_before_selecting(self, monkeypatch, capsys):
        # Same recovery as the bot listener (whole-tier review 2026-10-22): a
        # row a dead drainer left `sending` past its lease is released, and
        # the release runs BEFORE pending_notices so the freed row is in this
        # drain's selection.
        from src.config import settings
        monkeypatch.setattr(settings, "notify_outbox", True)
        self._route(monkeypatch, _mock_transport(200, {"ok": True, "result": {"message_id": 43}}))
        order: list = []

        async def _release(now=None):
            order.append("release")
            return 1

        async def _pending(limit=20):
            order.append("select")
            return []
        monkeypatch.setattr(self.cli, "release_stuck_sending", _release)
        monkeypatch.setattr(self.cli, "pending_notices", _pending)
        assert self.cli.main(["drain"]) == 0
        assert order == ["release", "select"]
        out = capsys.readouterr()
        assert "released 1 stuck sending row" in out.err
        assert "drained sent=0 failed=0 skipped=0 pending_before=0" in out.out

    def test_drain_release_failure_is_non_fatal_and_token_free(self, monkeypatch, capsys):
        from src.config import settings
        monkeypatch.setattr(settings, "notify_outbox", True)

        async def _release(now=None):
            raise RuntimeError(f"db down https://api.telegram.org/bot{TOKEN}/x")
        monkeypatch.setattr(self.cli, "release_stuck_sending", _release)
        monkeypatch.setattr(self.cli, "pending_notices", AsyncMock(return_value=[]))
        assert self.cli.main(["drain"]) == 0
        out = capsys.readouterr()
        assert "release_stuck_sending failed" in out.err and TOKEN not in out.err
        assert "drained sent=0" in out.out

    def test_drain_with_the_switch_off_skips_job_and_task_rows_but_sends_ops(self, monkeypatch, capsys):
        # Mirrors A6's legacy_mode: with NOTIFY_OUTBOX=0 the legacy listeners
        # still send job/task DMs, so a manual drain must not double-send them.
        from src.config import settings
        monkeypatch.setattr(settings, "notify_outbox", False)
        self._route(monkeypatch, _mock_transport(200, {"ok": True, "result": {"message_id": 42}}))
        rows = [SimpleNamespace(id=uuid.uuid4(), notice_kind="task_failed", body="b", severity="warn",
                                subject_type="task", subject_id="t", actions=None, target=None, thread=None,
                                attempts=0),
                SimpleNamespace(id=uuid.uuid4(), notice_kind="quota_paused", body="b", severity="warn",
                                subject_type=None, subject_id=None, actions=None, target=None, thread=None,
                                attempts=0)]
        skipped: list = []
        sent: list = []
        monkeypatch.setattr(self.cli, "pending_notices", AsyncMock(return_value=rows))
        monkeypatch.setattr(self.cli, "claim_notice", AsyncMock(return_value=True))
        monkeypatch.setattr(self.cli, "mark_skipped",
                            AsyncMock(side_effect=lambda nid, reason: skipped.append((nid, reason))))
        monkeypatch.setattr(self.cli, "mark_sent",
                            AsyncMock(side_effect=lambda nid, ref, **kw: sent.append(nid)))
        monkeypatch.setattr(self.cli, "mark_failed", AsyncMock())
        assert self.cli.main(["drain"]) == 0
        assert skipped == [(rows[0].id, "legacy_mode")] and sent == [rows[1].id]
        assert "sent=1 failed=0 skipped=1" in capsys.readouterr().out

    def test_drain_failure_is_recorded_without_the_token(self, monkeypatch):
        from src.config import settings
        monkeypatch.setattr(settings, "notify_outbox", True)
        self._route(monkeypatch, _mock_transport(400, {"ok": False, "description": "Bad Request: chat not found"}))
        row = SimpleNamespace(id=uuid.uuid4(), notice_kind="ops_alert", body="b", severity="warn",
                              subject_type=None, subject_id=None, actions=None, target=None, thread=None,
                              attempts=1)
        failed: list = []
        monkeypatch.setattr(self.cli, "pending_notices", AsyncMock(return_value=[row]))
        monkeypatch.setattr(self.cli, "claim_notice", AsyncMock(return_value=True))
        monkeypatch.setattr(self.cli, "mark_sent", AsyncMock())
        monkeypatch.setattr(self.cli, "mark_failed",
                            AsyncMock(side_effect=lambda nid, err, **kw: failed.append((nid, err, kw))))
        assert self.cli.main(["drain"]) == 0
        nid, err, kw = failed[0]
        assert nid == row.id and err == "telegram 400: Bad Request: chat not found"
        assert kw["attempts_so_far"] == 1 and TOKEN not in err
