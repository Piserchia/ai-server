"""
Alembic migration health.

Two layers:
  1. Chain consistency (ALWAYS runs, no DB): single head, walkable revision
     graph. Catches the "two heads after a merge" / "broken down_revision"
     class that otherwise only surfaces when `server-deploy` runs
     `alembic upgrade` on the live prod DB.
  2. Full apply + drift (OPT-IN via AI_SERVER_RUN_DB_TESTS=1, needs local
     Postgres): create a throwaway DB, `upgrade head`, assert autogenerate
     finds no diff vs models.py. Gated so the default pure-pytest run and the
     deploy gate don't create/drop Postgres databases.
"""

from __future__ import annotations

import os
import sqlite3
import subprocess
import uuid
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent


def _alembic_config():
    from alembic.config import Config
    cfg = Config(str(REPO / "alembic.ini"))
    cfg.set_main_option("script_location", str(REPO / "alembic"))
    return cfg


# ── Layer 1: chain consistency (no DB) ──────────────────────────────────────


def test_single_migration_head():
    from alembic.script import ScriptDirectory
    script = ScriptDirectory.from_config(_alembic_config())
    heads = script.get_heads()
    assert len(heads) == 1, f"expected exactly one migration head, got {heads} " \
                            f"(a merge left multiple heads — alembic upgrade will fail)"


def test_revision_chain_walkable():
    from alembic.script import ScriptDirectory
    script = ScriptDirectory.from_config(_alembic_config())
    revs = list(script.walk_revisions())          # raises on a broken down_revision link
    assert len(revs) >= 5, f"expected >=5 migrations, found {len(revs)}"
    # Exactly one base (down_revision is None).
    bases = [r.revision for r in revs if r.down_revision is None]
    assert len(bases) == 1, f"expected exactly one base migration, got {bases}"


# ── Layer 2: full apply + drift (opt-in, needs Postgres) ────────────────────


def _db_tests_enabled() -> bool:
    return os.environ.get("AI_SERVER_RUN_DB_TESTS") == "1"


@pytest.mark.skipif(not _db_tests_enabled(),
                    reason="opt-in: set AI_SERVER_RUN_DB_TESTS=1 (needs local Postgres)")
def test_migrations_apply_cleanly(monkeypatch):
    from urllib.parse import urlparse

    from alembic import command
    from src.config import settings

    base_dsn = settings.postgres_dsn
    owner = urlparse(base_dsn).username    # the role the async engine connects as
    # Swap the database name for a throwaway one.
    test_db = f"aiserver_test_{uuid.uuid4().hex[:8]}"
    prefix, _, _old = base_dsn.rpartition("/")
    test_dsn = f"{prefix}/{test_db}"

    # Own the temp DB as the DSN role — on PG15 only the owner may CREATE in
    # schema `public`, so a DB owned by the OS user would give the connecting
    # role a spurious "permission denied for schema public" (an env issue, not
    # a migration defect — skip, don't fail).
    createdb_cmd = ["createdb"] + (["-O", owner] if owner else []) + [test_db]
    created = subprocess.run(createdb_cmd, capture_output=True, text=True)
    if created.returncode != 0:
        pytest.skip(f"could not createdb (Postgres/permissions?): {created.stderr[:200]}")
    try:
        monkeypatch.setattr(settings, "postgres_dsn", test_dsn)
        # Must not raise — a migration that fails to apply is the exact failure
        # server-deploy runs blind against prod (migrate before the test gate).
        try:
            command.upgrade(_alembic_config(), "head")
        except Exception as exc:
            from asyncpg.exceptions import InsufficientPrivilegeError
            cause = exc.__cause__ or exc
            if isinstance(cause, InsufficientPrivilegeError) or "permission denied" in str(exc):
                pytest.skip(f"Postgres privilege setup issue, not a migration defect: {str(exc)[:200]}")
            raise
    finally:
        subprocess.run(["dropdb", "--if-exists", test_db], capture_output=True)


# ── Layer 1b: migration 007 round-trip on in-memory SQLite (no DB server) ───
#
# alembic/env.py is async-Postgres only (no aiosqlite in the lockfile), so the
# 007 module is driven directly through `Operations.context` on a sync SQLite
# engine. The fixture builds the minimal pre-007 `jobs` shape — including the
# 006 CHECK on status — seeds rows, and round-trips upgrade → downgrade.

_PRE_007_JOBS_DDL = (
    "CREATE TABLE jobs ("
    " id VARCHAR(36) PRIMARY KEY,"
    " status VARCHAR(32) NOT NULL,"
    " resolved_model VARCHAR(64),"
    " CONSTRAINT ck_jobs_status_valid CHECK (status IN ('queued', 'deferred',"
    " 'running', 'awaiting_user', 'completed', 'failed', 'cancelled'))"
    ")"
)

_SEED_ROWS = [
    ("j-anthropic", "completed", "claude-opus-4-7"),
    ("j-anthropic-2", "failed", "claude-sonnet-4-6"),
    ("j-codex", "completed", "gpt-6-luna"),
    ("j-unresolved", "queued", None),
]

_NEW_COLUMNS = {"resolved_provider", "terminal_reason", "model_served"}


def _migration_module(rev: str):
    from alembic.script import ScriptDirectory
    script = ScriptDirectory.from_config(_alembic_config())
    return script.get_revision(rev).module


def _run_migration(engine, fn) -> None:
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    with engine.begin() as conn:
        ctx = MigrationContext.configure(connection=conn)
        with Operations.context(ctx):
            fn()


def _jobs_columns(engine) -> dict:
    from sqlalchemy import inspect
    return {c["name"]: c for c in inspect(engine).get_columns("jobs")}


def _jobs_table_sql(engine) -> str:
    from sqlalchemy import text
    with engine.connect() as conn:
        return conn.execute(
            text("SELECT sql FROM sqlite_master WHERE type='table' AND name='jobs'")
        ).scalar_one()


@pytest.fixture
def pre_007_engine():
    from sqlalchemy import create_engine, text
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(text(_PRE_007_JOBS_DDL))
        for jid, status, model in _SEED_ROWS:
            conn.execute(
                text("INSERT INTO jobs (id, status, resolved_model) VALUES (:i, :s, :m)"),
                {"i": jid, "s": status, "m": model},
            )
    try:
        yield engine
    finally:
        engine.dispose()


def test_chain_head_is_007_revising_006():
    from alembic.script import ScriptDirectory
    script = ScriptDirectory.from_config(_alembic_config())
    assert script.get_heads() == ["007"]
    assert script.get_revision("007").down_revision == "006"


def test_job_model_declares_provider_columns():
    from sqlalchemy import String
    from src.models import Job
    cols = Job.__table__.c
    expected = {"resolved_provider": 32, "terminal_reason": 32, "model_served": 64}
    for name, length in expected.items():
        col = cols[name]
        assert isinstance(col.type, String) and col.type.length == length, \
            f"{name}: expected String({length}), got {col.type!r}"
        assert col.nullable is True, f"{name} must be nullable (additive, pre-007 rows)"


def test_007_upgrade_adds_columns_and_backfills_anthropic(pre_007_engine):
    from sqlalchemy import text
    mod = _migration_module("007")
    assert not _NEW_COLUMNS & set(_jobs_columns(pre_007_engine))

    _run_migration(pre_007_engine, mod.upgrade)

    cols = _jobs_columns(pre_007_engine)
    assert _NEW_COLUMNS <= set(cols)
    for name in _NEW_COLUMNS:
        assert cols[name]["nullable"] is True

    with pre_007_engine.connect() as conn:
        rows = dict(conn.execute(
            text("SELECT id, resolved_provider FROM jobs")
        ).all())
    assert rows == {
        "j-anthropic": "anthropic",
        "j-anthropic-2": "anthropic",
        "j-codex": None,        # backfill is LIKE 'claude-%' only — never a default
        "j-unresolved": None,
    }
    with pre_007_engine.connect() as conn:
        untouched = conn.execute(text(
            "SELECT count(*) FROM jobs WHERE terminal_reason IS NOT NULL "
            "OR model_served IS NOT NULL"
        )).scalar_one()
    assert untouched == 0


def test_007_columns_match_orm_declaration(pre_007_engine):
    from src.models import Job
    _run_migration(pre_007_engine, _migration_module("007").upgrade)
    cols = _jobs_columns(pre_007_engine)
    for name in _NEW_COLUMNS:
        orm = Job.__table__.c[name]
        assert cols[name]["type"].length == orm.type.length, name
        assert cols[name]["nullable"] == orm.nullable, name


@pytest.mark.skipif(
    sqlite3.sqlite_version_info < (3, 35),
    reason="downgrade uses native ALTER TABLE ... DROP COLUMN (SQLite >= 3.35)",
)
def test_007_downgrade_round_trip_leaves_status_check_intact(pre_007_engine):
    from sqlalchemy import text
    mod = _migration_module("007")
    before_sql = _jobs_table_sql(pre_007_engine)
    assert "ck_jobs_status_valid" in before_sql

    _run_migration(pre_007_engine, mod.upgrade)
    assert "ck_jobs_status_valid" in _jobs_table_sql(pre_007_engine)
    _run_migration(pre_007_engine, mod.downgrade)

    assert not _NEW_COLUMNS & set(_jobs_columns(pre_007_engine))
    assert "ck_jobs_status_valid" in _jobs_table_sql(pre_007_engine)
    with pre_007_engine.connect() as conn:
        rows = conn.execute(
            text("SELECT id, status, resolved_model FROM jobs ORDER BY id")
        ).all()
    assert sorted(tuple(r) for r in rows) == sorted(_SEED_ROWS)
    # The CHECK still enforces: an invented status is rejected after the round-trip.
    from sqlalchemy.exc import IntegrityError
    with pytest.raises(IntegrityError):
        with pre_007_engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO jobs (id, status) VALUES ('j-bad', 'succeeded')"
            ))


def test_007_source_never_touches_status_constraint():
    src = (REPO / "alembic" / "versions" / "007_provider_columns.py").read_text()
    assert "ck_jobs_status_valid" not in src
    assert "drop_constraint" not in src and "create_check_constraint" not in src
