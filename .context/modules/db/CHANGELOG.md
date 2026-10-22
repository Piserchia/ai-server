# Changelog: db / models

<!-- Newest entries at top. Every session that modifies this module appends here. -->

## 2026-10-21 — A3: `KEY_QUOTA_LAST_SOURCE` beside the global quota pair

**Agent task**: Observability Phase 1 re-cut plan A3 (`docs/superpowers/plans/2026-10-21-observability-phase1-recut.md` §6).
**Files changed**:
- `src/db.py` — `KEY_QUOTA_LAST_SOURCE = "quota:last_source"`: `"vendor"` when the global (Anthropic) pause's reset time came from a `RateLimitEvent`, else `"estimated"`. Written by `quota.pause_queue`, read by `quota.last_source`, deleted with the pair (`clear`, auto-resume, corrupt value). Never written for a per-provider lane.
- `.context/modules/db/CONTEXT.md` (Redis keys list).

**Why**: the label is state the bot reads out-of-process, so it lives next to `quota:paused_until` / `quota:last_reason` under the same contract.

**Side effects**: none for existing readers; one more key under the `quota:` namespace.

**Gotchas discovered**: none.

## 2026-10-21 — A1: migration 008 (Observability Phase 1 columns, task origin, notifications outbox) + alembic applied-history manifest

**Agent task**: Observability Phase 1 re-cut plan A1 (`docs/superpowers/plans/2026-10-21-observability-phase1-recut.md` §6; design of record P0 plan Task 1 + Task 18(a), re-cut against the slice's 007).
**Files changed**:
- `alembic/versions/008_p0_observability.py` (new) — revision `008` revising `007`. 17 nullable `jobs` columns (`cli_version`, `lane`, `origin_channel`, `origin_ref`, `origin_thread`, `queue_wait_ms`, `first_event_at`, `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_write_1h_tokens`, `cache_write_5m_tokens`, `num_turns`, `duration_api_ms`, `cost_usd_list`, `sdk_cost_usd`, `task_class`), 4 nullable `tasks` columns (`origin_channel`, `origin_ref`, `origin_thread`, `awaiting_since`), table `notifications` (17 columns) with `ix_notifications_status`, `ix_notifications_created_at` and the partial `ix_notifications_pending`. Three backfills (tokens from `result->'usage'`, job origin from `created_by`, task origin from `chat_id`/`thread_message_id`) run only under `if op.get_bind().dialect.name == "postgresql":`.
- `alembic/applied_history.txt` (new) — append-only manifest `001` … `008`, one revision id per line.
- `src/models.py` — `Numeric` import; the 17 `Job` columns after `review_outcome`; the 4 `Task` columns before `created_at`; `class Notification` after `TaskTurn`; docstring `Six tables` → `Seven`, `tokens_used` → `input_tokens/output_tokens`.
- `tests/test_migrations.py` — `test_chain_head_is_007_revising_006` retargeted to `test_head_is_008_revising_007` (via `get_current_head()`); chain floor `>= 5` → `>= 8`; `pre_008_engine` fixture (jobs with the 007 columns + `created_by`/`result`, tasks with `chat_id`/`thread_message_id`, the 006 CHECK); layer 1b-008: `test_008_is_additive_and_leaves_status_check_alone`, `test_models_declare_every_008_column`, `test_008_round_trip_on_sqlite_skips_backfills`, `test_008_backfill_sql_is_dialect_guarded` (AST: every `op.execute` in `upgrade()` sits under the postgresql guard, exactly three), `test_008_origin_backfill_case_matches_origin_from_created_by`; layer 1c: `test_every_revision_in_applied_history_exists_on_disk`, `test_applied_history_matches_disk_chain`, `test_applied_history_ends_at_current_head`.
- `.context/modules/db/CONTEXT.md` — schema 6 → 7 tables, the 008 columns on `jobs`/`tasks`, the `notifications` row, migration list + the manifest rule; `.context/SYSTEM.md` — migrations line (eight files, `notifications` table, manifest rule).

**Why**: columns first so every later Phase-1 task (A2 origin stamps, A4–A6 outbox, B3 result capture) is a small write. 008, not 007: the slice's `007_provider_columns.py` already holds `resolved_provider`/`terminal_reason`/`model_served`, so 008 does NOT re-add them (`op.add_column` would raise `DuplicateColumn` on prod) and the P0 plan's "`resolved_provider` absent" assertion is dropped — the column exists with a backfill and stays. The manifest is born in the same commit as 008 so the layer-1c gate never goes red twice.

**Side effects**: `jobs.status` and its 006 CHECK untouched (done-ness and the terminal reason are columns). `lane`/`task_class`/`first_event_at` stay NULL until Phase 3. Both cost columns, `num_turns` and `duration_api_ms` stay NULL on pre-008 rows (session.py never kept them in `result`; inventing a figure from tokens would put an unaudited number in the column B4's reconcile checks). Codex rows have flat usage and no nested `cache_creation` bucket → 1h/5m NULL, correct. `notifications.actions` is `JSONB().with_variant(JSON(), "sqlite")` and `created_at` defaults to `sa.func.now()` (→ `now()` on Postgres, `CURRENT_TIMESTAMP` on SQLite) so the SQLite layer-1b harness round-trips the DDL. Rollback rule (re-cut plan §4): revert application code by path, never this file; `alembic downgrade -1` on prod BEFORE removing it, and drop its manifest line in the same commit. Nothing writes the new columns yet (A2/B3 stamp them); the ORM `Notification` has no reader until A4.

**Gotchas discovered**: `jobs.result` is JSONB in the DB (001) although models.py declares `JSON` — `->>` works either way; the token backfill guards every value with a digit regex so one odd row cannot fail the migration. On SQLAlchemy 2.0 `sqlalchemy.dialects.postgresql.UUID` IS `sqltypes.UUID`, so the migration's `UUID(as_uuid=True)` compiles on SQLite (CHAR(32)) — no variant needed. `test_migrations_apply_cleanly` (opt-in, throwaway Postgres DB) passed against 008.

## 2026-10-21 — Whole-branch review: `audit_log.py` docstring (additive kinds/fields)

**Agent task**: cross-reference for the runner CHANGELOG entry of the same date (`src/audit_log.py` is the shape of record for audit kinds).
**Files changed**: `src/audit_log.py` (docstring only) — `merge_gate_refused` gains reasons `unparseable_path` (+`lines`) and `diff_too_large` (+`max_chars`); new kind `executor_slot_wait{executor, waited_s, concurrency}`. No kind renamed or reshaped (C14); `.context/modules/db/CONTEXT.md` kind list updated.

## 2026-10-21 — T9: docs, registries, runbook (no code change)

**Agent task**: cross-vendor writer slice T9 (`docs/superpowers/plans/2026-10-21-cross-vendor-writer-slice.md` §5). No file under
`src/` changed.
- `.context/modules/db/CONTEXT.md` § Audit log — lists the kinds the slice
  added (`provider_selected`, `provider_refused`, `executor_started`,
  `turn_completed`, `executor_error`, `merge_gate_verdict`,
  `merge_gate_skipped`, `merge_gate_refused`, `workspace_published`) and the
  additive fields on existing kinds, with the C14 rule (add, never rename or
  reshape); `src/audit_log.py`'s docstring remains the shape of record and
  `tests/test_cross_vendor_docs.py` checks the two agree on those names.

## 2026-10-21 — T6: quota key constants

**Agent task**: cross-vendor writer slice T6. **Files changed**:
- `src/db.py` — `KEY_QUOTA_PAUSED_UNTIL = "quota:paused_until"` and
  `KEY_QUOTA_LAST_REASON = "quota:last_reason"` (the GLOBAL = Anthropic
  pair `runner.quota` had inlined; same strings, INV-12 unchanged) and
  `KEY_QUOTA_PROVIDER_PREFIX = "quota:provider:"` (+ `<p>:paused_until` /
  `<p>:last_reason` — one pair per non-Anthropic provider, never written
  for `anthropic`). No schema change.

## 2026-10-21 — T2: migration 007-lite, provider columns on jobs

**Agent task**: cross-vendor writer slice T2
(`docs/superpowers/plans/2026-10-21-cross-vendor-writer-slice.md` §5).
**Files changed**:
- `alembic/versions/007_provider_columns.py` (new, revises 006) — additive,
  nullable: `jobs.resolved_provider` String(32), `jobs.terminal_reason`
  String(32), `jobs.model_served` String(64). Backfill
  `resolved_provider='anthropic' WHERE resolved_model LIKE 'claude-%'`;
  every other row stays NULL (C12: never a default). `jobs.status` and its
  006 CHECK are not touched. Downgrade drops the three columns.
- `src/models.py` — the same three columns on `Job`, all nullable. Nothing
  writes them yet: T4 stamps `resolved_provider` / `terminal_reason` /
  `model_served` from the dispatch branch; T7 surfaces them.
- `tests/test_migrations.py` — new SQLite layer (1b): the 007 module is
  loaded via `ScriptDirectory` and run under `Operations.context` on an
  in-memory sync SQLite engine (env.py is async-Postgres only; no aiosqlite),
  against a pre-007 `jobs` fixture carrying the 006 CHECK. Asserts head =
  007 revising 006, the ORM widths, backfill (claude-* → anthropic, codex /
  NULL untouched), reflected types == ORM, upgrade → downgrade round-trip
  with the CHECK still enforcing, and that the 007 source never names
  `ck_jobs_status_valid`.

**Why**: the executor dispatch (T4) and quota keys (T6) need a per-job
provider of record and a typed terminal reason; "-lite" because the old
spec's 007 (cost / cache-tier / origin observability columns) stays with
Observability Phase 1.

**How to verify**: `pipenv run pytest -q -p no:cacheprovider
tests/test_migrations.py`; on deploy `alembic upgrade head` then
`psql assistant -c "\\d jobs"` shows the three columns.


## 2026-07-31 — Event-loop circuit breaker key/TTL constants

**Files changed**: `src/db.py` — `KEY_EVENTS_BREAKER = "events:breaker"` and
`TTL_EVENTS_BREAKER = 1800` added beside the runner-heartbeat constants. Set
by the runner's event loop when >= 5 failures in 10 min share one normalized
error signature (key value = the signature); while present, event-trigger
spawning is paused (idle-queue review exempt). 30-min TTL auto-resets the
breaker. See runner CHANGELOG 2026-07-31 for the incident and semantics.


## 2026-07-31 — Runner heartbeat TTL constant

**Files changed**: `src/db.py` — `TTL_RUNNER_HEARTBEAT = 900` added beside
`KEY_RUNNER_HEARTBEAT`; that key's comment corrected (value is epoch seconds,
not ISO — the runner now writes `SET ... EX` so a dead runner's key expires
instead of lingering stale). Part of the runner-liveness work (see runner
CHANGELOG 2026-07-31).

## 2026-07-12 — P2: tasks.plan column + deferred job status

**Files changed**:
- `src/models.py` — `Task.plan` (JSON, nullable): the structured plan from the
  `plan` skill. `JobStatus.deferred`: a job waiting on `payload.depends_on`
  job ids; promoted to `queued` by `runner.plans.promote_deferred_for` (no
  Redis entry until promotion).
- `alembic/versions/005_task_plan.py` — migration for `tasks.plan`.

**Why**: plans and their dependency DAGs need first-class storage; deferred
status lets the queue express "after that one".

**How to verify**: `pipenv run alembic upgrade head`; then
`psql assistant -c "\\d tasks"` shows the `plan` column.

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
