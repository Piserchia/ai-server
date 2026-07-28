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
