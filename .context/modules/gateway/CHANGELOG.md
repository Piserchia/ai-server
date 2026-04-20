# Changelog: gateway

<!-- Newest entries at top. Every session that modifies this module appends here. -->

## 2026-04-20 — Documentation cleanup: updated CONTEXT.md

**Files changed**:
- `.context/modules/gateway/CONTEXT.md` — Updated public interface to include
  `/api/retrospective/context`, `/api/jobs/{id}/stream`, `/api/projects/public`
  routes. Added `/proposals` and `/schedule` to Telegram commands list.
  Removed stale Phase 2 references from Testing and Gotchas sections.

**Why**: CONTEXT.md was out of date — missing routes and commands added
in Phases 5-6 and evaluation recs.

**Side effects**: None.

## 2026-04-19 — Added GET /api/retrospective/context route (Rec 2)

**Files changed**:
- `src/gateway/web.py` — New `GET /api/retrospective/context?since=YYYY-MM-DD`
  route returning JSON array of context consumption data per (skill, file_path).
  Computes `read_rate` from `read_count / total_skill_jobs`. Auth-gated.

**Why**: Exposes the context consumption rollup (Rec 2) to the dashboard
and to skills like review-and-improve that consume it via HTTP.

**Side effects**: None; additive route only.

## 2026-04-18 — Added /proposals Telegram command (Rec 10)

**Files changed**:
- `src/gateway/telegram_bot.py` — new `cmd_proposals` handler with three
  modes: no-arg lists pending; `Nd` (e.g. `/proposals 30d`) lists all
  proposals from last N days; `<id_prefix>` shows details for one proposal.
  Registered via `CommandHandler("proposals", cmd_proposals)`. Added to
  `/help` text and module docstring command list.

**Why**: Users need visibility into what `review-and-improve` has proposed
and what's happened to those proposals. Per Rec 10, proposals are now
tracked in a DB table; the command is the Telegram-side window into it.

**Side effects**: None on existing commands. New command imports
`src.runner.proposals` lazily inside the handler so module load stays fast.

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
