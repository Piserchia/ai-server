# DB / models module

**Paths:** `src/db.py`, `src/models.py`, `src/config.py`, `src/audit_log.py`, `alembic/`

## Purpose

Persistence layer. SQLAlchemy async engine, Redis client, ORM models, and the
JSONL audit log on disk.

## Schema (6 tables)

- `jobs` — one unit of work. Includes `resolved_skill`, `resolved_model`,
  `resolved_effort`, `user_rating`, `review_outcome`, `parent_job_id`,
  `task_id` for the auto-tuning loop and multi-turn interaction.
- `schedules` — cron recipes that enqueue jobs.
- `projects` — registry of hosted projects.
- `proposals` — tuning/doc proposals emitted by `review-and-improve`.
- `tasks` — multi-turn conversation wrappers. Groups related jobs. Status:
  active → awaiting_user → pending_approval → completed. Persists `chat_id`
  for Telegram DM delivery across bot restarts.
- `task_turns` — individual turns in a task conversation. role: user |
  assistant | system. Links to job_id for assistant turns.
  Fields: `id`, `proposed_by_job_id` (FK→jobs, CASCADE), `target_file`,
  `change_type` ('default-model'|'context-files'|'frontmatter-tweak'|'doc-update'),
  `rationale`, `proposed_at`, `applied_pr_url`, `applied_at`, `outcome`
  ('pending'|'merged'|'rejected'|'superseded'). Partial index on
  `(target_file, change_type) WHERE outcome IN ('pending','rejected')`
  for fast dedup. See § 7 Rec 10 in `docs/EVALUATION_2026-04-18.md`.

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

Migrations under `alembic/versions/`. Never edit existing ones — new file per change.

- `001_initial.py` — Phase 1. Creates `jobs`, `schedules`, `projects`.
- `002_proposals_table.py` — Rec 10 (2026-04-18). Creates `proposals` with
  a partial index on `(target_file, change_type) WHERE outcome IN
  ('pending','rejected')` for the dedup query.

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
