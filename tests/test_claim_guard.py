"""
INV-9 — the runner's queued→running claim is a GUARDED update (follow-up to
Tier B E3, whole-branch review 2026-10-29 finding #4).

`_process_job` used to read the row, await a Redis round-trip, then set
`job.status = running` through the ORM and commit — an UPDATE with no status
predicate. A `cancel_job_durable` that committed `cancelled` inside that window
was overwritten: the job ran, with a `job_cancelled` audit row and a "removed
from the queue" reply that were both false. Now the claim is one core UPDATE
`… WHERE id = :id AND status = 'queued'`; rowcount 0 means someone else owns
the row (a cancel, another worker) and the job is NOT run.

Pure: a fake session that reports the rowcount the test chooses; every
collaborator of `_process_job` faked; no DB, no Redis, no SDK.

Run: PIPENV_DONT_LOAD_ENV=1 SERVER_ROOT="$PWD" pipenv run pytest tests/test_claim_guard.py -q
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from src.config import settings


class _Session:
    def __init__(self, job, rowcount: int):
        self.job = job
        self.rowcount = rowcount
        self.statements: list = []
        self.commits = 0

    def __call__(self):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, model, job_id):
        return self.job

    async def execute(self, stmt):
        self.statements.append(stmt)
        return SimpleNamespace(rowcount=self.rowcount)

    async def commit(self):
        self.commits += 1


@pytest.fixture
def claim(tmp_path, monkeypatch):
    from src.runner import main as runner_main
    from src.runner import session
    monkeypatch.setattr(settings, "server_root", tmp_path / "root")
    (tmp_path / "root").mkdir()

    def build(rowcount: int):
        job = SimpleNamespace(id=uuid.uuid4(), kind="demo", status="queued", started_at=None,
                              queue_wait_ms=None, created_at=None, resolved_skill="demo",
                              resolved_provider=None, error_message=None, payload={},
                              task_id=None, parent_job_id=None, created_by="telegram:1",
                              description="x")
        h = SimpleNamespace(db=_Session(job, rowcount), job=job, ran=[], finished=[])

        async def fake_run_session(j):
            h.ran.append(j.id)
            return {"summary": "ok", "usage": {}, "provider": "anthropic"}

        async def fake_preflight(j, log):
            return None

        async def fake_finish(job_id, status, **kw):
            h.finished.append((status, kw))

        async def fake_refetch(job_id, fallback, log):
            return fallback

        async def fake_hold(j, log):
            return False

        monkeypatch.setattr(runner_main, "async_session", h.db)
        monkeypatch.setattr(runner_main, "_preflight_check", fake_preflight)
        monkeypatch.setattr(session, "run_session", fake_run_session)
        monkeypatch.setattr(runner_main, "_finish_job", fake_finish)
        monkeypatch.setattr(runner_main, "_refetch_job", fake_refetch)
        monkeypatch.setattr(runner_main, "_hold_if_provider_paused", fake_hold)
        monkeypatch.setattr(runner_main, "_JOB_FETCH_DELAYS", (0.0,))
        # the post-steps after the session are not under test
        for name in ("_maybe_escalate", "_notify_task", "_maybe_review", "_verify_writeback"):
            async def _noop(*a, **k):
                return None
            monkeypatch.setattr(runner_main, name, _noop)
        return h

    return build


async def test_the_claim_is_one_guarded_update(claim):
    from src.runner import main as runner_main
    h = claim(rowcount=1)
    await runner_main._process_job(h.job.id)
    assert h.ran == [h.job.id]                               # the claim won → the job ran
    claims = [s for s in h.db.statements if "jobs" in str(s).lower() and "running" in
              str(s.compile(compile_kwargs={"literal_binds": True}))]
    assert len(claims) == 1, [str(s) for s in h.db.statements]
    sql = str(claims[0].compile(compile_kwargs={"literal_binds": True}))
    assert "UPDATE jobs" in sql and "WHERE" in sql
    where = sql.split("WHERE", 1)[1]
    assert "jobs.status = 'queued'" in where                                   # the INV-9 predicate
    params = dict(claims[0].compile().params)                                 # dialect-independent
    assert h.job.id in params.values()
    assert "started_at" in sql and "queue_wait_ms" in sql
    assert h.db.commits >= 1
    # the local object mirrors the row the UPDATE wrote
    assert h.job.status == "running" and h.job.started_at is not None


async def test_a_lost_claim_never_runs_the_job(claim):
    # The row read `queued` but a durable cancel (or another worker) committed
    # first → our guarded UPDATE matched 0 rows → nothing runs, nothing is
    # finished, and the local object is not flipped.
    from src.runner import main as runner_main
    h = claim(rowcount=0)
    await runner_main._process_job(h.job.id)
    assert h.ran == []
    assert h.finished == []
    assert h.job.status == "queued"


def test_no_unguarded_orm_flip_remains():
    # AST ordering: the local `job.status = running` assignment must come
    # AFTER the `if res.rowcount == 0: return` check, so no flip of the
    # in-memory object can happen for a lost claim, and the only UPDATE that
    # writes `running` carries the `status == queued` predicate.
    import ast
    import inspect
    import textwrap
    from src.runner import main as runner_main
    tree = ast.parse(textwrap.dedent(inspect.getsource(runner_main._process_job)))
    flips = [n for n in ast.walk(tree) if isinstance(n, ast.Assign)
             and ast.unparse(n.targets[0]) == "job.status"
             and ast.unparse(n.value) == "JobStatus.running.value"]
    checks = [n for n in ast.walk(tree) if isinstance(n, ast.If) and "rowcount" in ast.unparse(n.test)]
    assert len(flips) == 1 and len(checks) == 1
    assert flips[0].lineno > checks[0].end_lineno
    claims = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
              and ast.unparse(n.func).endswith(".where")
              and "Job.status == JobStatus.queued.value" in ast.unparse(n)]
    assert len(claims) == 1
