# DB / models module

**Paths:** `src/db.py`, `src/models.py`, `src/config.py`, `src/audit_log.py`, `alembic/`

## Purpose

Persistence layer. SQLAlchemy async engine, Redis client, ORM models, and the
JSONL audit log on disk.

## Schema (6 tables)

- `jobs` — one unit of work. Includes `resolved_skill`, `resolved_model`,
  `resolved_effort`, `user_rating`, `review_outcome`, `parent_job_id`,
  `task_id` for the auto-tuning loop and multi-turn interaction. Since
  migration 007 (2026-10-21) also `resolved_provider` ("anthropic" |
  "codex"), `terminal_reason` (executor outcome) and `model_served` (the id
  the provider reports back) — all nullable; pre-007 rows carry
  `resolved_provider='anthropic'` only where `resolved_model` is a
  `claude-*` id.
- `schedules` — cron recipes that enqueue jobs.
- `projects` — registry of hosted projects.
- `proposals` — tuning/doc proposals emitted by `review-and-improve`.
- `tasks` — multi-turn conversation wrappers. Groups related jobs. Status:
  active → awaiting_user → pending_approval → completed. Persists `chat_id`
  for Telegram DM delivery across bot restarts. `thread_message_id` stores
  the Telegram message ID of the bot's root reply for thread-based interaction.
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
- `KEY_QUOTA_PAUSED_UNTIL = "quota:paused_until"` / `KEY_QUOTA_LAST_REASON = "quota:last_reason"` — the GLOBAL (= Anthropic) pause pair (INV-12)
- `KEY_QUOTA_PROVIDER_PREFIX = "quota:provider:"` → `quota:provider:<p>:paused_until` / `:last_reason` — one pair per non-Anthropic provider lane (T6, 2026-10-21); never written for `anthropic`

## Audit log

JSONL files at `volumes/audit_log/<job_id>.jsonl`. Append-only. Event kinds:
`job_started`, `text`, `tool_use`, `tool_result`, `thinking`, `job_completed`,
`job_failed`, `job_cancelled`, `job_requeued_for_quota`, `job_held` (T6), `note`;
the cross-vendor writer slice (2026-10-21) added `provider_selected`,
`provider_refused` (T1/T4), `executor_started`, `turn_completed`,
`executor_error` (T3), `merge_gate_verdict`, `merge_gate_skipped`,
`merge_gate_refused`, `workspace_published` (T5) and additive fields on
`job_started`/`job_completed` (`provider`, …), `tool_result` (`exit_code`,
`output`), `workspace_created` (`base_sha`), `post_review_skipped`
(`pre_push_gate`), `job_requeued_for_quota` (`provider`, `until`). Kinds are
a parsing contract (C14): add, never rename or reshape. The full list with
field shapes is the `src/audit_log.py` docstring.

Plus `volumes/audit_log/<job_id>.summary.md` — human-readable one-paragraph
summary, written at job completion (the final text message from Claude).

## Migrations

Migrations under `alembic/versions/`. Never edit existing ones — new file per change.

- `001_initial.py` — Phase 1. Creates `jobs`, `schedules`, `projects`.
- `002_proposals_table.py` — Rec 10 (2026-04-18). Creates `proposals` with
  a partial index on `(target_file, change_type) WHERE outcome IN
  ('pending','rejected')` for the dedup query.
- `003_tasks_table.py` — 2026-04-20. Creates `tasks` and `task_turns` tables;
  adds `task_id` FK column to `jobs`.
- `004_task_thread_message_id.py` — 2026-04-20. Adds `thread_message_id`
  (BigInteger) to `tasks` for Telegram thread-based interaction.
- `005_task_plan.py` — 2026-07-12. Adds `plan` (JSON) to `tasks`.
- `006_job_status_constraint.py` — 2026-08-31. Repairs illegal statuses and
  adds the `ck_jobs_status_valid` CHECK on `jobs.status`.
- `007_provider_columns.py` — 2026-10-21. Adds nullable `resolved_provider`,
  `terminal_reason`, `model_served` to `jobs`; backfills
  `resolved_provider='anthropic'` for `claude-*` rows. Round-tripped on
  SQLite in `tests/test_migrations.py` (layer 1b).

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
