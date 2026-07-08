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
  `/api/jobs/{id}/rate` (POST), `/api/jobs/{id}/stream` (SSE),
  `/api/projects`, `/api/projects/public`, `/api/quota`,
  `/api/retrospective/context`, `/api/tasks`, `/api/tasks/{id}`
- `GET /health` — unauthenticated liveness probe. Returns **200** only when the
  runner heartbeat (`heartbeat:runner` in Redis, written every loop) is fresher than
  `runner_heartbeat_stale_seconds` (default 90s) AND Postgres + Redis are reachable;
  otherwise **503** with `{status, runner_ok, runner_heartbeat_age_s, queue_depth,
  db_ok, redis_ok}`. Polled by the external heartbeat Worker (`ops/heartbeat-worker/`).
- `web.health_verdict(heartbeat_age, db_ok, redis_ok, stale_after) -> (runner_ok, healthy)`
  — pure helper behind `/health` (tested in `tests/test_health.py`).
- Telegram primary commands: `/task`, `/status`, `/jobs`, `/help`
- Telegram admin commands: `/chat`, `/resume`, `/schedule`, `/projects`
- Thread-based interaction: plain text replies in task threads auto-route as continuations
- Inline keyboard buttons: approve, cancel, rate, view details, structured choices
- CallbackQueryHandler: parses `action:task_prefix[:extra]` callback data
- MessageHandler: detects replies to task threads via `thread_message_id` lookup

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
