# Gateway module

**Paths:** `src/gateway/jobs.py`, `src/gateway/web.py`, `src/gateway/telegram_bot.py`

## Purpose

Three ways to submit and observe jobs. All three share `src/gateway/jobs.py` as
the single enqueue/cancel/lookup helper.

- `src/gateway/web.py` — FastAPI app on `localhost:8080`. REST (`/api/jobs`) +
  HTMX dashboard shell at `/`.
- `src/gateway/telegram_bot.py` — python-telegram-bot process with 9 commands.
- `src/gateway/jobs.py` — shared helpers: `enqueue_job`, `cancel_job`,
  `find_job_by_prefix`.

## Public interface

- `enqueue_job(description, *, kind, payload, project_id, created_by, task_id,
  parent_job_id, origin_channel=None, origin_ref=None, origin_thread=None) -> Job`
  — A2 (2026-10-21): when `origin_channel` is omitted, channel and ref are
  derived from `created_by` via `origin_from_created_by` (an explicit
  `origin_ref` still wins); an explicit channel is taken as-is and its ref is
  NOT derived (web = `web`/NULL) and must be one of `ORIGIN_CHANNELS`
  (`ValueError` otherwise). An empty `origin_channel` derives like an
  omitted one; empty `origin_ref` / `origin_thread` → NULL; ref/thread
  clipped to 64. The Telegram launch sites pass `telegram`/`<chat id>`
  (+ `origin_thread` = the root reply's message id, persisted on both the
  Task and the Job once the reply exists); `POST /api/jobs` passes `web`.
- `ORIGIN_CHANNELS = ("telegram", "web", "cli", "scheduler", "system")` and
  `origin_from_created_by(created_by) -> (origin_channel, origin_ref | None)`
  — pure (Observability Phase 1 A1, 2026-10-21): the fallback origin for
  producers that pass none; arm-for-arm the same mapping as migration 008's
  `_BACKFILL_ORIGIN` CASE (`telegram:<chat>` → telegram/<chat>, `web`,
  `scheduler`, everything else → system/<created_by>; refs clipped to 64, an
  empty ref is `None`). Called by `enqueue_job` since A2.
- `cancel_job(job_id)` — publishes to `jobs:cancel`
- `find_job_by_prefix(prefix) -> Job | None` — accepts 8-char prefix or full UUID
- FastAPI: `/health`, `/api/jobs` (GET/POST), `/api/jobs/{id}` (GET/DELETE),
  `/api/jobs/{id}/rate` (POST), `/api/jobs/{id}/stream` (SSE),
  `/api/projects`, `/api/projects/public`, `/api/quota`,
  `/api/retrospective/context`, `/api/telemetry/schedules`, `/api/tasks`,
  `/api/tasks/{id}`
- `GET /health` — unauthenticated liveness probe. Returns **200** only when the
  runner heartbeat (`heartbeat:runner` in Redis, written every loop) is fresher than
  `runner_heartbeat_stale_seconds` (default 90s) AND Postgres + Redis are reachable;
  otherwise **503** with `{status, runner_ok, runner_heartbeat_age_s, queue_depth,
  redis_llen, pg_queued, pg_running, pg_deferred, db_ok, redis_ok}`. Since
  2026-08-31 (EVALUATION_2026-08-30 F2.4) `queue_depth` is the Postgres
  `queued` count — the REAL backlog — not the Redis LLEN (which reads 0 while
  ids sit inside the runner); `redis_llen` carries the old value. Polled by
  the external heartbeat Worker (`ops/heartbeat-worker/`).
- `web.health_verdict(heartbeat_age, db_ok, redis_ok, stale_after) -> (runner_ok, healthy)`
  — pure helper behind `/health` (tested in `tests/test_health.py`).
- Telegram primary commands: `/task`, `/status`, `/jobs`, `/help`
- Telegram admin commands: `/chat`, `/resume`, `/schedule`, `/projects`
- Thread-based interaction: plain text replies in task threads auto-route as continuations
- Inline keyboard buttons: approve, cancel, rate, view details, structured choices
- CallbackQueryHandler: parses `action:task_prefix[:extra]` callback data.
  `jd:<job8>` (A6, 2026-10-21) is a JOB-level callback — the FailedCard's
  `[Details]` button — handled before the task lookup: replies with
  `format_job_status(job)` as plain text (no `parse_mode`), or `Job not found.`
- `format_job_status(job) -> str` — pure (A6): `Job <8> — <status>`, kind,
  lane (`lane_label`, provider/model), terminal reason, turns, tokens, api
  time, list-equivalent cost, origin, 300-char error, 600-char summary;
  ≤ 4000 chars, never Markdown-safe by design (sent without `parse_mode`).
- `_lane_label` is a thin alias of `src.notify.outbox.lane_label` since A6
  (one definition for the done DM, `/jobs` and the outbox cards).
- `quota_paused_text(reset_at, reason, source)` (A3) and
  `provider_paused_text(provider, reset_at, reason)` (A6) — pure bodies of
  the `quota_paused` notice for the global Anthropic pause and for a
  non-Anthropic lane respectively.
- Outbox delivery (A6): `_drain_outbox(app, *, legacy_mode) -> (sent,
  failed, skipped)` and `_outbox_listener(app, *, legacy_mode)`
  (`_OUTBOX_POLL_SECONDS = 30`); `_handle_done_message(app, channel, data)
  -> bool` is the per-message gate of the legacy `jobs:done` listener. See
  "Notifications back to user".
- MessageHandler: detects replies to task threads via `thread_message_id` lookup

## Flag parsing

`parse_flags()` in `telegram_bot.py` extracts `--model=`, `--effort=`,
`--permission=`, `--project=`, `--kind=` from the front of a description.
Model aliases come from the repo-root `models.yml` via
`registry.models.alias_table()` (`_MODEL_ALIASES`, T1 2026-10-21): `opus`,
`opus-4-7`, `opus-4-6`, `sonnet`, etc. → bare Anthropic ids; a non-Anthropic
alias is keyed `provider/alias`. Retired aliases (`haiku`, `haiku-4-5`)
resolve to `claude-sonnet-4-6` via `_RETIRED_MODEL_ALIASES` and are not in
the registry. Whatever the alias tables yield is then resolved through
`registry.models.resolve()` and stored **canonical** (bare Anthropic id,
`provider/model_id` otherwise); an unknown provider or model raises
`ModelFlagRefused(raw, reason)` at parse time (T7, 2026-10-21) — never a raw
pass-through. Handlers call `_parse_flags_or_reply(update, raw)`, which adds
the `resolve_enabled` (`ROUTER_PROVIDERS_ENABLED`) check and replies with the
reason + accepted list on refusal, creating no Task and no job. Flags land in
`job.payload` and take precedence over skill frontmatter.

Provider surfaces (T7): `/jobs` rows and the task "details" card show
`` `provider/model` `` (`_lane_label(provider, model, terminal_reason)` —
pure; model alone for pre-007 rows, nothing while queued, `· <reason>`
appended when not `ok`); the done/failed DM (`_deliver_done` →
`_done_dm_text`) reads the lane from the job row (`_job_lane`), degrading to
the pre-T7 text on any lookup failure.

`POST /api/jobs` (web) validates `model` through
`registry.models.resolve_enabled` and stores the canonical form; unknown or
disabled → **422** `model refused: <reason>`. The dashboard model dropdown
is rendered from the registry (`web._model_options_html`), one `<optgroup>`
per enabled provider (T7). `JobOut` carries the 007 columns
`resolved_provider`, `model_served`, `terminal_reason` (additive, None on
pre-007 rows) and the jobs table has a Provider column.

## Auth

- Telegram: chat_id whitelist from `TELEGRAM_ALLOWED_CHAT_IDS`.
- Web: Bearer token or HTTP Basic (password = `WEB_AUTH_TOKEN`). If unset, dev mode (no auth).

## Notifications back to user

- **Outbox (A6, 2026-10-21; D-P1-10)**: the runner always writes a
  `notifications` row (A5) and always publishes the legacy channels; the bot
  decides which renderer sends. `_outbox_listener` ALWAYS runs
  (`release_stuck_sending()` once, subscribe `notify:outbox`, drain on every
  nudge and at least every 30 s — a bot restart loses no DM). With
  `settings.notify_outbox` **on** (the default since A6) it delivers every
  row (claim → `render_telegram` → `send_via_bot` → `mark_sent` /
  `mark_failed` with backoff; token-free `last_error`) and the legacy
  renderers below are gated off. With `NOTIFY_OUTBOX=0` (kill switch,
  bot-only restart) the listener runs in `legacy_mode`: job/task rows are
  marked `skipped`, the ops kinds (`quota_*`, `schedule_deferred`,
  `ops_alert`, …) are still delivered, and the legacy renderers send the
  job/task cards.
- Legacy `jobs:done:*` renderer (`_handle_done_message` → `_deliver_done`):
  DMs the submitter when their job completes, only while the outbox is off;
  the in-memory submitter→chat_id entry (`_job_to_chat`) is popped either
  way. Legacy `tasks:notify` renderer (`_task_notifier`): same gate.
- Quota state change (pause/resume) → `_quota_notifier` writes a
  `quota_paused` / `quota_resumed` OPS row per lane (the global Anthropic
  pause and every enabled non-Anthropic lane via `quota.is_provider_paused`),
  delivered in both switch positions. The Anthropic pause body is the pure
  `quota_paused_text(reset_at, reason, source)`; its reset line says
  `(vendor)` only when a `RateLimitEvent` carried the time
  (`quota.last_source()`), else `(estimated)` (A3, 2026-10-21). A lane body is
  `provider_paused_text(...)` and names `/resume <provider>`.

## Dependencies

- `src.config`, `src.db`, `src.models`, `src.audit_log`
- `src.notify.outbox` (A6: `OPS_NOTICE_KINDS`, `lane_label`, `build_ops_notice`, `enqueue_notice`, `pending_notices`, `claim_notice`, `mark_sent`, `mark_failed`, `mark_skipped`, `release_stuck_sending`) and `src.notify.telegram` (`render_telegram`, `send_via_bot`, `TelegramSendError`)
- `src.runner.quota` (is_paused, clear, last_source (A3); T6: is_provider_paused, paused_providers, clear_provider — `GET /api/quota` adds `providers: {<p>: {paused, reset_at, reason}}` for non-Anthropic registry providers; `/status` lists each paused lane; `/resume <provider>` lifts one lane, bare `/resume` the global pause)
- `fastapi`, `python-telegram-bot`

## Testing

Flag parsing and writeback classification are covered in `tests/test_pure_functions.py`.
`tests/test_health.py` covers the `/health` verdict logic (`health_verdict`).
No dedicated gateway integration tests (httpx/ASGI) — pure-function tests cover the
parsers, classifiers, and the health verdict.

## Gotchas

- Don't `from sqlalchemy import update` in the telegram module — it shadows
  `telegram.Update`. Use `sql_update` alias.
- `find_job_by_prefix` with a too-short prefix (3 chars) can match many jobs.
  It returns None on ambiguous matches — callers should treat that as "not found".
- The HTMX dashboard polls every 5s for the job list. Live streaming is available
  via `/api/jobs/{id}/stream` (SSE/EventSource) for individual job tailing.
