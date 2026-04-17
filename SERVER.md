# SERVER.md — Architecture overview

Personal assistant server running on a Mac Mini. Accepts tasks via Telegram or web, runs them through the Claude Agent SDK, hosts resulting projects on a single public domain.

## Six nouns

- **Job** — one unit of work. `kind`, `description`, `status`. Always has an audit log.
- **Skill** — a markdown file that tells Claude how to do a kind of work. Data, not code.
- **Project** — a hosted deliverable (static / service / api) with its own subdomain.
- **Schedule** — a cron expression that enqueues jobs on a recurrence.
- **Manifest** — per-project YAML declaring how to run / host / update it.
- **Audit log** — append-only JSONL of everything that happened on a job.

## Process topology

Managed by launchd, all under `~/Library/Application Support/ai-server/`:

- **runner** (`src/runner/main.py`) — consumes `jobs:queue`, spawns Agent SDK sessions, writes audit logs. Contains the scheduler and cancel-listener as async tasks.
- **web** (`src/gateway/web.py`) — FastAPI; `/api/jobs` REST + dashboard on localhost:8080.
- **bot** (`src/gateway/telegram_bot.py`) — Telegram polling + done notifications.
- **caddy** — reverse proxy; `*.yourdomain.com` routes to projects.
- **cloudflared** — named tunnel exposing Caddy to the internet.

## Data stores

- **Postgres** — `jobs`, `schedules`, `projects` (3 tables, 1 migration).
- **Redis** — `jobs:queue` (BLPOP), `jobs:stream:<id>` (SSE), `jobs:cancel` (pub/sub), `jobs:done:<id>`, `quota:paused_until`.
- **Filesystem** — `volumes/audit_log/<job_id>.jsonl`, `projects/<slug>/`, `skills/<n>/`.

## Auth

Subscription only. `claude login` once, bundled CLI handles the rest. `ANTHROPIC_API_KEY` is explicitly unset in every process's environment.

## Model defaults

- Global default: **Sonnet 4.6**.
- Skills override per-skill via YAML frontmatter in `SKILL.md`.
- Escalation rules (in frontmatter) promote to **Opus 4.7** on failure.
- Routing uses rule-based matcher first (`src/runner/router.py`), Haiku-based `route` skill only as fallback.

## Concurrency

Default 2 concurrent sessions (Max 5x plan; leaves headroom for your direct Claude use). Override via `MAX_CONCURRENT_JOBS`.

## Subscription quota behavior

Runner detects rate_limit / quota signals in SDK messages, pauses the queue until reset (or `QUOTA_PAUSE_MINUTES` default), requeues the current job at the front so it retries after reset. Telegram alert on pause and on resume.

## Invariants (enforced in code)

See `.context/SYSTEM.md` for the full list.

## What this server is NOT

- Not a general-purpose agent framework.
- Not multi-user. Single tenant, whitelisted chat IDs only.
- Not a replacement for Claude Code on your laptop for deep interactive work.
- Not auto-merging server code changes. Ever.
