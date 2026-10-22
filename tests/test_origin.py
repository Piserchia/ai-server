"""
Persisted job/task origin — Observability Phase 1 (re-cut plan A1/A2).

A1 lands the two pure helpers in `src/gateway/jobs.py`:
`ORIGIN_CHANNELS` and `origin_from_created_by(created_by)`. Nothing calls
them in A1; A2 wires them into `enqueue_job`. The mapping here is the one
migration 008's `_BACKFILL_ORIGIN` CASE implements in SQL, so backfilled
and new rows agree (tests/test_migrations.py pins the SQL side textually).

The `created_by` vocabulary below is every producer in the current tree
(grep `created_by=` under src/ and scripts/): the three channels with a
literal spelling (`telegram:<chat>`, `web`, `scheduler`) and the long tail
of internal producers that all map to `system` with the raw value as ref.
"""

from __future__ import annotations

import pytest

from src.gateway.jobs import ORIGIN_CHANNELS, origin_from_created_by


class TestOriginFromCreatedBy:
    @pytest.mark.parametrize("created_by,expected", [
        # The three literal channels.
        ("telegram:123456789", ("telegram", "123456789")),
        ("telegram:", ("telegram", None)),              # bare prefix → NULL ref (NULLIF arm)
        ("telegram:  42  ", ("telegram", "42")),       # whitespace never lands in a ref
        ("web", ("web", None)),
        ("scheduler", ("scheduler", None)),
        # Everything else is `system` with the raw created_by as the ref.
        ("dispatch-mcp", ("system", "dispatch-mcp")),
        ("event-trigger", ("system", "event-trigger")),
        ("event-trigger:deploy", ("system", "event-trigger:deploy")),
        ("learning:abcd1234", ("system", "learning:abcd1234")),
        ("writeback:abcd1234", ("system", "writeback:abcd1234")),
        ("escalation", ("system", "escalation")),
        ("escalation:abcd1234", ("system", "escalation:abcd1234")),
        ("plan:abcd1234", ("system", "plan:abcd1234")),
        ("evaluator:abcd1234", ("system", "evaluator:abcd1234")),
        ("eval-fix:abcd1234", ("system", "eval-fix:abcd1234")),
        ("auto-continue:abcd1234", ("system", "auto-continue:abcd1234")),
        ("bot-error-handler", ("system", "bot-error-handler")),
        ("deploy-autopilot", ("system", "deploy-autopilot")),
        ("owner-dm", ("system", "owner-dm")),
        ("unknown", ("system", "unknown")),
        # Degenerate inputs never produce an empty-string ref.
        ("", ("system", None)),
        ("   ", ("system", None)),
        (None, ("system", None)),
    ])
    def test_mapping(self, created_by, expected):
        assert origin_from_created_by(created_by) == expected

    def test_ref_fits_column(self):
        # jobs.origin_ref is String(64); a long created_by is clipped, never
        # rejected (the column itself is also String(64)).
        channel, ref = origin_from_created_by("owner-" + "x" * 200)
        assert channel == "system" and len(ref) <= 64

    def test_telegram_ref_fits_column(self):
        channel, ref = origin_from_created_by("telegram:" + "9" * 200)
        assert channel == "telegram" and len(ref) == 64

    def test_every_channel_is_declared(self):
        seen = {origin_from_created_by(cb)[0] for cb in
                ("telegram:1", "web", "scheduler", "dispatch-mcp", "")}
        assert seen <= set(ORIGIN_CHANNELS)
        assert ORIGIN_CHANNELS == ("telegram", "web", "cli", "scheduler", "system")
        assert all(len(c) <= 16 for c in ORIGIN_CHANNELS)   # origin_channel is String(16)


# ── A2: the helpers wired, awaiting_since, queue_wait_ms, typed failure stamps ──
#
# Re-cut plan A2 (design of record: P0 plan Task 4 + the 3b half of Task 3).
# Pure / fixture style: `enqueue_job` is driven against a recording session
# stand-in and a fake redis; `_set_task_status` against a recording
# `session_scope`; the runner's failure sites are pinned at the AST level
# (the tests/test_timeout_escalation.py style) and the cancelled guard is
# ALSO exercised behaviourally through `_process_job` with every
# collaborator faked (the tests/test_provider_dispatch.py harness shape).

import ast
import asyncio
import inspect
import uuid as _uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from sqlalchemy.dialects import postgresql

from src.gateway import jobs as jobs_mod
from src.gateway.jobs import enqueue_job

MAIN_SRC = Path(__file__).resolve().parent.parent / "src" / "runner" / "main.py"


class _RecordingSession:
    """`async_session()` / `session_scope()` stand-in that records what was
    added and executed and never touches a database."""

    def __init__(self):
        self.added: list = []
        self.executed: list = []

    def __call__(self):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def add(self, obj):
        self.added.append(obj)

    async def execute(self, stmt):
        self.executed.append(stmt)
        return SimpleNamespace(rowcount=1)

    async def commit(self):
        pass

    async def refresh(self, obj):
        pass


def _params(stmt) -> dict:
    return dict(stmt.compile(dialect=postgresql.dialect()).params)


class TestEnqueueSignature:
    def test_enqueue_job_accepts_origin_kwargs(self):
        params = inspect.signature(enqueue_job).parameters
        for name in ("origin_channel", "origin_ref", "origin_thread"):
            assert name in params and params[name].kind is inspect.Parameter.KEYWORD_ONLY
            assert params[name].default is None

    @pytest.fixture(autouse=True)
    def _fake_db(self, monkeypatch):
        self.db = _RecordingSession()
        self.redis = SimpleNamespace(rpush=AsyncMock())
        monkeypatch.setattr(jobs_mod, "async_session", self.db)
        monkeypatch.setattr(jobs_mod, "redis", self.redis)

    async def test_origin_is_derived_from_created_by_when_not_passed(self):
        job = await enqueue_job("reply pong", kind="chat", created_by="telegram:42")
        assert (job.origin_channel, job.origin_ref, job.origin_thread) == ("telegram", "42", None)
        assert self.db.added == [job]
        self.redis.rpush.assert_awaited_once()

    @pytest.mark.parametrize("created_by,expected", [
        ("web", ("web", None)),
        ("scheduler", ("scheduler", None)),
        ("dispatch-mcp", ("system", "dispatch-mcp")),
        ("", ("system", None)),
    ])
    async def test_derivation_matches_the_pure_helper(self, created_by, expected):
        job = await enqueue_job("x", created_by=created_by)
        assert (job.origin_channel, job.origin_ref) == expected

    async def test_explicit_channel_wins_and_ref_is_not_derived(self):
        # The web launch passes origin_channel="web" and no ref: the ref must
        # stay NULL (A1's CASE), not fall back to the created_by derivation.
        job = await enqueue_job("x", created_by="web", origin_channel="web")
        assert (job.origin_channel, job.origin_ref) == ("web", None)
        job = await enqueue_job("x", created_by="telegram:42", origin_channel="cli")
        assert (job.origin_channel, job.origin_ref) == ("cli", None)

    async def test_explicit_ref_overrides_the_derived_one(self):
        job = await enqueue_job("x", created_by="telegram:42", origin_ref="7")
        assert (job.origin_channel, job.origin_ref) == ("telegram", "7")

    async def test_thread_is_persisted_and_clipped(self):
        job = await enqueue_job("x", created_by="telegram:42", origin_thread="9" * 100)
        assert job.origin_thread == "9" * 64
        # The channel column (16) is wider than every declared channel, so
        # only the ref is ever clipped; an undeclared channel is refused.
        job = await enqueue_job("x", created_by="telegram:42", origin_ref="r" * 100,
                                origin_channel="web")
        assert len(job.origin_ref) == 64 and job.origin_channel == "web"

    async def test_empty_strings_land_as_null(self):
        job = await enqueue_job("x", created_by="telegram:42", origin_ref="", origin_thread="")
        assert job.origin_ref is None and job.origin_thread is None
        # An empty explicit channel derives exactly like an omitted one — it
        # must never be stored as "" (review round 1).
        job = await enqueue_job("x", created_by="telegram:42", origin_channel="")
        assert job.origin_channel == "telegram" and job.origin_ref == "42"

    async def test_unknown_explicit_channel_is_refused(self):
        # The column vocabulary is ORIGIN_CHANNELS (models.py comment, 008
        # backfill CASE); a caller cannot widen it by passing a new string.
        with pytest.raises(ValueError, match="origin_channel"):
            await enqueue_job("x", created_by="web", origin_channel="carrier-pigeon")


class TestAwaitingSince:
    NOW = datetime(2026, 10, 21, 12, 0, tzinfo=timezone.utc)

    def test_awaiting_statuses_get_a_stamp(self):
        from src.runner.main import awaiting_since_for
        assert awaiting_since_for("awaiting_user", self.NOW) == self.NOW
        assert awaiting_since_for("pending_approval", self.NOW) == self.NOW

    def test_other_statuses_clear_it(self):
        from src.runner.main import awaiting_since_for
        assert awaiting_since_for("active", self.NOW) is None
        assert awaiting_since_for("completed", self.NOW) is None
        assert awaiting_since_for("failed", self.NOW) is None

    def test_awaiting_statuses_are_the_two_task_wait_states(self):
        from src.runner.main import _AWAITING_STATUSES
        assert set(_AWAITING_STATUSES) == {"awaiting_user", "pending_approval"}

    async def test_set_task_status_stamps_and_clears_awaiting_since(self, monkeypatch):
        from src.runner import main as runner_main
        db = _RecordingSession()
        monkeypatch.setattr(runner_main, "session_scope", db)
        tid = _uuid.uuid4()
        await runner_main._set_task_status(tid, "awaiting_user")
        await runner_main._set_task_status(tid, "pending_approval")
        await runner_main._set_task_status(tid, "active")
        assert len(db.executed) == 3
        waiting, approval, active = (_params(s) for s in db.executed)
        assert waiting["status"] == "awaiting_user" and waiting["awaiting_since"] is not None
        assert waiting["awaiting_since"] == waiting["updated_at"]   # one clock read
        assert approval["awaiting_since"] is not None
        assert active["status"] == "active" and active["awaiting_since"] is None

    def test_no_inline_awaiting_user_update_remains_in_main(self):
        # The two `update(Task)...values(status=awaiting_user, …)` blocks in
        # _update_task_after_job are routed through _set_task_status so the
        # stamp has ONE writer. Any `.values(status=TaskStatus.awaiting_user…)`
        # call left in main.py would be a second, stamp-less writer.
        tree = ast.parse(MAIN_SRC.read_text())
        inline = [
            n for n in ast.walk(tree)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and n.func.attr == "values"
            and any(k.arg == "status" and "awaiting_user" in ast.unparse(k.value)
                    for k in n.keywords)
        ]
        assert inline == [], [ast.unparse(n) for n in inline]

    async def test_level_3_escalation_fails_the_task_through_set_task_status(self, monkeypatch):
        # _maybe_escalate's terminal (level >= 3) path used to write
        # `status=failed` inline, without updated_at / awaiting_since; it is
        # routed through _set_task_status so the runner keeps ONE writer of
        # tasks.status outside the sentinel block (review round 1).
        from src import db as db_mod
        from src.runner import main as runner_main
        from src.runner import plans as plans_mod
        calls: list = []

        async def _record(task_id, status):
            calls.append((task_id, status))

        monkeypatch.setattr(runner_main, "_set_task_status", _record)
        monkeypatch.setattr(plans_mod, "fail_dependents_of", AsyncMock(return_value=0))
        monkeypatch.setattr(db_mod, "redis", SimpleNamespace(publish=AsyncMock()))
        tid = _uuid.uuid4()
        job = SimpleNamespace(id=_uuid.uuid4(), task_id=tid, error_message="boom",
                              payload={"escalation_level": 3})
        await runner_main._maybe_escalate(job)
        assert calls == [(tid, "failed")]

    def test_no_inline_task_failed_update_remains_in_main(self):
        # Companion to the awaiting_user pin above: the level-3 terminal
        # write in _maybe_escalate is the only other Task status UPDATE the
        # runner had; it is routed through _set_task_status too.
        tree = ast.parse(MAIN_SRC.read_text())
        inline = [
            n for n in ast.walk(tree)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and n.func.attr == "values"
            and any(k.arg == "status" and "TaskStatus.failed" in ast.unparse(k.value)
                    for k in n.keywords)
        ]
        assert inline == [], [ast.unparse(n) for n in inline]

    def test_sentinel_pending_approval_update_carries_awaiting_since(self):
        # The auto-continue sentinel block keeps its shared session (it also
        # inserts a TaskTurn) so it cannot call _set_task_status; it must
        # stamp awaiting_since itself.
        tree = ast.parse(MAIN_SRC.read_text())
        sites = [
            n for n in ast.walk(tree)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and n.func.attr == "values"
            and any(k.arg == "status" and "pending_approval" in ast.unparse(k.value)
                    for k in n.keywords)
        ]
        assert sites, "no inline pending_approval update found (sentinel block moved?)"
        for call in sites:
            assert any(k.arg == "awaiting_since" for k in call.keywords), ast.unparse(call)


def test_queue_wait_ms():
    from src.runner.main import queue_wait_ms
    t0 = datetime(2026, 10, 21, 12, 0, tzinfo=timezone.utc)
    assert queue_wait_ms(t0, t0 + timedelta(seconds=2.5)) == 2500
    assert queue_wait_ms(None, t0) is None
    assert queue_wait_ms(t0, None) is None
    assert queue_wait_ms(t0 + timedelta(seconds=5), t0) == 0   # clock skew never negative


def test_running_flip_stamps_queue_wait_ms():
    # Source pin: the one place a job flips to `running` in _process_job
    # assigns queue_wait_ms right there, from created_at and started_at.
    tree = ast.parse(MAIN_SRC.read_text())
    process_job = next(n for n in ast.walk(tree)
                       if isinstance(n, ast.AsyncFunctionDef) and n.name == "_process_job")
    stamps = [
        n for n in ast.walk(process_job)
        if isinstance(n, ast.Assign) and len(n.targets) == 1
        and ast.unparse(n.targets[0]) == "job.queue_wait_ms"
    ]
    assert len(stamps) == 1
    assert "queue_wait_ms(" in ast.unparse(stamps[0].value)
    assert "started_at" in ast.unparse(stamps[0].value)


def test_scheduler_rows_carry_origin():
    # _tick_schedules builds the Job directly (not via enqueue_job): it must
    # stamp origin_channel="scheduler" and origin_ref=<schedule name>.
    tree = ast.parse(MAIN_SRC.read_text())
    tick = next(n for n in ast.walk(tree)
                if isinstance(n, ast.AsyncFunctionDef) and n.name == "_tick_schedules")
    ctor = next(n for n in ast.walk(tick)
                if isinstance(n, ast.Call) and ast.unparse(n.func) == "Job")
    kw = {k.arg: ast.unparse(k.value) for k in ctor.keywords}
    assert kw["created_by"] == "'scheduler'"
    assert kw["origin_channel"] == "'scheduler'"
    assert "sched.name" in kw["origin_ref"] and "[:64]" in kw["origin_ref"]


def _process_job_node() -> ast.AsyncFunctionDef:
    tree = ast.parse(MAIN_SRC.read_text())
    return next(n for n in ast.walk(tree)
                if isinstance(n, ast.AsyncFunctionDef) and n.name == "_process_job")


def test_every_failed_finish_passes_terminal_reason():
    # Source-level pin: every `_finish_job(<id>, JobStatus.failed, ...)` in
    # _process_job carries terminal_reason=, so no failed job is left with
    # NULL (preflight, skill-contract, deploy-refused, deploy-needs-approval,
    # timeout, generic — plus the typed non-Anthropic sites that already had it).
    sites = [n for n in ast.walk(_process_job_node())
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and n.func.id == "_finish_job" and len(n.args) >= 2
             and ast.unparse(n.args[1]) == "JobStatus.failed"]
    assert len(sites) >= 6, "expected preflight + 3 typed + timeout + generic"
    for call in sites:
        assert any(k.arg == "terminal_reason" for k in call.keywords), ast.unparse(call)


def test_every_job_failed_audit_carries_terminal_reason():
    # C14: `job_failed` keeps its name and fields and GAINS terminal_reason
    # on every branch, so the audit index and cost reconcile read one key.
    sites = [n for n in ast.walk(_process_job_node())
             if isinstance(n, ast.Call) and ast.unparse(n.func) == "audit_log.append"
             and len(n.args) >= 2 and ast.unparse(n.args[1]) == "'job_failed'"]
    assert len(sites) >= 6
    for call in sites:
        assert any(k.arg == "terminal_reason" for k in call.keywords), ast.unparse(call)


def _handlers_awaiting_finish() -> dict[str, ast.ExceptHandler]:
    """The asyncio.TimeoutError handler and the top-level `except Exception
    as exc` of _process_job (the ones that await _finish_job)."""
    found: dict[str, ast.ExceptHandler] = {}
    for node in ast.walk(_process_job_node()):
        if not isinstance(node, ast.ExceptHandler) or node.type is None:
            continue
        src = ast.unparse(node)
        if "_finish_job" not in src:
            continue
        t = ast.unparse(node.type)
        if t.endswith("TimeoutError"):
            found["timeout"] = node
        elif t == "Exception" and node.name == "exc":
            found["generic"] = node
    assert set(found) == {"timeout", "generic"}, set(found)
    return found


def _returns_when_cancelled(handler: ast.ExceptHandler) -> bool:
    for node in ast.walk(ast.Module(body=handler.body, type_ignores=[])):
        if isinstance(node, ast.If) and "cancelled" in ast.unparse(node.test):
            if any(isinstance(n, ast.Return) for n in ast.walk(node)):
                return True
    return False


class TestCancelledGuard:
    def test_both_handlers_return_before_escalating_a_cancelled_job(self):
        handlers = _handlers_awaiting_finish()
        assert _returns_when_cancelled(handlers["timeout"])
        assert _returns_when_cancelled(handlers["generic"])
        # …and the guard sits after the refetch (it reads the fresh status)
        # and before the escalation, in both.
        for h in handlers.values():
            src = ast.unparse(h)
            assert src.index("_refetch_job") < src.index("cancelled") < src.index("_maybe_escalate")

    @pytest.fixture
    def harness(self, tmp_path, monkeypatch):
        """_process_job with every collaborator faked; the refetched row's
        status is what the test says (the /cancel listener may flip it while
        the session is dying)."""
        from src.runner import main as runner_main
        from src.runner import session as session_mod
        from src.config import settings
        monkeypatch.setattr(settings, "server_root", tmp_path / "root")
        (tmp_path / "root").mkdir()

        def build(exc: BaseException, *, provider: str | None, refetched_status: str):
            now = datetime.now(timezone.utc)
            job = SimpleNamespace(
                id=_uuid.uuid4(), kind="demo", description="d", payload={},
                task_id=None, parent_job_id=None, project_id=None,
                created_by="telegram:1", status="queued", started_at=None,
                created_at=now - timedelta(seconds=3), resolved_skill="demo",
                resolved_provider=None, error_message=None,
            )
            db = _RecordingSession()
            db.get = AsyncMock(return_value=job)
            h = SimpleNamespace(job=job, finished=[], escalated=[], db=db)

            async def fake_run_session(j):
                raise exc

            async def fake_preflight(j, log):
                return None

            async def fake_finish(job_id, status, **kw):
                h.finished.append({"job_id": job_id, "status": status, **kw})

            async def fake_refetch(job_id, fallback, log):
                fallback.resolved_provider = provider
                fallback.status = refetched_status
                return fallback

            async def fake_escalate(j):
                h.escalated.append(j)

            monkeypatch.setattr(runner_main, "async_session", db)
            monkeypatch.setattr(runner_main, "_preflight_check", fake_preflight)
            monkeypatch.setattr(session_mod, "run_session", fake_run_session)
            monkeypatch.setattr(runner_main, "_finish_job", fake_finish)
            monkeypatch.setattr(runner_main, "_refetch_job", fake_refetch)
            monkeypatch.setattr(runner_main, "_maybe_escalate", fake_escalate)
            monkeypatch.setattr(runner_main, "_JOB_FETCH_DELAYS", (0.0,))
            return h

        return build

    @pytest.mark.parametrize("exc,reason", [
        (asyncio.TimeoutError(), "timeout"),
        # B3 replaced A2's interim "api_error" with the typed mapping
        # (`terminal_reason_for_exception`): a bare RuntimeError is `error`.
        (RuntimeError("boom"), "error"),
    ])
    async def test_cancelled_job_is_not_escalated(self, harness, exc, reason):
        from src.config import settings
        from src.runner import main as runner_main
        h = harness(exc, provider=None, refetched_status="cancelled")
        await runner_main._process_job(h.job.id)
        assert h.escalated == []
        # The guard sits between the refetch and the terminal stamp, so a
        # cancelled row is not even offered a `failed` stamp (the real
        # _finish_job's INV-9 WHERE would suppress it and publish nothing —
        # same outcome, one DB round-trip fewer). The audit line is typed.
        assert h.finished == []
        audit = (settings.audit_log_dir / f"{h.job.id}.jsonl").read_text()
        assert f'"terminal_reason": "{reason}"' in audit and '"job_failed"' in audit

    @pytest.mark.parametrize("exc", [asyncio.TimeoutError(), RuntimeError("boom")])
    async def test_running_job_still_escalates(self, harness, exc):
        # Control: the guard only fires on `cancelled`.
        from src.runner import main as runner_main
        h = harness(exc, provider=None, refetched_status="running")
        await runner_main._process_job(h.job.id)
        assert h.escalated == [h.job]

    async def test_running_flip_stamps_queue_wait(self, harness):
        from src.runner import main as runner_main
        h = harness(RuntimeError("boom"), provider=None, refetched_status="running")
        await runner_main._process_job(h.job.id)
        assert h.job.status == "running"      # flipped inside the fake session
        assert isinstance(h.job.queue_wait_ms, int) and 2500 <= h.job.queue_wait_ms <= 10_000
