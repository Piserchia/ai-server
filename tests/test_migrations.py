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
    assert len(revs) >= 8, f"expected >=8 migrations, found {len(revs)}"
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
            cfg = _alembic_config()
            command.upgrade(cfg, "head")
            # A1 Accept: the head migration's downgrade must apply on Postgres
            # too (the plan's rollback precondition, `alembic downgrade -1` on
            # prod) and head must re-apply to the downgraded shape — the 008
            # backfills are idempotent (whole-tier review 2026-10-22: the
            # round-trip was promised by the Accept line but only `upgrade
            # head` ran here).
            command.downgrade(cfg, "-1")
            command.upgrade(cfg, "head")
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


def test_head_is_008_revising_007():
    # Retargeted from "head is 007 revising 006" when Observability Phase 1
    # (re-cut plan A1) landed 008 on top of the slice's 007.
    from alembic.script import ScriptDirectory
    script = ScriptDirectory.from_config(_alembic_config())
    assert script.get_current_head() == "008"
    assert script.get_revision("008").down_revision == "007"
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


# ── Layer 1b (008): Observability Phase 1 shape + SQLite round-trip ─────────
#
# Re-cut plan A1 (docs/superpowers/plans/2026-10-21-observability-phase1-recut.md).
# 008 adds 17 nullable `jobs` columns, 4 nullable `tasks` columns and the
# `notifications` outbox. Its three backfills are Postgres-only SQL
# (`result->'usage'`, `split_part`, `::text`) and are guarded by dialect so
# the same module round-trips on this in-memory SQLite harness.

P0_JOB_COLUMNS = (
    "cli_version", "lane",
    "origin_channel", "origin_ref", "origin_thread", "queue_wait_ms",
    "first_event_at", "input_tokens", "output_tokens", "cache_read_tokens",
    # Two cache-write columns, not one: the subscription's TTL is 1 h and prod
    # records 100 % of writes as 1-h, priced $10/M Opus vs the $6.25/M 5-m rate
    # (spec §2.3, §2.8). A 5-m reading is itself the credit-overflow signature.
    "cache_write_1h_tokens", "cache_write_5m_tokens",
    # TWO cost columns, never one: cost_usd_list is the RUNNER's computation
    # from tokens via src/runner/pricing.py (B1), sdk_cost_usd is the SDK's own
    # ResultMessage.total_cost_usd, stored beside it and never assumed equal.
    "num_turns", "duration_api_ms", "cost_usd_list", "sdk_cost_usd",
    "task_class",
)
# NOT re-added by 008: `model_served` and `terminal_reason` exist since 007
# (`op.add_column` would raise DuplicateColumn). NOT in 008 at all: `priority`
# (lanes replace it), `executor`, `sensitivity` (deleted vendor scope).
# `resolved_provider` EXISTS via 007 and stays — it is not forbidden here.
FORBIDDEN_008_COLUMNS = ("priority", "executor", "sensitivity")
P0_TASK_COLUMNS = ("origin_channel", "origin_ref", "origin_thread", "awaiting_since")
P0_NOTIFICATION_COLUMNS = (
    "id", "notice_kind", "subject_type", "subject_id", "severity", "body", "actions",
    "channel", "target", "thread", "external_ref", "status", "attempts", "last_error",
    "next_attempt_at", "sent_at", "created_at",
)
_008_SRC = REPO / "alembic" / "versions" / "008_p0_observability.py"

# Pre-008 shape: the 007 columns are present, plus the columns the 008
# backfills READ (created_by, result on jobs; chat_id, thread_message_id on
# tasks), so a Postgres run of the same DDL would have something to read.
_PRE_008_JOBS_DDL = (
    "CREATE TABLE jobs ("
    " id VARCHAR(36) PRIMARY KEY,"
    " status VARCHAR(32) NOT NULL,"
    " created_by VARCHAR(64) NOT NULL DEFAULT 'unknown',"
    " result JSON,"
    " resolved_model VARCHAR(64),"
    " resolved_provider VARCHAR(32),"
    " terminal_reason VARCHAR(32),"
    " model_served VARCHAR(64),"
    " CONSTRAINT ck_jobs_status_valid CHECK (status IN ('queued', 'deferred',"
    " 'running', 'awaiting_user', 'completed', 'failed', 'cancelled'))"
    ")"
)
_PRE_008_TASKS_DDL = (
    "CREATE TABLE tasks ("
    " id VARCHAR(36) PRIMARY KEY,"
    " status VARCHAR(20) NOT NULL,"
    " chat_id BIGINT,"
    " thread_message_id BIGINT"
    ")"
)
_SEED_008_JOBS = [
    ("j-tg", "completed", "telegram:123", "claude-opus-4-7", "anthropic"),
    ("j-web", "completed", "web", "claude-sonnet-4-6", "anthropic"),
    ("j-sched", "failed", "scheduler", "gpt-6-luna", "codex"),
    ("j-sys", "queued", "dispatch-mcp", None, None),
]
_SEED_008_TASKS = [("t-1", "active", 123, 456), ("t-2", "completed", None, None)]


@pytest.fixture
def pre_008_engine():
    from sqlalchemy import create_engine, text
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(text(_PRE_008_JOBS_DDL))
        conn.execute(text(_PRE_008_TASKS_DDL))
        for jid, status, created_by, model, provider in _SEED_008_JOBS:
            conn.execute(
                text("INSERT INTO jobs (id, status, created_by, resolved_model, "
                     "resolved_provider) VALUES (:i, :s, :c, :m, :p)"),
                {"i": jid, "s": status, "c": created_by, "m": model, "p": provider},
            )
        for tid, status, chat_id, thread in _SEED_008_TASKS:
            conn.execute(
                text("INSERT INTO tasks (id, status, chat_id, thread_message_id) "
                     "VALUES (:i, :s, :c, :t)"),
                {"i": tid, "s": status, "c": chat_id, "t": thread},
            )
    try:
        yield engine
    finally:
        engine.dispose()


def _table_names(engine) -> set[str]:
    from sqlalchemy import inspect
    return set(inspect(engine).get_table_names())


def _columns(engine, table: str) -> dict:
    from sqlalchemy import inspect
    return {c["name"]: c for c in inspect(engine).get_columns(table)}


def test_008_is_additive_and_leaves_status_check_alone():
    src = _008_SRC.read_text()
    assert 'revision: str = "008"' in src
    assert 'down_revision: Union[str, None] = "007"' in src
    for col in P0_JOB_COLUMNS + P0_TASK_COLUMNS:
        assert f'"{col}"' in src, f"008 must add column {col}"
    assert 'op.create_table(\n        "notifications"' in src
    for col in P0_NOTIFICATION_COLUMNS:
        assert f'"{col}"' in src, f"notifications must carry column {col}"
    for col in FORBIDDEN_008_COLUMNS:
        assert f'"{col}"' not in src, f"008 must NOT add column {col}"
    # 007 already added these two: re-adding would raise DuplicateColumn on prod.
    for col in ("model_served", "terminal_reason"):
        assert f'sa.Column("{col}"' not in src, f"008 must not re-add 007's {col}"
    assert "ck_jobs_status_valid" not in src          # C16: status CHECK untouched
    assert "drop_constraint" not in src and "create_check_constraint" not in src
    upgrade_src = src.split("def upgrade")[1].split("def downgrade")[0]
    assert "drop_column" not in upgrade_src and "drop_table" not in upgrade_src
    for ix in ("ix_notifications_status", "ix_notifications_created_at",
               "ix_notifications_pending"):
        assert f'"{ix}"' in src, f"008 must create index {ix}"


def test_models_declare_every_008_column():
    from src.models import Job, Notification, Task
    job_cols = set(Job.__table__.columns.keys())
    task_cols = set(Task.__table__.columns.keys())
    notif_cols = set(Notification.__table__.columns.keys())
    assert set(P0_JOB_COLUMNS) <= job_cols
    assert not (set(FORBIDDEN_008_COLUMNS) & job_cols), \
        "priority/executor/sensitivity are not 008 columns"
    assert set(P0_TASK_COLUMNS) <= task_cols
    assert set(P0_NOTIFICATION_COLUMNS) == notif_cols
    assert Notification.__tablename__ == "notifications"
    for col in P0_JOB_COLUMNS:
        assert Job.__table__.columns[col].nullable, f"jobs.{col} must be nullable (additive)"
    for col in P0_TASK_COLUMNS:
        assert Task.__table__.columns[col].nullable, f"tasks.{col} must be nullable (additive)"
    # Widths the producers clip to (gateway.jobs.origin_from_created_by → 64).
    for table, name, length in (
        (Job, "cli_version", 24), (Job, "lane", 16), (Job, "origin_channel", 16),
        (Job, "origin_ref", 64), (Job, "origin_thread", 64), (Job, "task_class", 32),
        (Task, "origin_channel", 16), (Task, "origin_ref", 64), (Task, "origin_thread", 64),
        (Notification, "notice_kind", 32), (Notification, "status", 16),
    ):
        assert table.__table__.columns[name].type.length == length, f"{table.__name__}.{name}"
    for name in ("cost_usd_list", "sdk_cost_usd"):
        t = Job.__table__.columns[name].type
        assert (t.precision, t.scale) == (10, 4), name


@pytest.mark.skipif(
    sqlite3.sqlite_version_info < (3, 35),
    reason="downgrade uses native ALTER TABLE ... DROP COLUMN (SQLite >= 3.35)",
)
def test_008_round_trip_on_sqlite_skips_backfills(pre_008_engine):
    from sqlalchemy import text
    mod = _migration_module("008")
    assert "notifications" not in _table_names(pre_008_engine)
    assert not set(P0_JOB_COLUMNS) & set(_columns(pre_008_engine, "jobs"))
    assert "ck_jobs_status_valid" in _jobs_table_sql(pre_008_engine)

    _run_migration(pre_008_engine, mod.upgrade)

    jobs = _columns(pre_008_engine, "jobs")
    tasks = _columns(pre_008_engine, "tasks")
    assert set(P0_JOB_COLUMNS) <= set(jobs)
    assert set(P0_TASK_COLUMNS) <= set(tasks)
    for name in P0_JOB_COLUMNS:
        assert jobs[name]["nullable"] is True, name
    for name in P0_TASK_COLUMNS:
        assert tasks[name]["nullable"] is True, name
    assert "notifications" in _table_names(pre_008_engine)
    assert set(_columns(pre_008_engine, "notifications")) == set(P0_NOTIFICATION_COLUMNS)
    assert "ck_jobs_status_valid" in _jobs_table_sql(pre_008_engine)
    # The backfills are Postgres-only and were skipped: every new column stays NULL.
    with pre_008_engine.connect() as conn:
        touched = conn.execute(text(
            "SELECT count(*) FROM jobs WHERE origin_channel IS NOT NULL "
            "OR origin_ref IS NOT NULL OR input_tokens IS NOT NULL"
        )).scalar_one()
        task_touched = conn.execute(text(
            "SELECT count(*) FROM tasks WHERE origin_channel IS NOT NULL"
        )).scalar_one()
        # The outbox is writable in its migrated shape (server defaults apply).
        conn.execute(text(
            "INSERT INTO notifications (id, notice_kind, body) "
            "VALUES ('n-1', 'job_completed', 'hello')"
        ))
        row = conn.execute(text(
            "SELECT status, severity, channel, attempts, created_at IS NOT NULL "
            "FROM notifications WHERE id = 'n-1'"
        )).one()
        conn.commit()
    assert touched == 0 and task_touched == 0
    assert tuple(row) == ("pending", "info", "telegram", 0, 1)

    _run_migration(pre_008_engine, mod.downgrade)

    assert "notifications" not in _table_names(pre_008_engine)
    assert not set(P0_JOB_COLUMNS) & set(_columns(pre_008_engine, "jobs"))
    assert not set(P0_TASK_COLUMNS) & set(_columns(pre_008_engine, "tasks"))
    # The 007 columns and the 006 CHECK survive the round-trip untouched.
    assert _NEW_COLUMNS <= set(_columns(pre_008_engine, "jobs"))
    assert "ck_jobs_status_valid" in _jobs_table_sql(pre_008_engine)
    with pre_008_engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT id, status, created_by, resolved_model, resolved_provider "
            "FROM jobs ORDER BY id"
        )).all()
    assert sorted(tuple(r) for r in rows) == sorted(_SEED_008_JOBS)
    from sqlalchemy.exc import IntegrityError
    with pytest.raises(IntegrityError):
        with pre_008_engine.begin() as conn:
            conn.execute(text("INSERT INTO jobs (id, status) VALUES ('j-bad', 'succeeded')"))


def test_008_backfill_sql_is_dialect_guarded():
    """Every `op.execute` in upgrade() sits under `dialect.name == "postgresql"`.

    The backfills use `->`, `jsonb_typeof`, `~`, `split_part` and `::text` —
    none of which SQLite has — so an unguarded one would break the layer-1b
    harness AND any future SQLite consumer of the chain.
    """
    import ast
    tree = ast.parse(_008_SRC.read_text())
    upgrade = next(n for n in tree.body
                   if isinstance(n, ast.FunctionDef) and n.name == "upgrade")

    def _is_pg_guard(test: ast.expr) -> bool:
        return (isinstance(test, ast.Compare)
                and ast.unparse(test.left).endswith("dialect.name")
                and len(test.comparators) == 1
                and isinstance(test.comparators[0], ast.Constant)
                and test.comparators[0].value == "postgresql"
                and isinstance(test.ops[0], ast.Eq))

    guarded: set[int] = set()
    for node in ast.walk(upgrade):
        if isinstance(node, ast.If) and _is_pg_guard(node.test):
            for inner in ast.walk(node):
                if isinstance(inner, ast.Call) and ast.unparse(inner.func) == "op.execute":
                    guarded.add(inner.lineno)
    executes = [n.lineno for n in ast.walk(upgrade)
                if isinstance(n, ast.Call) and ast.unparse(n.func) == "op.execute"]
    assert len(executes) == 3, f"expected the three backfills, found op.execute at {executes}"
    unguarded = [ln for ln in executes if ln not in guarded]
    assert not unguarded, f"op.execute outside the postgresql guard at lines {unguarded}"


def test_008_origin_backfill_case_matches_origin_from_created_by():
    """The SQL CASE in 008 and the pure Python helper must agree branch for branch.

    The CASE cannot run on SQLite, so this drives `origin_from_created_by`
    over the created_by vocabulary and asserts the 008 source's CASE arms
    textually cover the same branches with the same NULLIF semantics.
    """
    from src.gateway.jobs import origin_from_created_by
    # Python side: the five branches of the vocabulary.
    assert origin_from_created_by("telegram:123") == ("telegram", "123")
    assert origin_from_created_by("telegram:") == ("telegram", None)
    assert origin_from_created_by("web") == ("web", None)
    assert origin_from_created_by("scheduler") == ("scheduler", None)
    for cb in ("dispatch-mcp", "event-trigger", "learning:x", "writeback:x",
               "escalation", "escalation:x", "plan:x", "evaluator:x", "eval-fix:x",
               "auto-continue:x", "bot-error-handler", "deploy-autopilot", "owner-dm"):
        assert origin_from_created_by(cb) == ("system", cb), cb
    assert origin_from_created_by("") == ("system", None)
    # SQL side: the same five arms, textually, in the origin backfill.
    src = _008_SRC.read_text()
    case = src.split("_BACKFILL_ORIGIN")[1].split("_BACKFILL_TASK_ORIGIN")[0]
    assert "WHEN created_by LIKE 'telegram:%' THEN 'telegram'" in case
    assert "WHEN created_by = 'web'" in case and "THEN 'web'" in case
    assert "WHEN created_by = 'scheduler'" in case and "THEN 'scheduler'" in case
    assert "ELSE 'system'" in case
    # The telegram and system ref arms are NULLIF'd and clipped to the
    # String(64) column; web/scheduler get an explicit NULL ref BEFORE the
    # ELSE (whole-tier review 2026-10-22: the ELSE alone stamped the literal
    # `web`/`scheduler` as origin_ref, unlike the helper and A2's stamps).
    assert "NULLIF(LEFT(split_part(created_by, ':', 2), 64), '')" in case
    web_null = "WHEN created_by IN ('web', 'scheduler') THEN NULL"
    else_arm = "ELSE NULLIF(LEFT(created_by, 64), '')"
    assert web_null in case and else_arm in case
    assert case.index(web_null) < case.index(else_arm)
    assert "WHERE origin_channel IS NULL" in case     # idempotent: never rewrites a stamped row
    assert "WHERE origin_channel IS NULL AND chat_id IS NOT NULL" in src   # task arm


# ── Layer 1c: applied history vs disk (no DB) — spec §9 rollback rule ──────
#
# `alembic_version` on prod is one row no pure test can see; a `git revert`
# that deletes a HEAD migration file leaves the on-disk chain perfectly
# walkable (head silently becomes the previous id) — exactly the state that
# breaks the next `alembic upgrade head`. `alembic/applied_history.txt` is the
# append-only list of revisions that have been applied; these tests make a
# deleted migration file fail the pytest gate in `server-deploy` instead of
# failing mid-incident. Removing a line is legal only after
# `alembic downgrade -1` ran on prod (re-cut plan §4 rollback rule).

HISTORY = REPO / "alembic" / "applied_history.txt"


def _applied_history() -> list[str]:
    return [ln.strip() for ln in HISTORY.read_text().splitlines()
            if ln.strip() and not ln.lstrip().startswith("#")]


def _disk_chain() -> list[str]:
    """base → head by following down_revision from the single head."""
    from alembic.script import ScriptDirectory
    script = ScriptDirectory.from_config(_alembic_config())
    rev = script.get_revision(script.get_current_head())
    chain: list[str] = []
    while rev is not None:
        chain.append(rev.revision)
        rev = script.get_revision(rev.down_revision) if rev.down_revision else None
    return chain[::-1]


def test_every_revision_in_applied_history_exists_on_disk():
    on_disk = set(_disk_chain())
    missing = [r for r in _applied_history() if r not in on_disk]
    assert not missing, (
        f"applied revisions with no script on disk: {missing} — a revert deleted a migration "
        f"file; run `alembic downgrade -1` on prod BEFORE removing it (spec §9 rollback rule)")


def test_applied_history_matches_disk_chain():
    assert _applied_history() == _disk_chain(), (
        "alembic/applied_history.txt must list exactly the on-disk chain base→head: append "
        "the new id in the same commit as a migration; remove one only after downgrade -1")


def test_applied_history_ends_at_current_head():
    from alembic.script import ScriptDirectory
    script = ScriptDirectory.from_config(_alembic_config())
    history = _applied_history()
    assert history[-1] == script.get_current_head() == "008"
    assert history == ["001", "002", "003", "004", "005", "006", "007", "008"]
