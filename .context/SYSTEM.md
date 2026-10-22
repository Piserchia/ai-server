# System context

> Source of truth for the server's architecture. Update when modules change.
> Last updated: 2026-08-31 (EVALUATION_2026-08-30 remediation: fail-closed
> skill registry, tighten-only isolation, dispatch guards, queue honesty,
> INV-13 row corrected to actual behavior, INV-21 defined, INV-22 live-money
> ceiling added. Previous: 2026-07-31 autonomous execution lane — INV-4
> rewritten, INV-20 added; 2026-07-27 SDK-native overhaul.)

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
- **Session isolation**: per-job git workspace clones (`volumes/workspaces/`) + PreToolUse guard hooks (`runner/guards.py`) that deny out-of-workspace writes and dangerous host commands in-process — even under bypassPermissions. (The docker container lane was removed 2026-07-27 — `docs/SDK_MIGRATION_2026-07-27.md`.)
- **Testing**: pytest, fakeredis (future)

## Module graph

| Module | Purpose | Depends on | Depended on by |
|---|---|---|---|
| `src/config.py` | Pydantic settings; no API key, subscription auth | — | Everything |
| `src/db.py` | Async SQLAlchemy + Redis | config | Everything that touches state |
| `src/models.py` | ORM: Job, Schedule, Project, Proposal, Task, TaskTurn, Notification | — | db, runner, gateway, registry, notify |
| `src/audit_log.py` | JSONL-per-job audit log | config | runner, gateway |
| `src/runner/session.py` | Skill/isolation resolution + one session per job: in-process SDK for Anthropic (guard hooks + subagents wired here), else dispatch to the registry-named executor module (T4, 2026-10-21; fail-closed lane rules before the clone) | config, db, models, audit_log, registry.skills, registry.models, runner.quota, runner.router, runner.llm_router, runner.workspaces, runner.guards, runner.agents, runner.delivery, runner.mcp_projects, runner.mcp_dispatch, runner.executors.codex_cli, runner.review, context.module_graph | runner.main |
| `src/runner/main.py` | Job loop + scheduler + cancel listener + writeback/escalation/plan-DAG/evaluate hooks + deploy-authority gate | config, db, models, runner.session, runner.quota, runner.writeback, runner.review, runner.events, runner.learning, runner.audit_index, runner.router, runner.plans, runner.delivery, gateway.jobs, registry.skills, registry.models, audit_log | (entry point) |
| `src/runner/router.py` | Rule-based keyword → skill matcher (incl. `plan` for multi-step asks) | — | runner.session, gateway.telegram_bot (triage) |
| `src/runner/llm_router.py` | `settings.utility_model` routing fallback when rules miss; audited decisions | claude_agent_sdk, config, registry.skills | runner.session |
| `src/runner/workspaces.py` | Per-job isolation: workspace clones, canonical ff-sync, tier resolution; runner-side commit+push for non-Anthropic lanes after the pre-push gate (T5) | — | runner.session, server-upkeep skill |
| `src/runner/executors/codex_cli.py` | Codex CLI executor (T3, 2026-10-21): `codex exec --json` per job under Seatbelt, scrubbed env, JSONL → existing audit kinds + `jobs:stream`; `interrupt` SIGTERM→SIGKILL. Dispatched by `runner.session._run_executor` since T4. `main()` = T10 canary / gate dry-run entry points (`scripts/codex-canary.sh`) | config, db, audit_log, runner.review (lazy, gate dry-run only) | runner.session, scripts/codex-canary.sh |
| `src/runner/delivery.py` | Project delivery contract enforcement: dev-repo cwd scoping + deploy-authority gate | config, registry.manifest | runner.session, runner.main |
| `src/runner/guards.py` | PreToolUse guard hooks: workspace write containment + Bash denylist (INV-17) | config, audit_log, claude_agent_sdk | runner.session |
| `src/runner/agents.py` | SKILL.md → SDK AgentDefinition compilation (frontmatter `subagents:` → in-session delegation) | registry.skills, claude_agent_sdk | runner.session |
| `src/runner/plans.py` | Plan validation + subtask DAG spawn/promotion/cascade | config, db, models, audit_log | runner.main, gateway.telegram_bot (manual approve) |
| `src/runner/quota.py` | Detect rate limits; global (Anthropic) queue pause + per-provider lane pauses `quota:provider:<p>:*` (T6, 2026-10-21) | config, db | runner.session, runner.main |
| `src/runner/writeback.py` | Classify whether a session needs a CHANGELOG follow-up | — | runner.main |
| `src/runner/review.py` | Code-review sub-agent; evaluates diffs post-session (Anthropic belt 2) and PRE-push for non-Anthropic lanes (T5 gate: `diff_for_gate`, fixed reviewer) | config, audit_log, claude_agent_sdk | runner.main, runner.session |
| `src/runner/events.py` | Event-trigger rules engine (4th async task) | db, models, gateway.jobs | runner.main |
| `src/runner/mcp_projects.py` | MCP server: project tools (list, get, logs, restart) | config, db, models | runner.session |
| `src/runner/mcp_dispatch.py` | MCP server: job enqueue tool (task/parent linkage + depends_on deferral) | gateway.jobs, db, models | runner.session |
| `src/runner/retention.py` | Audit log rotation (compress + archive old JSONL) | config | server-upkeep skill |
| `src/runner/audit_index.py` | Build INDEX.jsonl for fast job lookup by skill/status/keyword | config | server-upkeep skill, self-diagnose skill |
| `src/runner/retrospective.py` | Auto-tuning rollup queries (skill performance stats + context consumption) | config, db, models | review-and-improve skill, gateway.web |
| `src/runner/proposals.py` | Proposal tracking helpers (pure + async DB ops); dedup/merge-stamping in review-and-improve + server-patch. NOTE: there is no `/proposals` Telegram command yet — pending server-code proposals have no user-facing surface (EVALUATION_2026-07-28 U-backlog) | db, models | review-and-improve skill, server-patch skill |
| `src/runner/learning.py` | Post-session `settings.utility_model` classifier; enqueues `_learning_apply` child jobs when a completed job reveals a reusable learning | claude_agent_sdk, audit_log, config, gateway.jobs, db, models | runner.main |
| `src/context/module_graph.py` | Parse SYSTEM.md module graph; dependency detection + import validation | — | runner.session, scripts/lint_docs.py |
| `src/registry/skills.py` | Load SKILL.md frontmatter (`SkillConfig.provider`/`.model_id` derived via registry.models) | config, registry.models | runner.session |
| `src/registry/models.py` | Provider/model registry from repo-root `models.yml`: `[provider/]model_id` parse + alias resolution, fail-closed `ProviderRefused` (T1, 2026-10-21) | config | registry.skills, runner.session, runner.main, gateway.web, gateway.telegram_bot |
| `src/registry/manifest.py` | Load project manifest.yml | config | register-project.sh, healthcheck |
| `src/gateway/jobs.py` | Shared enqueue/cancel/find helpers + `ORIGIN_CHANNELS` / `origin_from_created_by` | db, models | web, telegram_bot, notify.outbox |
| `src/gateway/web.py` | FastAPI: /api/jobs + dashboard + retrospective routes (+ per-project delivery contract on /api/projects) | config, db, models, gateway.jobs, audit_log, registry.models, runner.retrospective, runner.delivery | (entry point) |
| `src/gateway/telegram_bot.py` | Telegram commands + NL-first plain-text asks + task/plan notification cards | config, db, models, gateway.jobs, audit_log, registry.models, runner.router, runner.plans | (entry point) |
| `src/notify/outbox.py` | Notifications outbox (A4, 2026-10-21): `Notice`, kind vocabulary, card eligibility (`should_notify_job`), `lane_label`, job/task/ops builders, `enqueue_notice` (always inserts — the switch is the bot's), claim/lease, retry math, `mark_*` | db, models, audit_log, gateway.jobs | runner.main (A5), gateway.telegram_bot (A6), notify.__main__ |
| `src/notify/telegram.py` | Telegram renderer (4096 / 64-byte / 8-button limits, no parse_mode), `send_via_bot`, `send_via_http`, `TelegramSendError` (token chokepoint) | — | gateway.telegram_bot (A6), notify.__main__ |
| `src/notify/__main__.py` | `python -m src.notify send` / `drain` for launchd alerters, the canary and ops; mirrors the bot's legacy_mode | config, notify.outbox, notify.telegram | scripts/healthcheck-all.sh + schedule-monitor.sh (A7), credential canary (E10) |
| `scripts/register-project.sh` | Project registration: manifest → Caddy + launchd + DB | yq, caddy, psql | — |
| `scripts/healthcheck-all.sh` | Probe all projects, update `last_healthy_at` | yq, curl, psql | — |
| `scripts/schedule-monitor.sh` | Schedule-adherence watchdog: DARK/NEVER_RAN/STUCK/FAILURE_STREAK findings → owner DM; writes `volumes/telemetry/schedule_adherence.json` | runner.schedule_adherence, curl | — (daily 07:15 launchd timer, out-of-band) |
| `scripts/backup.sh` | Nightly pg_dump + audit log + log snapshot | psql, tar | — (launchd timer) |
| `scripts/seed-schedules.sh` | Insert canonical schedules into DB | psql | server-deploy skill (step 3b, every deploy) |
| `scripts/seed-module-skills.sh` | Ensure every `.context/modules/<x>/` has `skills/{GOTCHAS,PATTERNS,DEBUG}.md` stubs | — | bootstrap.sh + test_doc_lint.py |
| `scripts/lint_docs.py` | Validate registries vs actual files; catches stale docs | context.module_graph | tests/test_doc_lint.py |
| `scripts/sync-learnings.sh` | Publish runtime doc drift → origin/runtime-learnings (plumbing; prod-side) | git | — (hourly launchd timer) |
| `scripts/codex-canary.sh` | T10 live canary of the Codex executor: throwaway clone under `CANARY_ROOT` (never the repo / prod / volumes), real `codex exec` via `codex_cli.main --canary`, then the Anthropic gate dry-run; results → plan §8 | runner.executors.codex_cli, git, pipenv | — (manual; the one place that spawns the real CLI) |

## Data flow

```
Telegram message (bare text or /task) → bot (validates chat_id; triage:
  question→chat, else task; creates Task+Job, RPUSH jobs:queue)
                                                        ↓
Runner: BLPOP → Job row → resolve skill (rule → LLM fallback → generic;
  multi-step asks → `plan`) → resolve cwd → resolve isolation tier
  (none | workspace | host) → per-job workspace clone + guard hooks if
  workspace-tier → in-process Agent SDK session (subagents from frontmatter) →
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
- **Migrations**: Alembic, eight files (`001_initial` … `007_provider_columns`,
  `008_p0_observability`). Tables: `jobs`, `schedules`, `projects`, `proposals`,
  `tasks`, `task_turns`, `notifications` (+ `alembic_version`).
  `tests/test_migrations.py` keeps the chain consistent and asserts the on-disk
  chain equals `alembic/applied_history.txt` (append the id in every migration
  commit; never revert a migration file without `alembic downgrade -1` on prod first).

## Invariants (hard rules)

| ID | Invariant | Enforced in |
|---|---|---|
| INV-1 | Every session has a resolved model, effort, permission_mode | `runner/session.py:_build_options` |
| INV-2 | Every job writes `job_started` + one terminal event to audit log (exception: pre-execution rejections — preflight failures and the deploy-authority gate — write only the terminal event; reconcile keys off the terminal event, so no orphan) | `runner/main.py:_process_job` |
| INV-3 | Server uses subscription auth; `ANTHROPIC_API_KEY` is never set | `runner/main.py:_check_subscription_auth` + `scripts/run.sh` |
| INV-4 | Server code merges autonomously only with gate-green + agent code-review LGTM + owner notification (owner decision 2026-07-31, generalizing the 2026-07-28 deploy-hotfix lane); protected paths (PROTOCOL.md, auth config, deletions, guards.py, lint_docs.py, MISSION §M, ORG.md safety-principle section, the lane's own executor skills) always require owner approval | `server-patch`/`new-skill` SKILL.md flow + INV-13 post-review + readonly guard hooks; `server-deploy` § Self-healing |
| INV-5 | Write-back verification runs after every session that modified code | `runner/main.py` post-session hook (Phase 4+) |
| INV-6 | Only whitelisted chat IDs can submit jobs via Telegram | `gateway/telegram_bot.py:_guard` |
| INV-7 | Only auth'd web requests can submit jobs | `gateway/web.py:_check_auth` |
| INV-8 | Cancel requests honored within 2s | `runner/main.py:_cancel_listener` |
| INV-9 | Job status transitions are valid; a user `cancelled` is never overwritten by a trailing finish (the cancel-race) | `_finish_job` guards `WHERE status != 'cancelled'` + rowcount check |
| INV-10 | Skills in `plan` mode cannot write files | SDK-level permission_mode |
| INV-11 | Audit logs are append-only | filesystem O_APPEND in `audit_log.append` |
| INV-12 | Quota exhaustion pauses queue until reset; jobs requeued at front (global/Anthropic only; a paused non-Anthropic lane holds its jobs to the TAIL — T6, plan §4g) | `runner/main.py:_process_job` |
| INV-13 | Code-touching skills require a `code-review` sub-agent LGTM **in-session, before push** (that is the merge gate). `main._maybe_review` is a SECOND belt that runs post-session, after the push, and only FLAGS: it stamps `review_outcome` (job stays `completed`) and on blocker/error emits `post_review_flagged` + a task DM — it does NOT park or fail the job. (Behavior weakened 2026-08-05; row corrected to match 2026-08-31 — restoring a fail-closed pre-push gate in code is an open owner decision, see EVALUATION_2026-08-30 F4.3.) | in-session `code-review` subagent per skill SKILL.md; `main._maybe_review` + `review.run_code_review` (flag-only) |
| INV-14 | Project slugs unique; port allocations never reused | `registry/manifest.py` + `projects/_ports.yml` |
| INV-15 | On startup the runner reconciles orphaned `running` jobs (fail-only) AND re-queues `queued` rows with no Redis entry, before consuming the queue; the job loop holds a concurrency slot before BLPOP so ids are never parked in-process | `runner/reconcile.py` + `runner/main.py:main`/`_job_loop` |
| INV-16 | Code-writing skills (`isolation: workspace`) never run in a shared checkout — one throwaway clone per job; work leaves only via git push | `runner/workspaces.py` + `runner/session.py:run_session` |
| INV-17 | Workspace-tier sessions are guard-hooked: file writes outside the per-job clone and dangerous host commands (sudo, launchctl, keychain, force-push, kills, API-key injection, destructive ops on protected roots) are DENIED at PreToolUse — hooks fire before permission evaluation, so this binds even under bypassPermissions. Denials are audited (`guard_denied`). (Redefined 2026-07-27; formerly the container-env rule.) | `runner/guards.py` + `runner/session.py:_build_options` |
| INV-18 | `god` is the ONLY `isolation: host` skill — the deliberate break-glass lane for phone-initiated server fixes; `kind=god` is rejected by the dispatch MCP and by `/task --kind=god` (Telegram `/god` is the single door). HONESTY NOTE: `isolation: none` is host-EQUIVALENT at runtime (no clone, no guard hooks) and is the default for ~44 skills including the ops skills (`server-deploy`, `*-redeploy`) that legitimately operate on the live checkout — lint freezes that set as an explicit debt register so new write-capable skills must isolate or be consciously allowlisted | `skills/god/SKILL.md` + `scripts/lint_docs.py` (isolation checks) + `runner/mcp_dispatch.py` + `gateway/telegram_bot.py` |
| INV-19 | A task auto-closes only on an `_evaluate` EVAL_PASS backed by evidence; the user can always overrule via Reopen | `runner/main.py:_handle_evaluator_result` + bot `reopen` action |
| INV-20 | `privilege_class: read-only` is hook-enforced at runtime: file-mutation tools, mutating Bash, and `restart_project` are PreToolUse-denied for such sessions regardless of permission_mode (dispatch via enqueue_job stays allowed) | `runner/guards.py:make_readonly_guard_hooks` + `runner/session.py:_build_options` |
| INV-21 | A non-Anthropic executor runs ONLY (a) at `isolation: workspace`, under its vendor sandbox (Codex Seatbelt `workspace-write`, network off — writes confined to the per-job clone; reads are NOT confined until the dedicated-user materialisation lands, plan §6 D-C) with an env scrubbed to `{PATH, HOME, LANG, TMPDIR, CODEX_HOME}` (never `env_files`, never a server/vendor/broker/Telegram secret), no MCP and no subagents; (b) on lanes the router may route: never `code-server` skills (`server-patch`, `server-deploy`, `new-skill`, `deploy-director`, `atlas-redeploy`, `project-redeploy`) nor a canonical inside this repo unless `ROUTER_CODE_SERVER_PROVIDERS` lists the provider (plan D-A, default `anthropic`), never review/evaluate — Anthropic stays the trust anchor: every non-Anthropic diff passes the **pre-push Anthropic review gate** (`code-review` protocol over the clone diff, LGTM or nothing lands) and the runner — never the vendor — commits (`Executor:`/`Job:` trailers) and pushes; a scheduled routine moves provider only by skill pin, a payload override is owner-origin only; (c) under the free-tier-only spend rule (owner decision 2026-08-17: OpenRouter free tiers, unpaid Gemini key, Codex Free) with provider credentials never session-assignable (`guards.py` denies assignment/export of `OPENAI_API_KEY|CODEX_API_KEY|GEMINI_API_KEY|OPENROUTER_API_KEY|XAI_API_KEY|CLAUDE_CODE_OAUTH_TOKEN` beside `ANTHROPIC_API_KEY`); its rate limits pause its own lane only (INV-12 stays Anthropic's). Ships dark: `ROUTER_PROVIDERS_ENABLED=anthropic` refuses every other provider fail-closed. Defined in `docs/superpowers/plans/2026-08-10-model-router.md` §8 (APPROVED 2026-08-17); implemented by the cross-vendor writer slice (`docs/superpowers/plans/2026-10-21-cross-vendor-writer-slice.md`), this row rewritten by its protected bundle (T8) | `registry/models.py:resolve_enabled` (C12 fail-closed) + `runner/session.py:lane_refusal`/`canonical_refusal`/`_pre_push_gate` + `runner/executors/codex_cli.py:scrubbed_env`/sandbox argv + `runner/workspaces.py:publish_workspace` + `runner/quota.py` per-provider keys + `scripts/lint_docs.py` checks 14-15 (pins resolve, non-Anthropic ⇒ workspace, code-server pinned by setting, code-server set of record) + `runner/guards.py` provider-credential deny (both profiles); tests `test_provider_dispatch`, `test_pre_push_gate`, `test_codex_executor`, `test_quota`, `test_doc_lint`, `test_guards` |
| INV-22 | No ai-server skill/session/task ever places, modifies, or cancels a brokerage order. The single order path in the system is the atlas swing vertical's deterministic executor behind its risk kernel (owner-accepted 2026-08-30), sandbox-pinned until the owner's `swing/LADDER.md` funding gate; the value vertical is advisory-only; brokerage creds live only in the atlas project env; any new/widened order path is a protected-path change (owner-approval-only) | `MISSION.md` §M (INV-22) + atlas `swing/CLAUDE.md` rules 1–3 + kernel grep-tripwires + atlas-side test gates; server-side code deny is an open follow-up |

## Environment & setup

```bash
# Once, during bootstrap:
claude login          # subscription auth (SDK sessions use these credentials;
                      # the SDK ships its own bundled CLI for execution)
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
- **Quota detection is typed-first** (2026-07-27): `RateLimitEvent` from the SDK
  drives pause/requeue (`quota.detect_from_rate_limit`); the string heuristic
  remains as fallback for error text that arrives outside the typed channel.
- **SDK pinned to 0.1.x** (`>=0.1.81,<0.2` — pyproject.toml is authoritative). The 0.2.x line exists on PyPI —
  upgrading is a deliberate follow-up with its own verification pass, never a
  side effect of other work.
- **SDK sandbox (macOS Seatbelt) not yet enabled** — `ClaudeAgentOptions.sandbox`
  is available and would add OS-level Bash confinement on top of guard hooks;
  needs per-skill tuning (git/network flows) before turning on.
- **Dashboard has SSE streaming** — `/api/jobs/{id}/stream` provides live job
  tailing via EventSourceResponse (shipped Phase 6).
- **Pure-function unit tests + local-git integration tests** (~640 test
  functions, ~1250 collected with parametrization; sub-second collect, no
  network). Don't hardcode the count elsewhere — run
  `pipenv run pytest --collect-only -q` when a number is needed. DB-backed
  tests are opt-in via `AI_SERVER_RUN_DB_TESTS=1`. SDK-mock integration tests
  remain deferred.

## Hosting

- **Domain**: `chrispiserchia.com` (Cloudflare Registrar)
- **Tunnel**: Cloudflare named tunnel `ai-server`, config at `~/.cloudflared/config.yml`
- **Reverse proxy**: Caddy at `$PROJECT_ROOT/Caddyfile` + `Caddyfile.d/*.conf`
- **Per-project supervision**: `~/Library/LaunchAgents/com.assistant.project.*.plist`
- **Healthcheck**: `scripts/healthcheck-all.sh` every 5 min via `com.assistant.healthcheck-all.plist`
- **Project registry**: `.context/PROJECTS_REGISTRY.md` (index) + per-project `.context/CONTEXT.md`

See `.context/modules/hosting/CONTEXT.md` for the full manifest schema and documentation standard.

## Active workstreams

All 8 phases shipped (see MISSION.md phase map). Historical trackers:
`docs/EVALUATION_2026-07-10.md` (T1–T17, done), `docs/EVALUATION_2026-07-28.md`
(remediation tracker, done). **Current audit: `docs/EVALUATION_2026-08-30.md`**
(third-party "grokbot" evaluation + 2026-08-31 remediation disposition).

Live workstreams as of 2026-08-31:

- **Atlas living loops** — evaluate/build/gap-scout/momo/trader/advisors/
  k401/swing/value verticals on schedules (see `scripts/seed-schedules.sh`,
  the single schedule writer).
- **Trading-bots verticals** — BUILT 2026-08-30 (spec
  `docs/superpowers/specs/2026-08-27-two-trading-bots-design.md`); armed
  pending owner P0 (Tradier sandbox tokens, funding). Bounded by INV-22.
- **Isolation/queue debt** — F1/F2 remediation landed 2026-08-31; remaining:
  privilege_class backfill vs charters, server-side INV-22 code deny,
  INV-13 fail-closed restore (owner decision).
- **Model router** — plan APPROVED 2026-08-17 (INV-21); the 2026-09-25
  multi-model spec was cut 2026-10-05, then its Codex-executor slice was
  BUILT 2026-10-21 on branch `multi-model/cross-vendor-writer`
  (`docs/superpowers/plans/2026-10-21-cross-vendor-writer-slice.md`: registry
  + `models.yml`, migration 007, `executors/codex_cli.py`, dispatch, pre-push
  Anthropic gate, per-provider quota keys, surfaces). Ships dark —
  `ROUTER_PROVIDERS_ENABLED=anthropic` refuses every non-Anthropic job until
  the owner flips it (plan §7). The INV-21 row above carries the
  implemented profile — rewritten by the owner-merged protected bundle
  (plan T8, branch `multi-model/protected-bundle`, 2026-10-21), together
  with lint checks 14-15 and the guards.py provider-credential + INV-22
  broker-order denies.
