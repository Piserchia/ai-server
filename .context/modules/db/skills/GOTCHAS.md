# Gotchas

> **What this file is for**: Non-obvious traps, unexpected behaviors, and things that look like they should work but don't.
>
> **When to add an entry here**: When a session hit a trap — something implicit, an ordering requirement, a race condition, an environment-specific behavior — that a future session should know about before making similar changes.
>
> Append entries newest-first. Each entry should include a date header,
> the symptom or pattern, the fix or approach, and (when possible) a
> reference to the audit log that led to the finding.
>
> This file is seeded empty. Claude sessions working in this module should
> append here when they learn something reusable (see `.context/PROTOCOL.md`).

<!-- Append entries below this marker. Do not delete the marker. -->
<!-- APPEND_ENTRIES_BELOW -->

## 2026-04-20 — `sqlalchemy.update` name collision with Telegram's `Update`

**Symptom**: `ImportError` or unexpected behavior when both SQLAlchemy and python-telegram-bot needed.

**Fix**: Import SQLAlchemy's update as `sql_update`: `from sqlalchemy import update as sql_update`. This convention is used codebase-wide.

## 2026-04-20 — Never edit existing Alembic migrations

Always add a new migration. Current: `001_initial.py`, `002_proposals_table.py`.

**Why**: Alembic tracks applied migrations by revision ID. Editing a migration that's already been applied causes schema drift. Use `op.execute()` with raw SQL for partial indexes.
