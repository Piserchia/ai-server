# System context

> Source of truth for the server's architecture. Update when modules change.
> Last updated: 2026-07-12 (P0–P3: deploy pipeline, workspace/container isolation,
> plan DAG + NL-first Telegram + acceptance evaluator)

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
- **Session isolation**: per-job git workspace clones (`volumes/workspaces/`); optional container lane via docker CLI (colima/OrbStack/Docker Desktop) for `isolation: container` skills — see `docs/CONTAINERS.md`
- **Testing**: pytest, fakeredis (future)

## Module graph

| Module | Purpose | Depends on | Depended on by |
|---|---|---|---|
| `src/config.py` | Pydantic settings; no API key, subscription auth | — | Everything |
| `src/db.py` | Async SQLAlchemy + Redis | config | Everything that touches state |
| `src/models.py` | ORM: Job, Schedule, Project, Proposal | — | db, runner, gateway, registry |
| `src/audit_log.py` | JSONL-per-job audit log | config | runner, gateway |
| `src/runner/session.py` | Skill/isolation resolution + one session per job (in-process SDK or container executor) | config, db, models, audit_log, registry.skills, runner.quota, runner.router, runner.llm_router, runner.workspaces, runner.executors, runner.mcp_projects, runner.mcp_dispatch, context.module_graph | runner.main |
| `src/runner/main.py` | Job loop + scheduler + cancel listener + writeback/escalation/plan-DAG/evaluate hooks | config, db, models, runner.session, runner.quota, runner.writeback, runner.review, runner.events, runner.learning, runner.audit_index, runner.router, runner.plans, gateway.jobs, registry.skills, audit_log | (entry point) |
| `src/runner/router.py` | Rule-based keyword → skill matcher (incl. `plan` for multi-step asks) | — | runner.session, gateway.telegram_bot (triage) |
| `src/runner/llm_router.py` | Haiku routing fallback when rules miss; audited decisions | claude_agent_sdk, config, registry.skills | runner.session |
| `src/runner/workspaces.py` | Per-job isolation: workspace clones, canonical ff-sync, tier resolution | — | runner.session, server-upkeep skill |
| `src/runner/executors.py` | Container execution lane (`claude -p` stream-json parity with SDK lane) | config, audit_log, runner.quota | runner.session |
| `src/runner/plans.py` | Plan validation + subtask DAG spawn/promotion/cascade | config, db, models, audit_log | runner.main, gateway.telegram_bot (manual approve) |
| `src/runner/quota.py` | Detect rate limits, pause/resume queue | config, db | runner.session, runner.main |
| `src/runner/writeback.py` | Classify whether a session needs a CHANGELOG follow-up | — | runner.main |
| `src/runner/review.py` | Code-review sub-agent; evaluates diffs post-session | config, audit_log, claude_agent_sdk | runner.main |
| `src/runner/events.py` | Event-trigger rules engine (4th async task) | db, models, gateway.jobs | runner.main |
| `src/runner/mcp_projects.py` | MCP server: project tools (list, get, logs, restart) | config, db, models | runner.session |
| `src/runner/mcp_dispatch.py` | MCP server: job enqueue tool (task/parent linkage + depends_on deferral) | gateway.jobs, db, models | runner.session |
| `src/runner/retention.py` | Audit log rotation (compress + archive old JSONL) | config | server-upkeep skill |
| `src/runner/audit_index.py` | Build INDEX.jsonl for fast job lookup by skill/status/keyword | config | server-upkeep skill, self-diagnose skill |
| `src/runner/retrospective.py` | Auto-tuning rollup queries (skill performance stats + context consumption) | config, db, models | review-and-improve skill, gateway.web |
| `src/runner/proposals.py` | Proposal tracking helpers (pure + async DB ops); backs `/proposals` + dedup/merge-stamping in review-and-improve + server-patch | db, models | gateway.telegram_bot, review-and-improve skill, server-patch skill |
| `src/runner/learning.py` | Post-session Haiku classifier; enqueues `_learning_apply` child jobs when a completed job reveals a reusable learning | claude_agent_sdk, audit_log, config, gateway.jobs, db, models | runner.main |
| `src/context/module_graph.py` | Parse SYSTEM.md module graph; dependency detection + import validation | — | runner.session, scripts/lint_docs.py |
| `src/registry/skills.py` | Load SKILL.md frontmatter | config | runner.session |
| `src/registry/manifest.py` | Load project manifest.yml | config | register-project.sh, healthcheck |
| `src/gateway/jobs.py` | Shared enqueue/cancel/find helpers | db, models | web, telegram_bot |
| `src/gateway/web.py` | FastAPI: /api/jobs + dashboard + retrospective routes | config, db, models, gateway.jobs, audit_log, runner.retrospective | (entry point) |
| `src/gateway/telegram_bot.py` | Telegram commands + NL-first plain-text asks + task/plan notification cards | config, db, models, gateway.jobs, audit_log, runner.proposals, runner.router, runner.plans | (entry point) |
| `scripts/register-project.sh` | Project registration: manifest → Caddy + launchd + DB | yq, caddy, psql | — |
| `scripts/healthcheck-all.sh` | Probe all projects, update `last_healthy_at` | yq, curl, psql | — |
| `scripts/backup.sh` | Nightly pg_dump + audit log + log snapshot | psql, tar | — (launchd timer) |
| `scripts/seed-schedules.sh` | Insert canonical schedules into DB | psql | — |
| `scripts/seed-module-skills.sh` | Ensure every `.context/modules/<x>/` has `skills/{GOTCHAS,PATTERNS,DEBUG}.md` stubs | — | bootstrap.sh + test_doc_lint.py |
| `scripts/lint_docs.py` | Validate registries vs actual files; catches stale docs | context.module_graph | tests/test_doc_lint.py |
| `scripts/sync-learnings.sh` | Publish runtime doc drift → origin/runtime-learnings (plumbing; prod-side) | git | — (hourly launchd timer) |
| `Dockerfile.agent` | Container image for `isolation: container` sessions | — | runner.executors (via docker CLI) |

## Data flow

```
Telegram message (bare text or /task) → bot (validates chat_id; triage:
  question→chat, else task; creates Task+Job, RPUSH jobs:queue)
                                                        ↓
Runner: BLPOP → Job row → resolve skill (rule → LLM fallback → generic;
  multi-step asks → `plan`) → resolve cwd → resolve isolation tier
  (none | workspace | container | host) → per-job workspace clone if tiered →
  execute (in-process SDK  or  `claude -p` in container — same audit events) →
  audit_log.append(...) per event + Redis publish jobs:stream:<id>
                                                        ↓
Session ends → final-text markers parsed (TASK_COMPLETE / TASK_QUESTION /
  TASK_PLAN block / EVAL_PASS / EVAL_FAIL → synthesized audit events) →
  workspace pushed → canonical ff-synced → update Job row → jobs:done:<id>
                                                        ↓
Task lifecycle: task_plan → validate → store → spawn subtask DAG (roots
  queued, dependents deferred; promoted as deps complete) →
  task_complete (DAG drained) → `_evaluate` acceptance check →
  EVAL_PASS → task auto-closed, evidence DM'd (Reopen button)
  EVAL_FAIL → fix round (≤ max_eval_rounds) → then awaiting_user
                                                        ↓
Bot's done_listener / task_notifier → DMs + thread cards (plan, completed,
  question, progress)
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
| INV-15 | On startup the runner reconciles orphaned `running` jobs (fail-only) before consuming the queue | `runner/reconcile.py` + `runner/main.py:main` |
| INV-16 | Code-writing skills (`isolation: workspace|container`) never run in a shared checkout — one throwaway clone per job; work leaves only via git push | `runner/workspaces.py` + `runner/session.py:run_session` |
| INV-17 | Containers receive `CLAUDE_CODE_OAUTH_TOKEN` only; `ANTHROPIC_API_KEY` is stripped from their env (INV-3 extended) | `runner/executors.py:run_in_container` |
| INV-18 | `god` is the ONLY host-tier skill — the deliberate break-glass lane for phone-initiated server fixes | `skills/god/SKILL.md` frontmatter + `scripts/lint_docs.py:check_isolation_values` |
| INV-19 | A task auto-closes only on an `_evaluate` EVAL_PASS backed by evidence; the user can always overrule via Reopen | `runner/main.py:_handle_evaluator_result` + bot `reopen` action |

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
- **Dashboard has SSE streaming** — `/api/jobs/{id}/stream` provides live job
  tailing via EventSourceResponse (shipped Phase 6).
- **Pure-function unit tests only** (289+). Integration tests with SDK mocks
  deferred indefinitely — the pure-function surface covers core business logic
  well, and the SDK mock surface is complex with limited payoff.

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
- Atlas integration (2026-07-09): `atlas-report`, `atlas-report-sweep`, `atlas-redeploy` skills registered; `Caddyfile.d/atlas.conf` added; atlas port 8791 in `_ports.yml`; atlas registered as a hosted service (Tailscale-gated via Cloudflare Access).
