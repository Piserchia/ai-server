# System context

> Source of truth for the server's architecture. Update when modules change.
> Last updated: 2026-04-16 (Phase 1 bootstrap)

## Tech stack

- **Language**: Python 3.12
- **Agent runtime**: Claude Agent SDK (subscription auth via bundled Claude Code CLI)
- **Database**: PostgreSQL 15 (async via asyncpg + SQLAlchemy 2.0)
- **Cache/queue**: Redis 7 (pub/sub, BLPOP queue, quota state)
- **Web**: FastAPI + Uvicorn
- **Bot**: python-telegram-bot
- **Scheduler**: croniter (runs inside the runner process)
- **Reverse proxy**: Caddy (per-project routing)
- **Tunnel**: cloudflared (named tunnel to Cloudflare edge)
- **Supervision**: macOS launchd
- **Testing**: pytest, fakeredis (future)

## Module graph

| Module | Purpose | Depends on | Depended on by |
|---|---|---|---|
| `src/config.py` | Pydantic settings; no API key, subscription auth | — | Everything |
| `src/db.py` | Async SQLAlchemy + Redis | config | Everything that touches state |
| `src/models.py` | ORM: Job, Schedule, Project | — | db, runner, gateway, registry |
| `src/audit_log.py` | JSONL-per-job audit log | config | runner, gateway |
| `src/runner/session.py` | One Agent SDK session per job | config, db, models, audit_log, registry.skills, runner.quota, runner.router | runner.main |
| `src/runner/main.py` | Job loop + scheduler + cancel listener + writeback/escalation hooks | config, db, models, runner.session, runner.quota, runner.writeback, gateway.jobs, registry.skills, audit_log | (entry point) |
| `src/runner/router.py` | Rule-based keyword → skill matcher | — | runner.session |
| `src/runner/quota.py` | Detect rate limits, pause/resume queue | config, db | runner.session, runner.main |
| `src/runner/writeback.py` | Classify whether a session needs a CHANGELOG follow-up | — | runner.main |
| `src/registry/skills.py` | Load SKILL.md frontmatter | config | runner.session |
| `src/registry/manifest.py` | Load project manifest.yml | config | register-project.sh, healthcheck |
| `src/gateway/jobs.py` | Shared enqueue/cancel/find helpers | db, models | web, telegram_bot |
| `src/gateway/web.py` | FastAPI: /api/jobs + dashboard | config, db, models, gateway.jobs, audit_log | (entry point) |
| `src/gateway/telegram_bot.py` | Telegram 6 commands + done-notification DMs | config, db, models, gateway.jobs, audit_log | (entry point) |
| `scripts/register-project.sh` | Project registration: manifest → Caddy + launchd + DB | yq, caddy, psql | — |
| `scripts/healthcheck-all.sh` | Probe all projects, update `last_healthy_at` | yq, curl, psql | — |

## Data flow

```
Telegram message → bot (validates chat_id, creates Job, RPUSH jobs:queue)
                                                        ↓
Runner: BLPOP → Job row → resolve skill (rule or frontmatter) → resolve cwd →
build ClaudeAgentOptions → ClaudeSDKClient session →
  stream AssistantMessage / UserMessage / ResultMessage →
  audit_log.append(...) per event + Redis publish jobs:stream:<id>
                                                        ↓
Session ends → write summary → update Job row → publish jobs:done:<id>
                                                        ↓
Bot's done_listener picks up → DMs the submitter
```

## Conventions

- **All LLM calls go through `runner.session.run_session`.** Never call the SDK elsewhere.
- **Skill frontmatter is the contract.** Runner reads it; skill body is the system prompt.
- **Audit log is append-only.** Use `audit_log.append(...)`. Never rewrite prior entries.
- **Redis channels** live in `db.py` as named constants. Don't inline string names.
- **Error handling**: catch `QuotaExhausted` specifically in the runner; everything else is a failure.
- **Migrations**: Alembic. One migration file (`001_initial.py`) for Phase 1; add more as schema evolves.

## Invariants (hard rules)

| ID | Invariant | Enforced in |
|---|---|---|
| INV-1 | Every session has a resolved model, effort, permission_mode | `runner/session.py:_build_options` |
| INV-2 | Every job writes `job_started` + one terminal event to audit log | `runner/main.py:_process_job` |
| INV-3 | Server uses subscription auth; `ANTHROPIC_API_KEY` is never set | `runner/main.py:_check_subscription_auth` + `scripts/run.sh` |
| INV-4 | Server code changes never auto-merge | `server-patch` SKILL.md + PR gate |
| INV-5 | Write-back verification runs after every session that modified code | `runner/main.py` post-session hook (Phase 4+) |
| INV-6 | Only whitelisted chat IDs can submit jobs via Telegram | `gateway/telegram_bot.py:_guard` |
| INV-7 | Only auth'd web requests can submit jobs | `gateway/web.py:_check_auth` |
| INV-8 | Cancel requests honored within 2s | `runner/main.py:_cancel_listener` |
| INV-9 | Job status transitions are valid (queued→running→terminal only) | `models.py` + `_finish_job` |
| INV-10 | Skills in `plan` mode cannot write files | SDK-level permission_mode |
| INV-11 | Audit logs are append-only | filesystem O_APPEND in `audit_log.append` |
| INV-12 | Quota exhaustion pauses queue until reset; jobs requeued at front | `runner/main.py:_process_job` |
| INV-13 | `server-patch` always requires a passing `code-review` sub-agent | `server-patch` SKILL.md + runner post-hook |
| INV-14 | Project slugs unique; port allocations never reused | `registry/manifest.py` + `projects/_ports.yml` |

## Environment & setup

```bash
# Once, during bootstrap:
claude login                                    # subscription auth
cp .env.example .env && vi .env                 # fill in secrets
brew services start postgresql@15 redis
pipenv install
pipenv run alembic upgrade head

# To run:
bash scripts/run.sh start
bash scripts/run.sh status
bash scripts/run.sh stop
```

## Known technical debt / open items

- **Write-back verification is in place** (Phase 2); if the primary session skips
  the PROTOCOL.md write-back, the runner enqueues a `_writeback` child job.
  Frequent triggering is a signal that the primary skill's SKILL.md needs clearer
  write-back instructions.
- **Escalation via `on_failure` frontmatter works** (Phase 2); one level only,
  guarded by `escalated_from` payload flag to prevent loops.
- **Quota detection is heuristic** — string-match on error messages. Once the SDK
  surfaces structured rate_limit errors, switch to typed detection.
- **Dashboard is HTMX shell** — enough for Phase 1/2; add SSE streaming for live
  job tail in Phase 3.
- **No integration tests yet** — only pure-function unit tests. The SDK mock
  surface is complex; Phase 4+ can add integration tests once we have a stable
  set of skills to test against.

## Hosting

- **Domain**: `chrispiserchia.com` (Cloudflare Registrar)
- **Tunnel**: Cloudflare named tunnel `ai-server`, config at `~/.cloudflared/config.yml`
- **Reverse proxy**: Caddy at `$PROJECT_ROOT/Caddyfile` + `Caddyfile.d/*.conf`
- **Per-project supervision**: `~/Library/LaunchAgents/com.assistant.project.*.plist`
- **Healthcheck**: `scripts/healthcheck-all.sh` every 5 min via `com.assistant.healthcheck-all.plist`
- **Project registry**: `.context/PROJECTS_REGISTRY.md` (index) + per-project `.context/CONTEXT.md`

See `.context/modules/hosting/CONTEXT.md` for the full manifest schema and documentation standard.

## Active workstreams

- Phase 1 ✓ (commit 05ad5e7): skeleton, 3 processes, Phase 1 smoke test verified locally
- Phase 2 ✓ (commit 6e58fe3): `research-report` + `_writeback` skills, write-back verification hook, failure-escalation hook, 52-test pure-function suite
- Phase 3 ✓: domain `chrispiserchia.com` + Cloudflare tunnel + Caddy + `baseball-bingo` (static) + `market-tracker` (3-service) + healthchecks
- Phase 4 ✓: `code-review` sub-agent + MCP servers (projects, dispatch) + `new-project` (two-phase Opus) + `app-patch` (direct push) + `new-skill` + `project-evaluate` + `self-diagnose` + event triggers (4 async tasks now)
- Phase 5 ✓: `server-upkeep` (daily at 03:00) + `backup` (nightly at 04:00, no retention cap) + `server-patch` (PR-gated, manual merge) + `review-and-improve` (idle-queue triggered, up to 1/day) + `retention.py` (audit log rotation)
- Phase 6 ✓: `research-deep` + `idea-generation` + `project-update-poll` + `restore` + `/schedule` Telegram command + SSE streaming endpoint + `retrospective.py` auto-tuning queries. All 6 phases complete.
