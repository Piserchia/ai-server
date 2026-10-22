"""The test suite must never reach the live Postgres/Redis (tests/conftest.py guard).

Regression for 2026-10-22: a test drove the runner's dual-write `_notify_task`
without patching the outbox session; on the prod deploy gate (prod `.env`
exported) it inserted a real `notifications` row and the bot delivered it.
"""
from __future__ import annotations

import os

import pytest


@pytest.mark.skipif(os.environ.get("AI_SERVER_RUN_DB_TESTS") == "1",
                    reason="opt-in DB mode uses the real DSN on purpose")
def test_settings_point_at_a_closed_port():
    from src.config import settings
    assert "127.0.0.1:1/" in settings.postgres_dsn
    assert settings.redis_url.startswith("redis://127.0.0.1:1/")


@pytest.mark.skipif(os.environ.get("AI_SERVER_RUN_DB_TESTS") == "1",
                    reason="opt-in DB mode uses the real DSN on purpose")
def test_engine_and_redis_client_are_bound_to_the_closed_port():
    from src import db
    assert db.engine.url.port == 1
    assert db.engine.url.host == "127.0.0.1"
    assert db.redis.connection_pool.connection_kwargs.get("port") == 1


async def test_unpatched_outbox_insert_fails_closed_without_raising():
    """`enqueue_notice` must swallow the connection failure (producers never
    raise) — and, because of the guard, it can never land on production."""
    if os.environ.get("AI_SERVER_RUN_DB_TESTS") == "1":
        pytest.skip("opt-in DB mode")
    from src.notify import outbox
    notice = outbox.build_ops_notice(kind="ops_alert", severity="warn", text="guard probe")
    assert await outbox.enqueue_notice(notice) is None
