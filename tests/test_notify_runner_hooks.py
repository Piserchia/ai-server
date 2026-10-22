"""
Runner → outbox wiring (Observability Phase 1, A5; design of record P0 plan
Task 6 minus its session.py half and minus its switch gating).

DB and Redis are monkeypatched; the policy itself lives in
src/notify/outbox.py (tests/test_notify_outbox.py). D-P1-10: the runner
DUAL-WRITES — the legacy `tasks:notify` / `jobs:done:<id>` publishes are
unconditional and byte-identical, AND the outbox row is always written; the
kill switch is read by the bot only.

Run: PIPENV_DONT_LOAD_ENV=1 SERVER_ROOT="$PWD" pipenv run pytest tests/test_notify_runner_hooks.py -q -p no:cacheprovider
"""

from __future__ import annotations

import ast
import inspect
import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.models import JobStatus
from src.notify.outbox import Notice
from src.runner import main as main_mod

REPO = Path(__file__).resolve().parent.parent
MAIN_SRC = REPO / "src" / "runner" / "main.py"

TASK = uuid.uuid4()
NOW = datetime(2026, 10, 21, 3, 0, tzinfo=timezone.utc)


def _job(**over):
    base = dict(id=uuid.uuid4(), kind="atlas-daily-brief", resolved_skill="atlas-daily-brief",
                result=None, error_message="API terminal error: 529", terminal_reason="api_error",
                origin_channel="scheduler", origin_ref="atlas-daily-brief", origin_thread=None,
                created_by="scheduler", task_id=None, parent_job_id=None,
                model_served="claude-opus-5", resolved_provider="anthropic",
                resolved_model="claude-opus-5", num_turns=3,
                started_at=NOW, completed_at=NOW + timedelta(seconds=123))
    base.update(over)
    return SimpleNamespace(**base)


class _GetSession:
    """`async_session()` stand-in whose `get` answers from a dict of rows."""

    def __init__(self, rows: dict | None = None, *, fail: bool = False):
        self.rows = rows or {}
        self.fail = fail
        self.gets: list = []

    def __call__(self):
        return self

    async def __aenter__(self):
        if self.fail:
            raise RuntimeError("db down")
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, model, key):
        self.gets.append((model.__name__, key))
        return self.rows.get(key)


class _FinishSession:
    """`session_scope()` stand-in for _finish_job: the UPDATE's rowcount is
    what the test says (0 = INV-9 suppressed the stamp)."""

    def __init__(self, rowcount: int = 1):
        self.rowcount = rowcount
        self.executed: list = []

    def __call__(self):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def execute(self, stmt):
        self.executed.append(stmt)
        return SimpleNamespace(rowcount=self.rowcount)


# ── Pure helpers ────────────────────────────────────────────────────────────


class TestEligibilityInheritance:
    def test_child_inherits_the_parent_channel(self):
        # spec §4.2: dispatch-MCP / escalation / self-diagnose / evaluator /
        # writeback children inherit the parent's eligibility.
        f = main_mod.effective_origin_channel
        assert f("system", "telegram") == "telegram"      # Telegram launch → child reports
        assert f("system", "scheduler") == "scheduler"    # schedule row → child stays quiet
        assert f(None, "telegram") == "telegram"
        assert f("telegram", "scheduler") == "telegram"   # an own human channel always wins
        assert f("web", "telegram") == "web"
        assert f("system", None) == "system"              # no parent: unchanged
        assert f(None, None) is None

    def test_pure(self):
        src = inspect.getsource(main_mod.effective_origin_channel)
        assert "await" not in src and "async_session" not in src


class TestJobNoticeKwargs:
    def test_scheduled_failure_kwargs(self):
        kw = main_mod.job_notice_kwargs(_job())
        assert kw["origin_channel"] == "scheduler" and kw["task_id"] is None
        assert kw["origin_ref"] == "atlas-daily-brief" and kw["origin_thread"] is None
        assert kw["created_by"] == "scheduler"
        assert kw["summary"] is None and kw["duration_seconds"] == 123
        assert kw["error_message"].startswith("API terminal")
        assert kw["terminal_reason"] == "api_error"
        assert kw["status"] is None     # the caller sets it

    def test_summary_pulled_from_result(self):
        kw = main_mod.job_notice_kwargs(_job(result={"summary": "pong", "usage": {}}))
        assert kw["summary"] == "pong"

    def test_non_dict_result_gives_no_summary(self):
        assert main_mod.job_notice_kwargs(_job(result="not a dict"))["summary"] is None

    def test_missing_timestamps_give_no_duration(self):
        assert main_mod.job_notice_kwargs(_job(completed_at=None))["duration_seconds"] is None
        assert main_mod.job_notice_kwargs(_job(started_at=None))["duration_seconds"] is None

    def test_passes_provider_and_model(self):
        # The lane label in the card comes from the 007 columns + num_turns
        # (008; NULL until B3) — read straight off the row.
        kw = main_mod.job_notice_kwargs(_job(resolved_provider="openai", resolved_model="gpt-5",
                                             model_served="gpt-5-codex", num_turns=None))
        assert kw["resolved_provider"] == "openai"
        assert kw["resolved_model"] == "gpt-5"
        assert kw["model_served"] == "gpt-5-codex"
        assert kw["num_turns"] is None

    def test_kwargs_fit_build_job_notice(self):
        from src.notify.outbox import build_job_notice
        params = inspect.signature(build_job_notice).parameters
        kw = main_mod.job_notice_kwargs(_job())
        assert set(kw) <= set(params), set(kw) - set(params)
        kw["status"] = "failed"
        notice = build_job_notice(**kw)
        assert notice is not None and notice.notice_kind == "job_failed"
        assert "anthropic/claude-opus-5 · api_error" in notice.body
        assert "· 3 turns" in notice.body


# ── _enqueue_job_notice ─────────────────────────────────────────────────────


class TestEnqueueJobNotice:
    @pytest.fixture
    def recorded(self, monkeypatch):
        calls: list[Notice] = []

        async def fake_enqueue(notice):
            calls.append(notice)
            return uuid.uuid4()

        monkeypatch.setattr(main_mod, "enqueue_notice", fake_enqueue)
        return calls

    async def test_completed_web_job_enqueues_notice(self, monkeypatch, recorded):
        # Review Focus 3: a web launch has no `_job_to_chat` entry today and
        # never got a completion DM. created_by="web" → origin "web" → DoneCard.
        job = _job(origin_channel="web", origin_ref=None, created_by="web",
                   error_message=None, terminal_reason="ok",
                   result={"summary": "deployed"})
        monkeypatch.setattr(main_mod, "async_session", _GetSession({job.id: job}))
        await main_mod._enqueue_job_notice(job.id, "completed")
        assert len(recorded) == 1
        n = recorded[0]
        assert n.notice_kind == "job_completed" and n.subject_id == str(job.id)
        assert n.target is None            # owner chat
        assert "deployed" in n.body

    async def test_scheduled_failure_without_task_enqueues_notice(self, monkeypatch, recorded):
        job = _job()
        monkeypatch.setattr(main_mod, "async_session", _GetSession({job.id: job}))
        await main_mod._enqueue_job_notice(job.id, "failed")
        assert [n.notice_kind for n in recorded] == ["job_failed"]
        assert "via atlas-daily-brief" in recorded[0].body

    async def test_scheduled_completion_writes_no_row(self, monkeypatch, recorded):
        job = _job(error_message=None, terminal_reason="ok", result={"summary": "x"})
        monkeypatch.setattr(main_mod, "async_session", _GetSession({job.id: job}))
        await main_mod._enqueue_job_notice(job.id, "completed")
        assert recorded == []

    async def test_missing_row_writes_nothing(self, monkeypatch, recorded):
        monkeypatch.setattr(main_mod, "async_session", _GetSession({}))
        await main_mod._enqueue_job_notice(uuid.uuid4(), "failed")
        assert recorded == []

    async def test_child_inherits_parent_channel_and_target(self, monkeypatch, recorded):
        # A dispatch-MCP child of a Telegram launch: its own origin is
        # ("system", "dispatch-mcp"); the parent's chat is where the card goes.
        parent = _job(origin_channel="telegram", origin_ref="123", origin_thread="777",
                      created_by="telegram:123")
        child = _job(origin_channel="system", origin_ref="dispatch-mcp", origin_thread=None,
                     created_by="dispatch-mcp", parent_job_id=parent.id,
                     error_message=None, terminal_reason="ok", result={"summary": "child done"})
        db = _GetSession({parent.id: parent, child.id: child})
        monkeypatch.setattr(main_mod, "async_session", db)
        await main_mod._enqueue_job_notice(child.id, "completed")
        assert len(recorded) == 1
        n = recorded[0]
        assert n.notice_kind == "job_completed"
        assert n.target == "123" and n.thread == "777"
        assert n.subject_id == str(child.id)
        # exactly one extra read, only for a child
        assert [m for m, _ in db.gets] == ["Job", "Job"]

    async def test_child_of_a_schedule_stays_quiet_on_completion(self, monkeypatch, recorded):
        parent = _job()
        child = _job(origin_channel="system", origin_ref="dispatch-mcp", created_by="dispatch-mcp",
                     parent_job_id=parent.id, error_message=None, terminal_reason="ok",
                     result={"summary": "x"})
        monkeypatch.setattr(main_mod, "async_session", _GetSession({parent.id: parent, child.id: child}))
        await main_mod._enqueue_job_notice(child.id, "completed")
        assert recorded == []

    async def test_orphan_child_keeps_its_own_origin(self, monkeypatch, recorded):
        # parent_job_id set but the parent row is gone: no inheritance, the
        # own "system" origin decides (failure still DMs the owner).
        child = _job(origin_channel="system", origin_ref="dispatch-mcp", created_by="dispatch-mcp",
                     parent_job_id=uuid.uuid4())
        db = _GetSession({child.id: child})
        monkeypatch.setattr(main_mod, "async_session", db)
        await main_mod._enqueue_job_notice(child.id, "failed")
        assert len(recorded) == 1 and recorded[0].target is None
        # the builder's source rule: schedule name, else channel, else created_by
        assert "via system" in recorded[0].body
        assert [m for m, _ in db.gets] == ["Job", "Job"]

    def test_signature_takes_the_row_not_the_payload(self):
        # Delta: the review-blocked path overrides the done payload; the
        # notice is built from the ROW, so the helper has no payload input.
        params = list(inspect.signature(main_mod._enqueue_job_notice).parameters)
        assert params == ["job_id", "status"]


# ── _task_target ────────────────────────────────────────────────────────────


class TestTaskTarget:
    async def test_prefers_origin_columns(self, monkeypatch):
        task = SimpleNamespace(origin_ref="123", origin_thread="777",
                               chat_id=999, thread_message_id=888)
        monkeypatch.setattr(main_mod, "async_session", _GetSession({TASK: task}))
        assert await main_mod._task_target(TASK) == ("123", "777")

    async def test_falls_back_to_legacy_columns(self, monkeypatch):
        task = SimpleNamespace(origin_ref=None, origin_thread=None,
                               chat_id=999, thread_message_id=888)
        monkeypatch.setattr(main_mod, "async_session", _GetSession({TASK: task}))
        assert await main_mod._task_target(TASK) == ("999", "888")

    async def test_mixed_columns(self, monkeypatch):
        task = SimpleNamespace(origin_ref="123", origin_thread=None,
                               chat_id=999, thread_message_id=None)
        monkeypatch.setattr(main_mod, "async_session", _GetSession({TASK: task}))
        assert await main_mod._task_target(TASK) == ("123", None)

    async def test_missing_task_is_owner_chat(self, monkeypatch):
        monkeypatch.setattr(main_mod, "async_session", _GetSession({}))
        assert await main_mod._task_target(TASK) == (None, None)


# ── _notify_task: the dual-write chokepoint ─────────────────────────────────


async def _first_message(pubsub, tries: int = 20):
    for _ in range(tries):
        msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=0.1)
        if msg:
            return msg
    return None


class TestNotifyTask:
    # Every test patches main_mod.redis: the legacy publish is unconditional
    # (dual-write), so no path skips Redis.

    @pytest.fixture
    def wired(self, monkeypatch, fake_redis):
        monkeypatch.setattr(main_mod, "redis", fake_redis)
        calls: list[Notice] = []

        async def fake_target(task_id):
            return ("123", "777")

        async def fake_enqueue(notice):
            calls.append(notice)
            return uuid.uuid4()

        monkeypatch.setattr(main_mod, "_task_target", fake_target)
        monkeypatch.setattr(main_mod, "enqueue_notice", fake_enqueue)
        return calls

    @pytest.mark.parametrize("switch", [False, True])
    async def test_outbox_row_written_in_both_modes(self, monkeypatch, wired, switch):
        # D-P1-10: the runner never reads the switch — the row is always written.
        monkeypatch.setattr(main_mod.settings, "notify_outbox", switch)
        await main_mod._notify_task(TASK, "question", text="which one?")
        assert len(wired) == 1, f"outbox row missing with notify_outbox={switch}"
        n = wired[0]
        assert n.notice_kind == "task_question" and n.target == "123" and n.thread == "777"
        assert n.body == "which one?" and n.subject_id == str(TASK)

    async def test_choices_card_carries_question_and_options(self, wired):
        await main_mod._notify_task(TASK, "choices", question="Pick:", choices=["a", "b"])
        n = wired[0]
        assert n.notice_kind == "task_choices" and n.body == "Pick:"
        assert n.actions["choices"] == ["a", "b"]

    async def test_choices_without_options_writes_no_row(self, wired, fake_redis):
        # parity with the legacy `_task_notifier` (`elif notify_type ==
        # "choices" and choices`): no "Pick one:" card with zero buttons. The
        # legacy publish still goes out byte-identically.
        pubsub = fake_redis.pubsub()
        await pubsub.subscribe("tasks:notify")
        await main_mod._notify_task(TASK, "choices", question="Pick:", choices=[])
        assert wired == []
        msg = await _first_message(pubsub)
        assert msg is not None and json.loads(msg["data"])["choices"] == []

    async def test_outbox_insert_failure_never_raises(self, monkeypatch, fake_redis):
        monkeypatch.setattr(main_mod, "redis", fake_redis)

        async def boom(task_id):
            raise RuntimeError("db down")

        monkeypatch.setattr(main_mod, "_task_target", boom)
        pubsub = fake_redis.pubsub()
        await pubsub.subscribe("tasks:notify")
        await main_mod._notify_task(TASK, "progress", text="x")   # must not raise
        # …and the legacy publish still went out first.
        assert await _first_message(pubsub) is not None

    async def test_enqueue_failure_never_raises(self, monkeypatch, fake_redis):
        monkeypatch.setattr(main_mod, "redis", fake_redis)

        async def fake_target(task_id):
            return (None, None)

        async def boom(notice):
            raise RuntimeError("insert exploded")

        monkeypatch.setattr(main_mod, "_task_target", fake_target)
        monkeypatch.setattr(main_mod, "enqueue_notice", boom)
        await main_mod._notify_task(TASK, "failed", text="x")

    @pytest.mark.parametrize("switch", [False, True])
    async def test_legacy_channel_published_byte_identically(self, monkeypatch, fake_redis,
                                                             wired, switch):
        # The wire format never depends on the switch; only the bot's
        # renderer choice does (A6). Bytes = exactly what pre-A5 published.
        monkeypatch.setattr(main_mod.settings, "notify_outbox", switch)
        pubsub = fake_redis.pubsub()
        await pubsub.subscribe("tasks:notify")
        fields = {"question": "Pick one:", "choices": ["a", "b"]}
        await main_mod._notify_task(TASK, "choices", **fields)
        msg = await _first_message(pubsub)
        assert msg is not None, f"legacy publish missing with notify_outbox={switch}"
        legacy = json.dumps({"task_id": str(TASK), "type": "choices", **fields})
        assert msg["data"] == legacy

    async def test_legacy_publish_precedes_the_row(self, monkeypatch, fake_redis):
        order: list[str] = []

        class _R:
            async def publish(self, channel, data):
                order.append("publish")

        async def fake_target(task_id):
            order.append("target")
            return (None, None)

        async def fake_enqueue(notice):
            order.append("enqueue")

        monkeypatch.setattr(main_mod, "redis", _R())
        monkeypatch.setattr(main_mod, "_task_target", fake_target)
        monkeypatch.setattr(main_mod, "enqueue_notice", fake_enqueue)
        await main_mod._notify_task(TASK, "progress", text="x")
        assert order == ["publish", "target", "enqueue"]


# ── _finish_job → job notice ────────────────────────────────────────────────


class TestFinishJobNotice:
    @pytest.fixture
    def wired(self, monkeypatch):
        h = SimpleNamespace(done=[], notices=[], order=[])

        async def fake_done(job_id, status, payload=None):
            h.done.append((job_id, status, payload))
            h.order.append("done")

        async def fake_notice(job_id, status):
            h.notices.append((job_id, status))
            h.order.append("notice")

        monkeypatch.setattr(main_mod.session_mod, "publish_done", fake_done)
        monkeypatch.setattr(main_mod, "_enqueue_job_notice", fake_notice)

        def build(rowcount: int = 1):
            monkeypatch.setattr(main_mod, "session_scope", _FinishSession(rowcount))
            return h

        return build

    async def test_finish_job_failed_enqueues_notice_without_task(self, wired):
        # Review Focus 2: a failing scheduler job (no task_id) must reach the outbox.
        h = wired()
        jid = uuid.uuid4()
        await main_mod._finish_job(jid, JobStatus.failed, error="boom", terminal_reason="api_error")
        assert h.notices == [(jid, "failed")]
        assert h.order == ["done", "notice"]      # after publish_done

    async def test_completed_enqueues_notice(self, wired):
        h = wired()
        jid = uuid.uuid4()
        await main_mod._finish_job(jid, JobStatus.completed, result={"summary": "ok"})
        assert h.notices == [(jid, "completed")]

    async def test_finish_job_cancelled_writes_no_notice(self, wired):
        h = wired()
        await main_mod._finish_job(uuid.uuid4(), JobStatus.cancelled)
        assert h.notices == []
        assert len(h.done) == 1               # the legacy publish is untouched

    async def test_suppressed_finish_writes_no_row(self, wired):
        # INV-9: the UPDATE matched nothing (job already cancelled) → no
        # jobs:done publish and no outbox row.
        h = wired(rowcount=0)
        await main_mod._finish_job(uuid.uuid4(), JobStatus.completed, result={"summary": "x"})
        assert h.done == [] and h.notices == []

    async def test_review_blocked_payload_does_not_feed_the_notice(self, wired):
        # Delta: done_payload overrides the published payload only; the
        # notice helper gets (job_id, status) and reads the row.
        h = wired()
        jid = uuid.uuid4()
        await main_mod._finish_job(jid, JobStatus.failed, error="Review blocked: x",
                                   terminal_reason="review_blocked", review_outcome="blocked",
                                   done_payload={"summary": "card"})
        assert h.done[0][2] == {"summary": "card"}
        assert h.notices == [(jid, "failed")]

    async def test_notice_failure_is_non_fatal(self, monkeypatch, wired):
        h = wired()

        async def boom(job_id, status):
            raise RuntimeError("outbox down")

        monkeypatch.setattr(main_mod, "_enqueue_job_notice", boom)
        await main_mod._finish_job(uuid.uuid4(), JobStatus.failed, error="e", terminal_reason="error")
        assert len(h.done) == 1


# ── Source pins ─────────────────────────────────────────────────────────────


def test_only_one_tasks_notify_literal_remains():
    # The five direct publishes (escalation L3, choices, question, sentinel
    # approval, auto-continue progress) are routed through _notify_task.
    assert MAIN_SRC.read_text().count('"tasks:notify"') == 1


def _func(name: str) -> ast.AsyncFunctionDef:
    tree = ast.parse(MAIN_SRC.read_text())
    return next(n for n in ast.walk(tree)
                if isinstance(n, ast.AsyncFunctionDef) and n.name == name)


def _notify_calls(node: ast.AST) -> list[ast.Call]:
    return [n for n in ast.walk(node)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
            and n.func.id == "_notify_task"]


def test_the_literal_lives_in_the_chokepoint():
    # ast.unparse renders the literal single-quoted; the count test above
    # pins the source spelling.
    assert "tasks:notify" in ast.unparse(_func("_notify_task"))


def test_escalation_l3_routes_through_the_chokepoint():
    node = _func("_maybe_escalate")
    src = ast.unparse(node)
    assert "import redis as _redis" not in src and "_redis" not in src
    types = [ast.unparse(c.args[1]) for c in _notify_calls(node)]
    assert "'failed'" in types


def test_update_task_after_job_routes_all_four_cards():
    node = _func("_update_task_after_job")
    types = {ast.unparse(c.args[1]) for c in _notify_calls(node)}
    assert {"'choices'", "'question'", "'approval_request'", "'progress'"} <= types
    assert "redis.publish" not in ast.unparse(node)


def test_switch_is_not_read_by_the_runner():
    # D-P1-10: `settings.notify_outbox` is the bot's. Nothing under
    # src/runner/ or in the outbox module reads it.
    offenders = []
    for path in [*sorted((REPO / "src" / "runner").rglob("*.py")),
                 REPO / "src" / "notify" / "outbox.py"]:
        if "notify_outbox" in path.read_text():
            offenders.append(str(path.relative_to(REPO)))
    assert offenders == []


def test_finish_job_enqueues_after_publish_done():
    body = ast.unparse(_func("_finish_job"))
    assert body.index("publish_done") < body.index("_enqueue_job_notice")
