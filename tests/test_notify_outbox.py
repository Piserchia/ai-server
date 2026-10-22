"""
Notification outbox — pure builders + retry math, and the async wrappers
driven against a recording session (no DB, no Redis, no network).

Design of record: P0 plan Task 5 (docs/superpowers/plans/
2026-09-25-multi-model-platform-p0.md) re-cut by A4 of
docs/superpowers/plans/2026-10-21-observability-phase1-recut.md.

Run: PIPENV_DONT_LOAD_ENV=1 SERVER_ROOT="$PWD" pipenv run pytest tests/test_notify_outbox.py -q -p no:cacheprovider
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.dialects import postgresql

from src.gateway.jobs import ORIGIN_CHANNELS
from src.notify import outbox
from src.notify.outbox import (
    COMPLETION_DM_CHANNELS,
    MAX_ATTEMPTS,
    NOTICE_KINDS,
    OPS_NOTICE_KINDS,
    SENDING_LEASE_SECONDS,
    STATUSES,
    TASK_NOTIFY_TYPES,
    Notice,
    build_job_notice,
    build_ops_notice,
    build_task_notice,
    claim_notice,
    enqueue_notice,
    lane_label,
    mark_failed,
    mark_sent,
    mark_skipped,
    notice_kind_for_task_type,
    record_notice,
    release_stuck_sending,
    retry_delay_seconds,
    should_notify_job,
    transition_after_failure,
)

OUTBOX_SRC = Path(__file__).resolve().parent.parent / "src" / "notify" / "outbox.py"

JOB = uuid.uuid4()
NOW = datetime(2026, 10, 21, 3, 0, tzinfo=timezone.utc)


def _job(**over):
    base = dict(job_id=JOB, status="completed", kind="chat", resolved_skill="chat",
                summary="pong", error_message=None, terminal_reason="ok",
                origin_channel="telegram", origin_ref="123", origin_thread="777",
                created_by="telegram:123", task_id=None, model_served="claude-sonnet-4-6",
                resolved_provider="anthropic", resolved_model="claude-sonnet-4-6",
                num_turns=1, duration_seconds=3.2)
    base.update(over)
    return build_job_notice(**base)


class TestVocabulary:
    def test_every_tasks_notify_type_has_an_outbox_kind(self):
        # spec §9 P0 test gate: "every tasks:notify kind has an outbox equivalent"
        legacy = ("approval_request", "question", "choices", "plan", "plan_approval",
                  "completed", "progress", "failed", "review_flagged")   # telegram_bot._task_notifier
        assert TASK_NOTIFY_TYPES == legacy
        for t in legacy:
            # two asserts, not a chained comparison: `a == b in c` is valid
            # Python but reads as a precedence bug and invites a wrong "fix".
            assert notice_kind_for_task_type(t) == f"task_{t}"
            assert f"task_{t}" in NOTICE_KINDS

    def test_unknown_task_type_rejected(self):
        with pytest.raises(ValueError):
            notice_kind_for_task_type("bogus")

    def test_kinds_fit_column(self):
        assert all(len(k) <= 32 for k in NOTICE_KINDS)
        assert {"job_completed", "job_failed", "ops_alert", "credential_canary",
                "quota_paused", "quota_resumed", "schedule_deferred",
                "settings_override", "provider_enforcement"} <= NOTICE_KINDS

    def test_ops_kinds_are_everything_but_job_and_task(self):
        # A6's legacy_mode still delivers exactly these (D-P1-10).
        assert OPS_NOTICE_KINDS == frozenset(
            k for k in NOTICE_KINDS if not k.startswith(("job_", "task_")))
        assert OPS_NOTICE_KINDS and OPS_NOTICE_KINDS < NOTICE_KINDS
        assert "quota_paused" in OPS_NOTICE_KINDS and "job_failed" not in OPS_NOTICE_KINDS

    def test_statuses_include_sending(self):
        # `sending` = claimed by exactly one drainer (bot listener OR the CLI drain).
        assert STATUSES == ("pending", "sending", "sent", "failed", "skipped")

    def test_completion_dm_channels_subset_of_origin_channels(self):
        # Delta 5: the dashboard (`web`) is a human launch, `cli` stays per
        # spec §4.2, `pwa` is not an origin channel until Phase 2.
        assert COMPLETION_DM_CHANNELS == ("telegram", "web", "cli")
        assert set(COMPLETION_DM_CHANNELS) <= set(ORIGIN_CHANNELS)
        assert "pwa" not in ORIGIN_CHANNELS


class TestShouldNotify:
    def test_completed_task_less_job_dms(self):
        assert should_notify_job(status="completed", kind="chat", task_id=None,
                                 origin_channel="telegram")

    def test_completed_task_bound_job_is_covered_by_task_card(self):
        assert not should_notify_job(status="completed", kind="task", task_id=uuid.uuid4(),
                                     origin_channel="telegram")

    def test_failed_always_dms_even_task_bound(self):
        assert should_notify_job(status="failed", kind="task", task_id=uuid.uuid4(),
                                 origin_channel="telegram")

    def test_internal_kinds_never_dm(self):
        assert not should_notify_job(status="failed", kind="_writeback", task_id=None,
                                     origin_channel="scheduler")
        assert not should_notify_job(status="completed", kind="_evaluate", task_id=None,
                                     origin_channel="telegram")

    def test_cancelled_never_dms(self):
        assert not should_notify_job(status="cancelled", kind="chat", task_id=None,
                                     origin_channel="telegram")

    def test_scheduled_completion_is_quiet(self):
        # spec §4.5: per-schedule notify defaults to `failures` — 79 scheduler
        # completions a week must not become 79 DMs.
        assert not should_notify_job(status="completed", kind="atlas-report", task_id=None,
                                     origin_channel="scheduler")

    def test_dispatch_completion_is_quiet(self):
        # dispatch-mcp / event-trigger / self-diagnose / escalation children all
        # derive origin_channel="system" (origin_from_created_by).
        assert not should_notify_job(status="completed", kind="self-diagnose", task_id=None,
                                     origin_channel="system")
        assert not should_notify_job(status="completed", kind="chat", task_id=None,
                                     origin_channel=None)

    def test_scheduled_failure_still_dms(self):
        # The exit criterion: a scheduled FAILURE DMs within 60 s.
        assert should_notify_job(status="failed", kind="atlas-report", task_id=None,
                                 origin_channel="scheduler")
        assert should_notify_job(status="failed", kind="self-diagnose", task_id=None,
                                 origin_channel="system")

    def test_human_launchers_get_completion_dms(self):
        # Delta 5 (rewritten from P0): telegram / web / cli are eligible,
        # `pwa` is not an origin channel in Phase 1.
        for ch in ("telegram", "web", "cli"):
            assert should_notify_job(status="completed", kind="chat", task_id=None,
                                     origin_channel=ch), ch
        assert not should_notify_job(status="completed", kind="chat", task_id=None,
                                     origin_channel="pwa")

    def test_a_child_inherits_the_parents_eligibility(self):
        # spec §4.2: children inherit the parent's eligibility. A5 resolves the
        # PARENT's channel and passes that, so this pure function only has to
        # honour what it is given — both directions are asserted here.
        assert should_notify_job(status="completed", kind="chat", task_id=None,
                                 origin_channel="telegram")      # parent = Telegram launch
        assert not should_notify_job(status="completed", kind="chat", task_id=None,
                                     origin_channel="scheduler")  # parent = schedule row


class TestLaneLabel:
    def test_provider_and_model(self):
        assert lane_label("codex", "gpt-6-luna", "ok") == "codex/gpt-6-luna"
        assert lane_label("codex", "gpt-6-luna", None) == "codex/gpt-6-luna"

    def test_non_ok_reason_is_appended(self):
        assert lane_label("codex", "gpt-6-luna", "auth_expired") == "codex/gpt-6-luna · auth_expired"

    def test_pre_007_row_shows_model_alone_and_queued_row_nothing(self):
        assert lane_label(None, "claude-sonnet-4-6", "ok") == "claude-sonnet-4-6"
        assert lane_label(None, None, "ok") == ""
        assert lane_label(None, None, "timeout") == ""

    def test_matches_the_bot_definition(self):
        # A6 makes telegram_bot._lane_label a thin alias; until then both must agree.
        from src.gateway.telegram_bot import _lane_label
        cases = [("anthropic", "claude-sonnet-4-6", "ok"), ("codex", "gpt-6-luna", "auth_expired"),
                 (None, "claude-opus-4-8", None), (None, None, "error"), ("codex", None, "timeout")]
        for provider, model, reason in cases:
            assert lane_label(provider, model, reason) == _lane_label(provider, model, reason), (provider, model, reason)


class TestBuildJobNotice:
    def test_completed_telegram_job_targets_its_chat_and_thread(self):
        n = _job()
        assert isinstance(n, Notice)
        assert n.notice_kind == "job_completed" and n.severity == "info"
        assert n.target == "123" and n.thread == "777"
        assert n.subject_type == "job" and n.subject_id == str(JOB)
        assert "pong" in n.body and str(JOB)[:8] in n.body
        assert n.actions["buttons"] == []

    def test_build_job_notice_scheduled_failure_targets_owner(self):
        # Review Focus 2: scheduler job, no task, no chat → owner DM (target None).
        n = _job(status="failed", kind="atlas-daily-brief", resolved_skill="atlas-daily-brief",
                 origin_channel="scheduler", origin_ref="atlas-daily-brief", origin_thread=None,
                 created_by="scheduler", error_message="API terminal error: 529",
                 terminal_reason="api_error", summary=None)
        assert n is not None and n.notice_kind == "job_failed" and n.severity == "warn"
        assert n.target is None and n.thread is None
        assert "atlas-daily-brief" in n.body and "api_error" in n.body and "529" in n.body
        assert n.actions["buttons"] == [[["Details", f"jd:{str(JOB)[:8]}"]]]

    def test_web_launch_targets_owner(self):
        # Review Focus 3: a dashboard launch gets its completion DM at the owner chat.
        n = _job(origin_channel="web", origin_ref=None, origin_thread=None, created_by="web")
        assert n is not None and n.notice_kind == "job_completed"
        assert n.target is None and n.thread is None

    def test_scheduler_origin_without_ref_says_via_scheduler(self):
        # enqueue_job(created_by="scheduler") derives ("scheduler", None): the
        # card must read "via scheduler", never "via None".
        n = _job(status="failed", origin_channel="scheduler", origin_ref=None, origin_thread=None,
                 created_by="scheduler", error_message="boom", terminal_reason="error", summary=None)
        assert n is not None and "via scheduler" in n.body and "None" not in n.body

    def test_returns_none_when_not_notifying(self):
        assert _job(kind="_learning_apply", resolved_skill="_learning_apply") is None
        assert _job(origin_channel="scheduler", origin_ref="atlas-report", created_by="scheduler") is None

    def test_body_is_unbounded_here(self):
        # Limits belong to the renderer (telegram.py), not the builder.
        n = _job(summary="x" * 10_000)
        assert len(n.body) > 4096

    def test_build_job_notice_renders_the_lane_label(self):
        from src.gateway.telegram_bot import _lane_label
        n = _job(status="failed", resolved_provider="codex", resolved_model="gpt-6-luna",
                 terminal_reason="auth_expired", error_message="login expired", summary=None)
        expected = _lane_label("codex", "gpt-6-luna", "auth_expired")
        assert expected == "codex/gpt-6-luna · auth_expired" and expected in n.body
        assert "login expired" in n.body
        done = _job()
        assert _lane_label("anthropic", "claude-sonnet-4-6", "ok") in done.body
        assert "*" not in done.body.split("\n")[0] and "`" not in done.body   # plain text header

    def test_failure_without_a_lane_still_names_the_reason(self):
        # A queued/pre-dispatch failure (no provider, no model) must still say why.
        n = _job(status="failed", resolved_provider=None, resolved_model=None, model_served=None,
                 terminal_reason="timeout", error_message="hung", summary=None)
        assert "timeout" in n.body and "via telegram" in n.body
        n2 = _job(status="failed", resolved_provider=None, resolved_model=None, model_served=None,
                  terminal_reason=None, error_message="hung", summary=None)
        assert "error" in n2.body.split("\n")[0]

    def test_model_served_is_the_fallback_lane(self):
        n = _job(resolved_provider=None, resolved_model=None, model_served="claude-opus-4-8")
        assert "claude-opus-4-8" in n.body.split("\n")[0]

    def test_target_only_for_telegram_origins(self):
        # A Telegram chat id is the only target a Phase-1 producer can address.
        n = _job(origin_channel="cli", origin_ref="shell", origin_thread=None, created_by="cli")
        assert n is not None and n.target is None and n.thread is None


class TestBuildTaskNotice:
    TASK = uuid.uuid4()

    def test_approval_request_buttons_match_legacy_callbacks(self):
        n = build_task_notice(task_id=self.TASK, notify_type="approval_request",
                              text="done", target="123", thread="777")
        p = str(self.TASK)[:8]
        assert n.notice_kind == "task_approval_request"
        assert n.actions["buttons"] == [[["Approve", f"approve:{p}"],
                                         ["Send Feedback", f"feedback:{p}"],
                                         ["View Details", f"details:{p}"]]]
        assert "rate:" not in str(n.actions)     # spec §4.1: /rate leaves the cards
        assert n.target == "123" and n.thread == "777"
        assert n.subject_type == "task" and n.subject_id == str(self.TASK)

    def test_choices_become_one_button_per_row_capped_at_8(self):
        n = build_task_notice(task_id=self.TASK, notify_type="choices", text="",
                              question="Pick", choices=[f"opt{i}" for i in range(12)])
        assert len(n.actions["buttons"]) == 8
        assert n.actions["buttons"][0] == [["opt0", f"choice:{str(self.TASK)[:8]}:0"]]
        assert n.body == "Pick"

    @pytest.mark.parametrize("t,expected", [("failed", "warn"), ("review_flagged", "warn"),
                                            ("progress", "info"), ("completed", "info")])
    def test_severity(self, t, expected):
        assert build_task_notice(task_id=self.TASK, notify_type=t, text="x").severity == expected

    def test_plan_cards_carry_the_legacy_callbacks(self):
        p = str(self.TASK)[:8]
        plan = build_task_notice(task_id=self.TASK, notify_type="plan", text="steps")
        assert plan.actions["buttons"] == [[["Cancel plan", f"cancel:{p}"]]]
        gate = build_task_notice(task_id=self.TASK, notify_type="plan_approval", text="steps")
        assert gate.actions["buttons"] == [[["Approve plan", f"approve_plan:{p}"], ["Cancel", f"cancel:{p}"]]]
        done = build_task_notice(task_id=self.TASK, notify_type="completed", text="evidence")
        assert done.actions["buttons"] == [[["Reopen", f"reopen:{p}"], ["View Details", f"details:{p}"]]]
        assert "rate:" not in str(done.actions)

    def test_no_rating_row_on_any_card(self):
        for t in TASK_NOTIFY_TYPES:
            n = build_task_notice(task_id=self.TASK, notify_type=t, text="x", choices=["a"])
            assert "rate:" not in str(n.actions), t

    def test_unknown_type_rejected(self):
        with pytest.raises(ValueError):
            build_task_notice(task_id=self.TASK, notify_type="bogus", text="x")


class TestOpsNotice:
    def test_ops_notice_shape(self):
        n = build_ops_notice(kind="credential_canary", severity="critical", text="FAILED",
                             subject="job:abc")
        assert n.notice_kind == "credential_canary" and n.subject_type == "job"
        assert n.subject_id == "abc" and n.target is None

    def test_unknown_kind_rejected(self):
        with pytest.raises(ValueError):
            build_ops_notice(kind="nope", severity="info", text="x")

    def test_unknown_severity_rejected(self):
        with pytest.raises(ValueError):
            build_ops_notice(kind="ops_alert", severity="loud", text="x")

    def test_job_and_task_kinds_are_not_ops_notices(self):
        with pytest.raises(ValueError):
            build_ops_notice(kind="job_failed", severity="warn", text="x")


class TestRetry:
    def test_retry_delay_backoff(self):
        assert [retry_delay_seconds(a) for a in (1, 2, 3, 4, 5, 9)] == [30, 60, 120, 240, 480, 600]

    def test_mark_failed_keeps_pending_until_max_attempts(self):
        status, attempts, nxt = transition_after_failure(0, NOW)
        assert (status, attempts) == ("pending", 1) and nxt == NOW + timedelta(seconds=30)
        status, attempts, nxt = transition_after_failure(MAX_ATTEMPTS - 1, NOW)
        assert (status, attempts) == ("failed", MAX_ATTEMPTS)


# ── Async wrappers against a recording session ───────────────────────────────


class _RecordingSession:
    """`async_session()` stand-in that records what was added and executed and
    never touches a database. `rowcount` is settable per test."""

    def __init__(self, rowcount: int = 1, fail_add: bool = False):
        self.added: list = []
        self.executed: list = []
        self.rowcount = rowcount
        self.fail_add = fail_add

    def __call__(self):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def add(self, obj):
        if self.fail_add:
            raise RuntimeError("db down")
        self.added.append(obj)

    async def execute(self, stmt):
        self.executed.append(stmt)
        return SimpleNamespace(rowcount=self.rowcount, scalars=lambda: iter(()))

    async def commit(self):
        pass


def _params(stmt) -> dict:
    return dict(stmt.compile(dialect=postgresql.dialect()).params)


def _sql(stmt) -> str:
    return str(stmt.compile(dialect=postgresql.dialect()))


class TestAsyncWrappers:
    @pytest.fixture(autouse=True)
    def _fakes(self, monkeypatch):
        self.db = _RecordingSession()
        self.redis = SimpleNamespace(publish=AsyncMock())
        self.audit: list[tuple] = []
        monkeypatch.setattr(outbox, "async_session", self.db)
        monkeypatch.setattr(outbox, "redis", self.redis)
        monkeypatch.setattr(outbox.audit_log, "append",
                            lambda job_id, kind, **f: self.audit.append((str(job_id), kind, f)))

    async def test_enqueue_notice_ignores_the_switch(self, monkeypatch):
        # D-P1-10: producers always write the row; the switch is the bot's.
        from src.config import settings
        monkeypatch.setattr(settings, "notify_outbox", False)
        n = _job()
        row_id = await enqueue_notice(n)
        assert isinstance(row_id, uuid.UUID)
        assert len(self.db.added) == 1
        row = self.db.added[0]
        assert row.status == "pending" and row.attempts == 0 and row.id == row_id
        assert row.notice_kind == "job_completed" and row.target == "123"
        self.redis.publish.assert_awaited_once_with("notify:outbox", str(row_id))
        assert self.audit == [(str(JOB), "notice_queued",
                               {"notice_id": str(row_id), "notice_kind": "job_completed"})]

    def test_outbox_never_reads_the_switch(self):
        assert "notify_outbox" not in OUTBOX_SRC.read_text()

    async def test_enqueue_notice_returns_none_when_the_insert_fails(self, monkeypatch):
        monkeypatch.setattr(outbox, "async_session", _RecordingSession(fail_add=True))
        assert await enqueue_notice(_job()) is None
        self.redis.publish.assert_not_awaited()

    async def test_enqueue_notice_survives_a_failed_nudge(self):
        self.redis.publish = AsyncMock(side_effect=ConnectionError("redis down"))
        assert isinstance(await enqueue_notice(_job()), uuid.UUID)   # the 30 s poll delivers

    async def test_record_notice_sent_audits_sent_and_stamps_attempts(self):
        n = build_ops_notice(kind="ops_alert", severity="warn", text="x", subject=f"job:{JOB}")
        row_id = await record_notice(n, status="sent", external_ref="42")
        row = self.db.added[0]
        assert row.status == "sent" and row.attempts == 1 and row.external_ref == "42"
        assert row.sent_at is not None
        assert self.audit == [(str(JOB), "notice_sent", {"notice_id": str(row_id), "external_ref": "42"})]

    async def test_record_notice_failed_audits_failed(self):
        n = build_ops_notice(kind="ops_alert", severity="warn", text="x", subject=f"job:{JOB}")
        row_id = await record_notice(n, status="failed", last_error="telegram 400: chat not found")
        assert self.db.added[0].attempts == 1 and self.db.added[0].sent_at is None
        assert self.audit[0][:2] == (str(JOB), "notice_failed")
        assert self.audit[0][2]["notice_id"] == str(row_id)

    async def test_record_notice_without_a_job_subject_writes_no_audit(self):
        await record_notice(build_ops_notice(kind="ops_alert", severity="info", text="x"), status="pending")
        assert self.audit == []

    async def test_record_notice_rejects_bad_kind_or_status(self):
        with pytest.raises(ValueError):
            await record_notice(Notice(notice_kind="bogus", body="x"), status="pending")
        with pytest.raises(ValueError):
            await record_notice(build_ops_notice(kind="ops_alert", severity="info", text="x"), status="done")

    async def test_claim_notice_is_a_conditional_update_that_bumps_attempts(self):
        nid = uuid.uuid4()
        assert await claim_notice(nid, now=NOW) is True
        sql, params = _sql(self.db.executed[0]), _params(self.db.executed[0])
        assert "UPDATE notifications" in sql and "status = " in sql
        assert params["status"] == "sending"
        assert "attempts + " in sql
        assert params["next_attempt_at"] == NOW + timedelta(seconds=SENDING_LEASE_SECONDS)
        assert params["status_1"] == "pending" and params["id_1"] == nid

    async def test_claim_notice_false_when_another_drainer_has_it(self, monkeypatch):
        monkeypatch.setattr(outbox, "async_session", _RecordingSession(rowcount=0))
        assert await claim_notice(uuid.uuid4()) is False

    async def test_release_stuck_sending_returns_pending_rows_past_the_lease(self, monkeypatch):
        monkeypatch.setattr(outbox, "async_session", _RecordingSession(rowcount=2))
        assert await release_stuck_sending(now=NOW) == 2

    async def test_mark_sent_clips_the_ref_and_audits(self):
        nid = uuid.uuid4()
        await mark_sent(nid, "9" * 80, subject_type="job", subject_id=str(JOB))
        params = _params(self.db.executed[0])
        assert params["status"] == "sent" and params["external_ref"] == "9" * 64
        assert params["last_error"] is None and params["next_attempt_at"] is None
        assert "attempts" not in params           # claim_notice already counted this try
        assert self.audit[0][:2] == (str(JOB), "notice_sent")

    async def test_mark_failed_follows_the_retry_math(self):
        nid = uuid.uuid4()
        assert await mark_failed(nid, "telegram 400: x", attempts_so_far=0,
                                 subject_type="job", subject_id=str(JOB)) == "pending"
        assert _params(self.db.executed[0])["attempts"] == 1
        assert self.audit == []                   # not terminal yet → no notice_failed
        assert await mark_failed(nid, "telegram 400: x", attempts_so_far=MAX_ATTEMPTS - 1,
                                 subject_type="job", subject_id=str(JOB)) == "failed"
        assert self.audit[0][:2] == (str(JOB), "notice_failed")

    async def test_mark_failed_clips_the_error(self):
        await mark_failed(uuid.uuid4(), "e" * 900, attempts_so_far=0)
        assert len(_params(self.db.executed[0])["last_error"]) == 500

    async def test_mark_skipped_is_terminal_and_keeps_the_reason(self):
        await mark_skipped(uuid.uuid4(), "legacy_mode")
        params = _params(self.db.executed[0])
        assert params["status"] == "skipped" and params["last_error"] == "legacy_mode"
        assert params["next_attempt_at"] is None
