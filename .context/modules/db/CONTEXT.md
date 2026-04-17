# DB / models module

**Paths:** `src/db.py`, `src/models.py`, `src/config.py`, `src/audit_log.py`, `alembic/`

## Purpose

Persistence layer. SQLAlchemy async engine, Redis client, ORM models, and the
JSONL audit log on disk.

## Schema (3 tables)

- `jobs` — one unit of work. Includes `resolved_skill`, `resolved_model`,
  `resolved_effort`, `user_rating`, `review_outcome`, `parent_job_id` for
  the auto-tuning loop.
- `schedules` — cron recipes that enqueue jobs.
- `projects` — registry of hosted projects.

See `src/models.py` for the authoritative schema. No foreign tables, no
pgvector, no DuckDB.

## Redis channel constants

Defined as named constants in `src/db.py`, not inline strings:
- `QUEUE_JOBS = "jobs:queue"`
- `CHANNEL_JOB_STREAM = "jobs:stream"` → per-job: `"jobs:stream:<id>"`
- `CHANNEL_JOB_DONE = "jobs:done"` → per-job: `"jobs:done:<id>"`
- `CHANNEL_JOB_CANCEL = "jobs:cancel"`

## Audit log

JSONL files at `volumes/audit_log/<job_id>.jsonl`. Append-only. Event kinds:
`job_started`, `text`, `tool_use`, `tool_result`, `thinking`, `job_completed`,
`job_failed`, `job_cancelled`, `job_requeued_for_quota`, `note`.

Plus `volumes/audit_log/<job_id>.summary.md` — human-readable one-paragraph
summary, written at job completion (the final text message from Claude).

## Migrations

One migration in Phase 1: `alembic/versions/001_initial.py`. Every schema
change: new migration file, never edit existing ones.

To add a migration after editing `src/models.py`:
```bash
pipenv run alembic revision --autogenerate -m "<description>"
pipenv run alembic upgrade head
```

## Configuration

All settings live in `src/config.py` as a pydantic `Settings` class. Read
from `.env` → env vars → defaults. Never log `settings.model_dump()` — contains secrets.

## Gotchas

- `asyncpg` doesn't like SERIAL/auto-increment UUID generation; we explicitly
  set `default=uuid.uuid4` on the Python side.
- SQLAlchemy 2.0 requires `Mapped[...]` type annotations on columns.
- The `jobs.parent_job_id` self-FK requires `op.create_foreign_key` after the
  table is created (not inline in `create_table`).
- Don't add new tables for things that fit in `payload` or `result` JSONB.
  Phase 1 explicitly doesn't have `tool_invocations`, `llm_calls`,
  `model_escalation_state`, etc. from the old system. Prove the need first.
