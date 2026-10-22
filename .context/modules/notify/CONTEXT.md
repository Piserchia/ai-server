# Notify module

**Paths:** `src/notify/outbox.py`, `src/notify/telegram.py`, `src/notify/__main__.py` (`src/notify/__init__.py` re-exports only)

## Purpose

Durable, channel-agnostic notifications (Observability Phase 1, spec §3 +
§9; plan `docs/superpowers/plans/2026-10-21-observability-phase1-recut.md`
A4). Producers INSERT a `notifications` row and nudge `notify:outbox`; the
Telegram bot's outbox listener (A6) delivers on the nudge + a 30 s poll and
stamps delivery status, so a bot restart loses nothing and alert history is
queryable (`SELECT notice_kind, status, attempts, last_error FROM
notifications ORDER BY created_at DESC`).

**The switch is the bot's (D-P1-10).** `settings.notify_outbox`
(`NOTIFY_OUTBOX`, default True since A6) is read ONLY by
`src/gateway/telegram_bot.py` and `src/notify/__main__.py`. The runner,
`outbox.py` and the launchd alerter scripts (`scripts/healthcheck-all.sh`,
`scripts/schedule-monitor.sh` — `python -m src.notify send` first, raw curl
as the fallback, A7) never read it: the runner always publishes the legacy
`tasks:notify` / `jobs:done` channels AND always writes the row. Off = the
legacy renderers send job/task DMs and the listener delivers only
`OPS_NOTICE_KINDS` (the kinds that have no legacy path); on = the listener
delivers everything and the legacy renderers are gated.

## Public interface

- `outbox.Notice(notice_kind, body, severity="info", subject_type=None, subject_id=None, actions=None, channel="telegram", target=None, thread=None)` — frozen dataclass. `target` = chat id (None → owner = first `TELEGRAM_ALLOWED_CHAT_IDS` entry ONLY — since A6 the quota pause/resume notices no longer fan out to every allowed chat as the pre-A6 loop did); `thread` = Telegram message id to reply under; `actions = {"buttons": [[[label, callback], …], …], …}`.
- Vocabulary: `NOTICE_KINDS` = `JOB_NOTICE_KINDS` (`job_completed`, `job_failed`) ∪ `TASK_NOTICE_KINDS` (`task_<t>` for the nine `TASK_NOTIFY_TYPES`: `approval_request, question, choices, plan, plan_approval, completed, progress, failed, review_flagged`) ∪ `OPS_NOTICE_KINDS` (`ops_alert, quota_paused, quota_resumed, schedule_deferred, settings_override, credential_canary, provider_enforcement`); `STATUSES = (pending, sending, sent, failed, skipped)`; `SEVERITIES = (info, warn, critical)`; `MAX_ATTEMPTS = 5`; `SENDING_LEASE_SECONDS = 300`; `COMPLETION_DM_CHANNELS = ("telegram", "web", "cli")` (⊆ `gateway.jobs.ORIGIN_CHANNELS`; `pwa` is Phase 2).
- Pure policy: `should_notify_job(*, status, kind, task_id, origin_channel) -> bool` (spec §3 card eligibility: `_`-prefixed kinds never; `failed` always; `completed` only when `task_id is None` and the channel is in `COMPLETION_DM_CHANNELS`; children inherit the PARENT's channel — the caller resolves it); `lane_label(provider, model, terminal_reason) -> str` (THE definition of `provider/model[ · reason]`; A6 aliases `telegram_bot._lane_label` to it); `notice_kind_for_task_type(t)`; `retry_delay_seconds(n)` (30 s · 2^(n-1), cap 600); `transition_after_failure(attempts_so_far, now) -> (status, attempts, next_attempt_at)`.
- Pure builders: `build_job_notice(*, job_id, status, kind, resolved_skill, summary, error_message, terminal_reason, origin_channel, origin_ref, origin_thread, created_by, task_id=None, model_served=None, resolved_provider=None, resolved_model=None, num_turns=None, duration_seconds=None) -> Notice | None` (plain-text header `<job8> · <skill> · <duration> · <lane_label> · <turns>`, failures add `· via <schedule|channel|created_by>` and the `[Details]` button `jd:<job8>`; `target` only for `telegram` origins, else owner); `build_task_notice(*, task_id, notify_type, text, question=None, choices=None, target=None, thread=None) -> Notice` (one card per legacy type, callbacks identical to what `_handle_button` parses, **no `rate:` row**); `build_ops_notice(*, kind, severity, text, subject=None, target=None) -> Notice` (`kind` must be an OPS kind; `subject` = `job:<uuid>` | `task:<uuid>` | `schedule:<name>`).
- Async (thin SQLAlchemy, never raise to producers): `enqueue_notice(notice) -> uuid | None` (ALWAYS inserts `pending` + nudges `CHANNEL_NOTIFY_OUTBOX`; None only when the insert failed, logged); `record_notice(notice, *, status, external_ref=None, last_error=None) -> uuid` (raises on bad kind/status or insert failure; `attempts=1` for `sent`/`failed`); `pending_notices(limit=20, now=None)`; `claim_notice(id, now=None) -> bool` (`pending → sending`, `attempts+1`, lease in `next_attempt_at`; False = another drainer has it); `release_stuck_sending(now=None) -> int` (called before EVERY drain — bot listener startup + each iteration, CLI drain once per run; whole-tier review 2026-10-22); `mark_sent(id, external_ref, *, subject_type=None, subject_id=None)`; `mark_failed(id, error, *, attempts_so_far, subject_type=None, subject_id=None) -> status`; `mark_skipped(id, reason)` (terminal; A6 `legacy_mode` for job/task kinds).
- `telegram.TelegramMessage(chat_id, text, buttons=(), reply_to_message_id=None)`; `render_telegram(notice_or_row, *, owner_chat_id) -> TelegramMessage` (the ONLY place that knows `TELEGRAM_TEXT_LIMIT=4096`, `CALLBACK_LIMIT_BYTES=64`, `MAX_BUTTONS=8`; plain text, no `parse_mode`; non-numeric/absent `target` → owner; `task_*` headers carry `actions.prefix` — `✋ task abcdef12 needs your approval`); `fit_text`, `validate_callback`, `build_buttons`, `keyboard_markup` (lazy `from telegram import …` — the module name shadows the package; never module-level); `send_via_bot(bot, msg) -> message_id` (retries once without `reply_to` when the target is gone); `send_via_http(token, msg, *, transport=None) -> message_id`.
- `telegram.TelegramSendError` — the secrets chokepoint: `send_via_http` never calls `raise_for_status()`; a non-2xx raises `TelegramSendError("telegram <status>: <API description | reason phrase>")`, any other exception (connect error, timeout, malformed body) is wrapped as `TelegramSendError(type(exc).__name__)`. No httpx message (which carries the request URL with the bot token) escapes into `notifications.last_error`, stdout or a timer log.
- CLI: `python -m src.notify send --kind <ops kind> [--severity info|warn|critical] --text "…" [--subject job:<uuid>] [--target <chat>]` — direct HTTP send first (the bot may be what is down), then `record_notice(status=sent|failed)` as the alert history; **exit 0 only when delivered**, 1 otherwise so bash callers take their curl fallback (A7). `python -m src.notify drain [--limit N]` — claims before sending (safe beside the running bot) and mirrors the bot's `legacy_mode`: with `NOTIFY_OUTBOX=0` job/task rows are marked `skipped`, ops rows are sent. Everything the CLI records or prints passes through `_redact` (bot token → `[REDACTED]`).
- Audit kinds on `subject_type == "job"` rows (appended to the job's JSONL only — not mirrored to `jobs:stream:<id>`): `notice_queued{notice_id, notice_kind}`, `notice_sent{notice_id, external_ref}`, `notice_failed{notice_id, error}`. `record_notice` emits the one matching the status it writes; `mark_failed` emits `notice_failed` only at the terminal `failed`.

## Consumers (by task)

A5 runner (`build_job_notice`, `build_task_notice`, `enqueue_notice`); A6 bot (`pending_notices`, `claim_notice`, `release_stuck_sending`, `mark_sent`, `mark_failed`, `mark_skipped`, `render_telegram`, `send_via_bot`, `build_ops_notice` for quota, `lane_label`, `OPS_NOTICE_KINDS`); A7 alerters and E10 canary (`python -m src.notify send`); D1 (`schedule_deferred`); E1 (`settings_override`).

## Dependencies

`db` (`async_session`, `redis`, `CHANNEL_NOTIFY_OUTBOX`), `models.Notification`, `audit_log`, `gateway.jobs.ORIGIN_CHANNELS` (no cycle: `gateway.jobs` imports only `db`/`models`); `__main__` adds `config`. `telegram.py` imports nothing from `src`; `telegram` (python-telegram-bot) and `httpx` are imported lazily inside functions.

## Testing

`tests/test_notify_outbox.py` (pure policy/builders + the async wrappers against a recording session), `tests/test_notify_telegram.py` (renderer limits, `send_via_bot` with a fake bot, `send_via_http` through `httpx.MockTransport`, the CLI with the sender routed through the mock and the row writer recorded). No DB, no Redis, no network. Live smoke after deploy: `python -m src.notify send --kind ops_alert --severity info --text "outbox CLI smoke — ignore"` → `notice <uuid> sent`.
