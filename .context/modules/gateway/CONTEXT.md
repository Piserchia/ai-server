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

- `enqueue_job(description, kind, payload, project_id, created_by) -> Job`
- `cancel_job(job_id)` — publishes to `jobs:cancel`
- `find_job_by_prefix(prefix) -> Job | None` — accepts 8-char prefix or full UUID
- FastAPI: `/health`, `/api/jobs` (GET/POST), `/api/jobs/{id}` (GET/DELETE),
  `/api/jobs/{id}/rate` (POST), `/api/projects`, `/api/quota`
- Telegram commands: `/task`, `/chat`, `/status`, `/cancel`, `/rate`,
  `/projects`, `/resume`, `/help`

## Flag parsing

`parse_flags()` in `telegram_bot.py` extracts `--model=`, `--effort=`,
`--permission=`, `--project=`, `--kind=` from the front of a description.
Model aliases: `opus`, `opus-4-7`, `opus-4-6`, `sonnet`, `haiku`, etc.
Flags land in `job.payload` and take precedence over skill frontmatter.

## Auth

- Telegram: chat_id whitelist from `TELEGRAM_ALLOWED_CHAT_IDS`.
- Web: Bearer token or HTTP Basic (password = `WEB_AUTH_TOKEN`). If unset, dev mode (no auth).

## Notifications back to user

- Telegram bot subscribes to `jobs:done:*` channels; DMs the submitter when
  their job completes. The submitter→chat_id mapping is held in memory (lost
  on bot restart — acceptable tradeoff vs adding a Redis key per job).
- Quota state change (pause/resume) → periodic notifier DMs all allowed chat IDs.

## Dependencies

- `src.config`, `src.db`, `src.models`, `src.audit_log`
- `src.runner.quota` (read-only: is_paused, clear)
- `fastapi`, `python-telegram-bot`

## Testing

None yet (Phase 1). Phase 2: add `tests/test_flag_parsing.py`,
`tests/test_web_api.py` with httpx/ASGI.

## Gotchas

- Don't `from sqlalchemy import update` in the telegram module — it shadows
  `telegram.Update`. Use `sql_update` alias.
- `find_job_by_prefix` with a too-short prefix (3 chars) can match many jobs.
  It returns None on ambiguous matches — callers should treat that as "not found".
- The HTMX dashboard uses no persistent SSE yet; it polls every 5s. Phase 2 adds
  real streaming via `/api/jobs/{id}/stream` (EventSource).
