"""
Shared test fixtures.

Historically the suite was pure-function-only (no DB/Redis/SDK); `fakeredis`
was a declared dev dep that nothing used. This adds an in-memory Redis fixture
so the highest-blast-radius Redis paths (quota pause/resume, queue state) get
real coverage without a live server. DB/SDK integration remains out of scope
here — those need a temp Postgres / SDK harness (see test_migrations.py for the
opt-in Postgres gate).
"""

from __future__ import annotations

import os

# ── Never let a test reach the live Postgres or Redis ───────────────────────
# The suite is pure/fixture style, but `pydantic-settings` reads `.env` from the
# CWD even under PIPENV_DONT_LOAD_ENV=1, and the dev `.env` points at the
# PRODUCTION database; the prod deploy gate runs with prod's `.env` exported.
# On 2026-10-22 a test that drove `_notify_task` without patching the outbox
# session inserted a real `notifications` row on prod and the bot DM'd it.
# Point both DSNs at a closed port BEFORE `src.db` builds its engine/client, so
# an unpatched access fails fast instead of touching production. The opt-in
# Postgres migration test (AI_SERVER_RUN_DB_TESTS=1) needs the real DSN prefix
# to derive its throwaway database, so it is the one exemption.
if os.environ.get("AI_SERVER_RUN_DB_TESTS") != "1":
    os.environ["POSTGRES_DSN"] = "postgresql+asyncpg://nobody:nobody@127.0.0.1:1/aiserver_tests_never_connect"
    os.environ["REDIS_URL"] = "redis://127.0.0.1:1/0"

import pytest

try:
    import fakeredis.aioredis as _fakeredis_aio
    _HAVE_FAKEREDIS = True
except Exception:  # pragma: no cover
    _HAVE_FAKEREDIS = False


@pytest.fixture
async def fake_redis(monkeypatch):
    """An in-memory async Redis, swapped in for the module-level `redis`
    clients that `src.db` and the runner modules bind at import time.

    decode_responses=True mirrors the real client (src/db.py), so code that
    does `datetime.fromisoformat(await redis.get(...))` behaves identically.
    """
    if not _HAVE_FAKEREDIS:
        pytest.skip("fakeredis not installed")
    fake = _fakeredis_aio.FakeRedis(decode_responses=True)
    # Patch every module that did `from src.db import redis` (binds its own name).
    monkeypatch.setattr("src.db.redis", fake, raising=False)
    monkeypatch.setattr("src.runner.quota.redis", fake, raising=False)
    yield fake
    try:
        await fake.aclose()
    except Exception:
        pass
