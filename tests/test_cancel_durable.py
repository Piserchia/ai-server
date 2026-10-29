"""
E3 — durable cancel, one semantics (D-P1-4): a queued/deferred job leaves Redis
and flips to `cancelled` with `terminal_reason="interrupted"` and
`error_message="cancelled by user (<stage>)"` in ONE place (`cancel_job_durable`);
a running job gets the `jobs:cancel` publish (the runner interrupts and stamps
the same vocabulary); anything else is a no-op. The four cancel sites — the
runner listener, the task Cancel button, `/cancel <prefix>`, `DELETE /api/jobs`
(and E4's `/clear`) — all route through it. Pure/fixture style: fake Redis, a
fake session capturing the UPDATE.

Run: PIPENV_DONT_LOAD_ENV=1 SERVER_ROOT="$PWD" pipenv run pytest tests/test_cancel_durable.py -q
"""

from __future__ import annotations

import inspect
import uuid
from types import SimpleNamespace

import pytest

from src import audit_log
from src.db import QUEUE_JOBS
from src.gateway import jobs as jobs_mod
from src.gateway.jobs import cancel_action_for_status, cancel_job_durable, remove_from_queue


class TestCancelAction:
    @pytest.mark.parametrize("status,expected", [
        ("queued", "lrem_and_flip"), ("deferred", "lrem_and_flip"),
        ("running", "publish"), ("awaiting_user", "noop"),
        ("completed", "noop"), ("failed", "noop"), ("cancelled", "noop"),
    ])
    def test_mapping(self, status, expected):
        assert cancel_action_for_status(status) == expected

    def test_cancel_action_noop_for_terminal(self):
        # The second /cancel of the same job must be a no-op.
        assert cancel_action_for_status("cancelled") == "noop"


class TestRemoveFromQueue:
    async def test_remove_from_queue_idempotent(self, fake_redis, monkeypatch):
        monkeypatch.setattr(jobs_mod, "redis", fake_redis)
        jid = str(uuid.uuid4())
        other = str(uuid.uuid4())
        await fake_redis.rpush(QUEUE_JOBS, other, jid, jid)   # duplicates from a requeue race
        assert await remove_from_queue(jid) == 2
        assert await remove_from_queue(jid) == 0               # second cancel: nothing to remove
        assert await fake_redis.lrange(QUEUE_JOBS, 0, -1) == [other]


class _FakeDB:
    """Captures every statement; `results` is what each execute reports, in
    order — an int is a rowcount (the guarded UPDATE), a str is the scalar a
    re-read of `Job.status` returns."""

    def __init__(self, results):
        self.results = list(results)
        self.statements = []

    def __call__(self):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def execute(self, stmt):
        self.statements.append(stmt)
        r = self.results.pop(0)
        if isinstance(r, str):
            return SimpleNamespace(rowcount=0, scalar=lambda: r)
        return SimpleNamespace(rowcount=r, scalar=lambda: None)

    async def commit(self):
        pass


def _params(stmt) -> dict:
    return dict(stmt.compile().params)


def _job(status: str):
    return SimpleNamespace(id=uuid.uuid4(), status=status)


def _kinds(job_id) -> list[dict]:
    return [e for e in audit_log.read(str(job_id)) if e["kind"] == "job_cancelled"]


class TestCancelJobDurable:
    async def test_queued_row_is_flipped_once_with_interrupted(self, fake_redis, monkeypatch):
        monkeypatch.setattr(jobs_mod, "redis", fake_redis)
        db = _FakeDB([1])
        monkeypatch.setattr(jobs_mod, "async_session", db)
        job = _job("queued")
        await fake_redis.rpush(QUEUE_JOBS, str(job.id))

        assert await cancel_job_durable(job, stage="telegram") == "cancelled_queued"
        assert await fake_redis.lrange(QUEUE_JOBS, 0, -1) == []
        p = _params(db.statements[0])
        assert p["status"] == "cancelled"
        assert p["terminal_reason"] == "interrupted"                   # D-P1-4: never a 16th value
        assert p["error_message"] == "cancelled by user (telegram)"
        assert "completed_at" in p
        # The guard: only THIS row, and only while still queued/deferred (INV-9 safe).
        where = str(db.statements[0].compile(compile_kwargs={"literal_binds": True}))
        assert "queued" in where and "deferred" in where and "WHERE" in where
        assert job.id.hex in where                  # literal_binds renders the UUID as hex
        events = _kinds(job.id)
        assert len(events) == 1 and events[0]["stage"] == "telegram"

        # Second cancel: the row is already cancelled → the guarded UPDATE hits
        # nothing → no second audit row, and the caller is told.
        job.status = "cancelled"
        assert await cancel_job_durable(job, stage="telegram") == "already_terminal"
        assert len(_kinds(job.id)) == 1

    async def test_the_flip_happens_before_the_lrem(self, fake_redis, monkeypatch):
        # Review 2026-10-29: LREM first would strand a queued row in Postgres
        # (invisible until the next restart's requeue) if the UPDATE then
        # failed. UPDATE first: a Redis failure leaves a dead id the runner
        # skips gracefully (main._process_job returns on status != queued).
        monkeypatch.setattr(jobs_mod, "redis", fake_redis)
        order = []

        class _DB(_FakeDB):
            async def execute(self, stmt):
                order.append("update")
                return await super().execute(stmt)
        monkeypatch.setattr(jobs_mod, "async_session", _DB([1]))
        real_lrem = fake_redis.lrem

        async def lrem(*a, **k):
            order.append("lrem")
            return await real_lrem(*a, **k)
        monkeypatch.setattr(fake_redis, "lrem", lrem)
        await cancel_job_durable(_job("queued"), stage="api")
        assert order == ["update", "lrem"]

    async def test_a_race_with_the_running_flip_falls_through_to_the_publish(self, fake_redis, monkeypatch):
        # The row read `queued` but the runner flipped it to running between
        # the read and our UPDATE: rowcount 0 → re-read → it is RUNNING → the
        # user's cancel is not dropped; it becomes the publish (review
        # 2026-10-29: before E3, DELETE /api/jobs published for any
        # non-terminal row, so dropping it here would have been a regression).
        monkeypatch.setattr(jobs_mod, "redis", fake_redis)
        monkeypatch.setattr(jobs_mod, "async_session", _FakeDB([0, "running"]))
        published = []

        async def fake_cancel(job_id):
            published.append(str(job_id))
        monkeypatch.setattr(jobs_mod, "cancel_job", fake_cancel)
        job = _job("queued")
        assert await cancel_job_durable(job, stage="api") == "cancel_requested"
        assert published == [str(job.id)] and _kinds(job.id) == []

    async def test_a_race_with_another_cancel_is_reported_not_double_written(self, fake_redis, monkeypatch):
        # rowcount 0 and the fresh status is terminal → honest reply, no audit row.
        monkeypatch.setattr(jobs_mod, "redis", fake_redis)
        monkeypatch.setattr(jobs_mod, "async_session", _FakeDB([0, "cancelled"]))
        job = _job("queued")
        assert await cancel_job_durable(job, stage="api") == "already_terminal"
        assert _kinds(job.id) == []

    async def test_running_row_publishes_cancel(self, fake_redis, monkeypatch):
        monkeypatch.setattr(jobs_mod, "redis", fake_redis)
        db = _FakeDB([])
        monkeypatch.setattr(jobs_mod, "async_session", db)
        published = []

        async def fake_cancel(job_id):
            published.append(str(job_id))
        monkeypatch.setattr(jobs_mod, "cancel_job", fake_cancel)
        job = _job("running")
        assert await cancel_job_durable(job, stage="button") == "cancel_requested"
        assert published == [str(job.id)] and db.statements == []
        assert _kinds(job.id) == []            # the runner writes job_cancelled when it interrupts

    async def test_deferred_row_is_cancelled(self, fake_redis, monkeypatch):
        monkeypatch.setattr(jobs_mod, "redis", fake_redis)
        db = _FakeDB([1])
        monkeypatch.setattr(jobs_mod, "async_session", db)
        job = _job("deferred")
        assert await cancel_job_durable(job, stage="cleared") == "cancelled_queued"
        assert _params(db.statements[0])["error_message"] == "cancelled by user (cleared)"
        assert _kinds(job.id)[0]["stage"] == "cleared"

    async def test_terminal_row_is_a_noop(self, fake_redis, monkeypatch):
        monkeypatch.setattr(jobs_mod, "redis", fake_redis)
        db = _FakeDB([])
        monkeypatch.setattr(jobs_mod, "async_session", db)
        for status in ("completed", "failed", "cancelled", "awaiting_user"):
            assert await cancel_job_durable(_job(status), stage="api") == "already_terminal"
        assert db.statements == []


class TestTheFourSitesShareOneVocabulary:
    def test_runner_listener_stamps_interrupted_and_the_stage(self):
        # The running-job site: session.interrupt() succeeded → the row gets
        # the same terminal_reason / error_message vocabulary and a
        # job_cancelled{stage="running"} audit row.
        from src.runner import main as runner_main
        src = inspect.getsource(runner_main._cancel_listener)
        assert 'terminal_reason="interrupted"' in src or "terminal_reason='interrupted'" in src
        assert "cancelled by user (running)" in src
        assert 'stage="running"' in src

    def test_button_and_api_route_through_the_durable_path(self):
        from src.gateway import telegram_bot, web
        button = inspect.getsource(telegram_bot._handle_button)
        assert 'cancel_job_durable(' in button and 'stage="button"' in button
        assert '"task cancelled by user"' not in button            # the old second vocabulary is gone
        api = inspect.getsource(web.delete_job)
        assert 'cancel_job_durable(' in api and 'stage="api"' in api
        assert "is_terminal" not in api                             # the durable path decides

    def test_audit_docstring_names_the_stage(self):
        import pathlib
        doc = pathlib.Path(audit_log.__file__).read_text(encoding="utf-8")
        line = next(l for l in doc.splitlines() if l.startswith("- job_cancelled:"))
        assert "stage" in line
