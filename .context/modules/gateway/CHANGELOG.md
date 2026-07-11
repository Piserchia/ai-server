# Changelog: gateway

<!-- Newest entries at top. Every session that modifies this module appends here. -->

## 2026-07-11 — T8: model tier map — alias map and web dropdown use settings tiers

**Files changed**:
- `src/gateway/telegram_bot.py` — `_MODEL_ALIASES`: `"opus"` now resolves to `settings.model_deep`, `"sonnet"` to `settings.default_model`, `"haiku"` to `settings.model_fast`. Explicit versioned aliases (`opus-4-7`, `haiku-4-5`, etc.) kept as literal strings for backward compatibility.
- `src/gateway/web.py` — Dashboard model dropdown now injects `settings.default_model`, `settings.model_deep`, `settings.model_fast` via `.replace()` substitution in the `index()` handler. Display labels updated to "sonnet (default)", "opus (deep)", "haiku (fast)".

**Why**: T8 eval remediation — model strings centralised in `src/config.py` so a generation bump in one place propagates everywhere.

## 2026-07-06 — Meaningful /health for external dead-man's-switch

**Files changed**:
- `src/gateway/web.py` — `/health` now reads the runner heartbeat + queue depth from
  Redis and pings Postgres; returns **503** (not 200) when the runner heartbeat is
  stale or DB/Redis is unreachable, with a JSON body `{status, runner_ok,
  runner_heartbeat_age_s, queue_depth, db_ok, redis_ok}`. Extracted pure helper
  `health_verdict()`.
- `tests/test_health.py` (new) — 6 pure-function tests for the verdict.

**Why**: Part of the external heartbeat monitor (A3). All in-process alerters go
silent if the runner dies, so `/health` had to actually reflect runner liveness for
an off-box Worker (`ops/heartbeat-worker/`) to detect outages. Previously `/health`
always returned `{"status":"ok"}` regardless of runner state.

**Depends on**: runner writes `heartbeat:runner` each loop (see runner CHANGELOG);
`KEY_RUNNER_HEARTBEAT` constant + `runner_heartbeat_stale_seconds` setting.

**How to verify**: `curl -s localhost:8080/health | jq` → 200 with a small
`runner_heartbeat_age_s` while the runner is up; `launchctl stop com.assistant.runner`
→ 503 within ~90s.

## 2026-04-20 — Telegram interface redesign: threads + inline buttons

**Files changed**: `src/gateway/telegram_bot.py` (major rewrite)

**What changed**:
- Added `_error_safe` decorator with 4-level error handling (reply → retry → self-diagnose → graceful degrade)
- `/task` now creates a Telegram reply chain (thread) and stores `thread_message_id` on the Task row
- Thread replies (plain text) auto-route as task continuations via `_handle_thread_reply` MessageHandler
- Inline keyboard buttons replace slash commands for: Approve, Cancel, Send Feedback, View Details, Rate 1–5, structured choices
- `_handle_button` CallbackQueryHandler parses `action:task_prefix[:extra]` callback data
- `_task_notifier` rewritten to reply in threads with buttons (approval_request, question, choices)
- `/help` rewritten to show 4 primary commands; `/status` updated with thread context hints
- Removed dead code: `cmd_cancel`, `cmd_rate`, `cmd_proposals`, `cmd_reply`, `cmd_approve`, `cmd_tasks`
- `_parse_callback` helper added for callback data parsing

**Why**: Replace 16 slash commands with conversational thread-based interaction.

## 2026-04-20 — Fix task notifications: remove parse_mode for AI content

**Files changed**: `src/gateway/telegram_bot.py` — `_task_notifier` now sends
AI-generated content (summaries, plans) without `parse_mode="Markdown"`.
Prevents 400 Bad Request from Telegram when content has unmatched markdown.

**Why**: Implementation plans with `##`, `**`, backticks crashed the notification.

## 2026-04-20 — Add /clear admin command

**Files changed**: `src/gateway/telegram_bot.py` — New `cmd_clear` handler.
Cancels all queued/running jobs, fails all active/awaiting/pending tasks,
flushes the Redis queue.

**Why**: Users needed a way to bulk-cancel everything without raw SQL.

## 2026-04-20 — Diagnose: cmd_jobs crashes on `_writeback` skill name

**Files changed**: none (diagnosis only — server code edit requires `server-patch` / manual apply).

**Root cause**: `cmd_jobs` (`src/gateway/telegram_bot.py:810`) interpolates
`skill = j.resolved_skill or j.kind` into a Markdown message without passing it
through `_esc_md()`. When the skill name begins with `_` (e.g. `_writeback`), the
leading underscore opens an italic entity that never closes, and the Telegram API
returns `400 Bad Request: can't find end of the entity starting at byte offset N`.

**Proposed fix**: wrap the assignment in `_esc_md(...)`, and audit sibling
renderers (`cmd_status`, `cmd_tasks`, callback handlers) for the same pattern.
See `docs/Troubleshooting.md` → "Telegram handler crashes with 'Can't parse entities'".

**Risk**: medium (server code). Not auto-applied; Phase 5 `server-patch` or manual edit required.

## 2026-04-20 — Thread-based Telegram interface with inline buttons

**Files changed**:
- `src/gateway/telegram_bot.py` — Rewrote interface from 16 slash commands to
  thread-based with inline buttons. `/task` creates reply thread with [Cancel]
  button. Plain text replies in threads auto-route as task continuations.
  Inline buttons handle approve/cancel/rate/feedback/details/choices.
  `_task_notifier` posts in threads + sends summary DM. `/help` shows 4
  commands. `/status` shows active tasks. Removed old slash commands
  (reply, approve, tasks, cancel, rate, proposals). `@_error_safe` applied
  to all handlers.
- `tests/test_telegram_commands.py` — Added `TestParseCallback` (3 tests).

**Why**: 16 slash commands created cognitive overhead. Thread-based approach
is more natural: start a task, reply in the thread to continue, tap buttons
for actions. Users no longer need to remember task IDs or command syntax.

**Side effects**: Old `/reply`, `/approve`, `/tasks`, `/cancel`, `/rate`,
`/proposals` commands removed. Functionality preserved via inline buttons
and thread replies.

## 2026-04-20 — Add _error_safe decorator for Telegram handlers

**Files changed**: `src/gateway/telegram_bot.py`

**Why**: Handlers crashed silently. Now: retry once, self-diagnose, graceful degradation.

## 2026-04-20 — Pin response options to /tasks and /jobs output

**Files changed**: `src/gateway/telegram_bot.py` — Each task and job in
the list output now shows its available actions inline based on status.
Cross-links between `/tasks` and `/jobs` at the bottom of each listing.

**Why**: Users had to remember which commands to run after seeing a listing.
Now the next action is right there.

## 2026-04-20 — Fix Markdown escaping in /tasks, /jobs + add command tests

**Files changed**:
- `src/gateway/telegram_bot.py` — Added `_esc_md()` helper to escape
  Telegram Markdown special chars in user-supplied text. Applied to
  description fields in `/tasks` and `/jobs` output. Fixed silent crash
  when descriptions contained underscores/backticks.
- `tests/test_telegram_commands.py` (NEW) — 13 tests for `_esc_md()` and
  `parse_flags()` regression.

**Why**: `/tasks` crashed with `BadRequest: can't find end of entity` when
task descriptions contained Markdown-breaking characters.

## 2026-04-20 — Added /jobs command

**Files changed**: `src/gateway/telegram_bot.py` — New `cmd_jobs` handler.
Shows recent jobs with status icon, skill, description, and linked task ID.
Usage: `/jobs` (default 10) or `/jobs 25` (max 25).

**Why**: Users couldn't see what jobs are running or recently completed
without using `/status` on individual job IDs.

## 2026-04-20 — Fix /approve handler broken query

**Files changed**: `src/gateway/telegram_bot.py` — Removed broken nested
`select(select(...))` in `cmd_approve` that crashed before the status update.

**Why**: `/approve` silently failed — task stayed in `pending_approval`.

## 2026-04-20 — Multi-turn task commands + API endpoints

**Files changed**:
- `src/gateway/telegram_bot.py` — New commands: `/reply` (respond to task),
  `/approve` (mark task complete), `/tasks` (list active tasks). Modified
  `/task` to create a Task + first turn before enqueueing the job. Added
  `_task_notifier` listener for `tasks:notify` Redis channel (DMs questions
  and approval requests). Updated `/help` text.
- `src/gateway/web.py` — New endpoints: `GET /api/tasks` (list with status
  filter), `GET /api/tasks/{id}` (task + turns).

**Why**: Users couldn't respond to task output or approve completion.
New commands close the interaction loop.

**Side effects**: `/task` now creates a Task row + TaskTurn in addition
to the Job. `chat_id` persisted on Task (fixes lost DM mapping on bot restart).

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
