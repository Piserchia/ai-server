# Changelog: db / models

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
