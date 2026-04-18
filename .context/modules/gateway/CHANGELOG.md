# Changelog: gateway

<!-- Newest entries at top. Every session that modifies this module appends here. -->

## 2026-04-18 — Seeded skills/ subdirectory per Rec 3 (§ 7 Seed module skills/ dirs)

**Change**: This module now has `.context/modules/gateway/skills/` containing stub `GOTCHAS.md`, `PATTERNS.md`, and `DEBUG.md` files. Stubs were created via `scripts/seed-module-skills.sh`; no source code modified.

**Why**: PROTOCOL.md directs sessions to append learnings to these files, but four of five modules had no skills/ directory at all, discouraging write-backs. Creating the directories with format-header stubs removes the friction and gives future sessions a template to append to. See `docs/EVALUATION_2026-04-18.md` § 7 Rec 3.

**Side effects**: None on module behavior. New lint check `check_module_skills_dirs` in `scripts/lint_docs.py` verifies these files continue to exist.


## 2026-04-17 — Public landing page + projects API

**Files changed**:
- `src/gateway/web.py` — Added `/api/projects/public` (no-auth endpoint returning project list for the landing page). Extracted shared `_get_projects()` helper used by both the auth'd and public endpoints.

**Why**: The public landing page at `chrispiserchia.com` needs to fetch project data without an auth token.

## 2026-04-16 — Initial bootstrap (Phase 1)

**Agent task**: Create the three gateway processes from scratch.

**Files created**:
- `src/gateway/jobs.py` — shared enqueue/cancel/find helpers
- `src/gateway/web.py` — FastAPI with 8 routes + HTMX dashboard
- `src/gateway/telegram_bot.py` — 9-command bot + done-listener + quota notifier

**Why**: Three submission pathways (Telegram, web form, programmatic API) with
one consistent backend.

**Side effects**: None — new module.

**Gotchas discovered**:
- Telegram's `Update` type collides with SQLAlchemy's `update` function. Import
  the latter as `sql_update` in telegram_bot.py.
- `_job_to_chat` dict is in-process; on bot restart any pending jobs lose their
  DM destination. Acceptable for now; users can `/status` to check.
- Dashboard renders JSON responses client-side for simplicity. Works but is ugly
  on slow connections; consider server-side rendering in Phase 2.
