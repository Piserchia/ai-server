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

## 2026-10-09 — Can't derive team W/L from pool-selected games

When building charts that group by team performance attributes (e.g., "games vs losing teams"), the schema may lack those attributes directly. The `games` table contains only pool-selected games, so deriving W/L records from game scores would be dishonest — you'd be computing statistics from a biased subset.

When a requested grouping category is unbuildable due to schema gaps, do NOT fake the data. Instead: create a named leftover bucket (e.g., "same conference, other division") that accounts for all remaining rows, and verify the sum matches the known total (e.g., total correct picks). Document the limitation clearly in the chart description.

_Evidence: job `1995598b`_

## 2026-10-09 — Double-counting in 'either team' category breakdowns without deduplication

When breaking down sports analytics by team attributes (division, conference, league) and counting records 'if either team is from that category', intra-category games get counted twice without explicit deduplication. Naive grouping after joining picks to both home_team and away_team divisions produces double-counts: a divisional game with CORRECT result appears twice in that division's totals (once via home team, once via away team). Fix: use DISTINCT (game_id, category_attribute) in the result grouping or subquery. Example from NFL pick'em: 65C/46I total across 8 divisions, but only 39C/26I when single-counted = 17 intra-division games being double-counted.

_Evidence: job `51f4dcc7`_

## 2026-04-20 — `sqlalchemy.update` name collision with Telegram's `Update`

**Symptom**: `ImportError` or unexpected behavior when both SQLAlchemy and python-telegram-bot needed.

**Fix**: Import SQLAlchemy's update as `sql_update`: `from sqlalchemy import update as sql_update`. This convention is used codebase-wide.

## 2026-04-20 — Never edit existing Alembic migrations

Always add a new migration. Current: `001_initial.py`, `002_proposals_table.py`.

**Why**: Alembic tracks applied migrations by revision ID. Editing a migration that's already been applied causes schema drift. Use `op.execute()` with raw SQL for partial indexes.
