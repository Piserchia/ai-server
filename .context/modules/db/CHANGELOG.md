# Changelog: db / models

<!-- Newest entries at top. Every session that modifies this module appends here. -->

## 2026-07-06 — Runner heartbeat key + health staleness setting

**Files changed**:
- `src/db.py` — new Redis key constant `KEY_RUNNER_HEARTBEAT = "heartbeat:runner"`
  (runner SETs it each loop; `/health` reads it). No schema/migration change.
- `src/config.py` — new setting `runner_heartbeat_stale_seconds` (default 90):
  `/health` returns 503 if the heartbeat is older than this.

**Why**: Supports the external dead-man's-switch (A3). Redis key names live in one
place per the "don't inline channel strings" convention.

**Side effects**: None — additive constant + setting with a safe default.

## 2026-04-20 — Add thread_message_id to tasks table

**Files changed**: `src/models.py`, `alembic/versions/004_task_thread_message_id.py`
**Why**: Telegram threads need a message ID to reply in the correct thread.

## 2026-04-20 — Fix Task.chat_id BigInteger type

**Files changed**: `src/models.py` — Changed `Task.chat_id` from default
`Integer` to explicit `BigInteger`. Telegram chat IDs exceed int32 range.

**Why**: `asyncpg.DataError: value out of int32 range` on task creation.

## 2026-04-20 — Added tasks + task_turns tables for multi-turn interaction

**Files changed**:
- `alembic/versions/003_tasks_table.py` (NEW) — Creates `tasks` and
  `task_turns` tables, adds `task_id` FK column to `jobs`.
- `src/models.py` — Added `Task`, `TaskTurn`, `TaskStatus` models.
  Added `task_id` field to `Job`. Updated docstring (6 tables).

**Why**: Jobs were fire-and-forget. Users couldn't reply to a task's
output or approve completion. Tasks wrap related jobs into a conversation
with turn-by-turn context.

**Side effects**: Existing jobs have `task_id = NULL` (unaffected).
New `/task` commands create a Task automatically.

## 2026-04-18 — Added `proposals` table + Proposal model (Rec 10)

**Files changed**:
- `alembic/versions/002_proposals_table.py` (NEW) — creates `proposals` with
  columns id/proposed_by_job_id(FK→jobs CASCADE)/target_file/change_type/
  rationale/proposed_at/applied_pr_url/applied_at/outcome. Partial index
  `ix_proposals_dedup` on `(target_file, change_type) WHERE outcome IN
  ('pending','rejected')`. Secondary index on `proposed_at`.
- `src/models.py` — added `ProposalChangeType` enum (default-model,
  context-files, frontmatter-tweak, doc-update), `ProposalOutcome` enum
  (pending, merged, rejected, superseded with `is_terminal` property),
  `Proposal` ORM class with relationship to parent Job.

**Why**: Closes the loop on retrospective proposals per
`docs/EVALUATION_2026-04-18.md` § 7 Rec 10. Without this table,
`review-and-improve` could propose the same change month after month
because the PR got ignored ("proposal zombies"). Now each proposal has
tracked state so dedup + fate tracking both work.

**Side effects**: Schema goes from 3 tables to 4. Existing code unaffected.

**Gotchas discovered**: Partial indexes in Alembic are easiest via
`op.execute(...)` with raw SQL — keeps the predicate readable in one place.

## 2026-04-18 — Seeded skills/ subdirectory per Rec 3 (§ 7 Seed module skills/ dirs)

**Change**: This module now has `.context/modules/db/skills/` containing stub `GOTCHAS.md`, `PATTERNS.md`, and `DEBUG.md` files. Stubs were created via `scripts/seed-module-skills.sh`; no source code modified.

**Why**: PROTOCOL.md directs sessions to append learnings to these files, but four of five modules had no skills/ directory at all, discouraging write-backs. Creating the directories with format-header stubs removes the friction and gives future sessions a template to append to. See `docs/EVALUATION_2026-04-18.md` § 7 Rec 3.

**Side effects**: None on module behavior. New lint check `check_module_skills_dirs` in `scripts/lint_docs.py` verifies these files continue to exist.


## 2026-04-16 — Initial bootstrap (Phase 1)

**Agent task**: Create the persistence layer from scratch.

**Files created**:
- `src/config.py` — pydantic Settings, subscription auth only, no API key field
- `src/db.py` — async engine, Redis client, channel/queue constants
- `src/models.py` — 3 ORM models (Job, Schedule, Project) with auto-tuning columns
- `src/audit_log.py` — JSONL append-only per-job event log
- `alembic/env.py`, `alembic/versions/001_initial.py` — initial schema migration

**Why**: Minimal state surface. 3 tables vs the old system's 17. Audit trail
lives on disk (grep-friendly, append-only by construction) rather than in a
DuckDB analytics replica.

**Side effects**: None — new module.

**Gotchas discovered**:
- The `jobs.parent_job_id` self-referencing FK can't be declared inside
  `create_table`; it needs `op.create_foreign_key` in the migration body.
- Composite index `ix_jobs_autotune` on `(resolved_skill, resolved_model,
  resolved_effort, status)` supports the `review-and-improve` monthly query.
