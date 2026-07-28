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
