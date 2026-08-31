# SERVER.md — Architecture overview

> Rewritten 2026-08-31 against the live machine (EVALUATION_2026-08-30 F4 —
> the previous version had frozen at ~2026-07-30 and contradicted MISSION.md
> and the running system on merge policy, schema, and concurrency).

Personal assistant server running on a Mac Mini (`AlfredblersMini`, macOS user
`alfredbot.ai.butler`). Accepts tasks via Telegram or web, runs them through
the Claude Agent SDK on subscription auth, hosts resulting projects on a
single public domain — and carries **Atlas**, a first-class hosted
finance/markets product org (see MISSION.md).

## Six nouns

- **Job** — one unit of work. `kind`, `description`, `status`. Always has an audit log.
- **Skill** — a markdown file (`skills/<name>/SKILL.md`) that tells Claude how to do a kind of work. Data, not code. YAML frontmatter is the machine contract (model/effort/tools/permission_mode/isolation) — corrupt frontmatter fails the job (never silently defaults).
- **Project** — a hosted deliverable (static / service / api) with its own subdomain.
- **Schedule** — a cron expression that enqueues jobs on a recurrence. `scripts/seed-schedules.sh` is the single writer.
- **Manifest** — per-project YAML declaring how to run / host / update it (and, for delivery-contract projects, where code is born and how deploys are gated).
- **Audit log** — append-only JSONL of everything that happened on a job.

## Two checkouts (single-writer topology)

- **Dev** `~/Documents/repos/ai-server` — the ONLY birthplace of code/config
  commits. All src/scripts/alembic/skill-frontmatter work happens here.
- **Prod** `~/Library/Application Support/ai-server` — pull-only deploy
  target; launchd's WorkingDirectory. The only writes born here are runtime
  doc learnings (GOTCHAS/CHANGELOG/PATTERNS/DEBUG + Troubleshooting),
  auto-published hourly to `origin/runtime-learnings` by
  `scripts/sync-learnings.sh` and merged back into main from dev.

See CLAUDE.md § single-writer topology for the full rules and push gates.

## Process topology

**launchd owns the processes** (`~/Library/LaunchAgents/com.assistant.*`,
WorkingDirectory = the prod checkout). `scripts/run.sh` is dev-only: when the
launchd units exist it reports launchd status and refuses `start`. Restart a
service with `launchctl kickstart -k gui/$UID/com.assistant.<name>`.
KeepAlive is `Crashed=true, SuccessfulExit=false` — a crash restarts, a clean
exit stays down (deliberate).

- **runner** (`src/runner/main.py`) — consumes `jobs:queue`, spawns Agent SDK sessions, writes audit logs. Contains the scheduler, cancel-listener, and event loop as async tasks. Acquires a concurrency slot before popping Redis; heals stranded rows at startup.
- **web** (`src/gateway/web.py`) — FastAPI; `/api/jobs` REST + dashboard on localhost:8080; unauthenticated `/health` (published at `health.chrispiserchia.com`).
- **bot** (`src/gateway/telegram_bot.py`) — Telegram polling + done notifications; chat-ID allowlist.
- **caddy** (`com.assistant.caddy`) — reverse proxy on :80 only; TLS terminates at Cloudflare. Per-project vhosts in `Caddyfile.d/`.
- **cloudflared** — named tunnel `ai-server`, installed as a **system LaunchDaemon** (`/Library/LaunchDaemons/com.cloudflare.cloudflared.plist`) — NOT installed by `scripts/install-launchd.sh`; a rebuild must re-install it by hand.
- **Homebrew services** — postgresql@15 (127.0.0.1:5432), redis (127.0.0.1:6379). An `ollama serve` also runs on this Mini (127.0.0.1:11434) for non-server experiments; the server itself does not depend on it today (the model-router plan may change that).
- **Per-project units** — `com.assistant.project.*` (atlas node app :8791, baseball-bingo :8790, content-forge :8792, plus atlas sidecars), `com.assistant.backup` (nightly), `com.assistant.healthcheck-all` (5-min probes + deploy autopilot + swing watchdog), `com.assistant.sync-learnings` (hourly).

Deploys are agent-run: commit in the dev repo → push `origin/main` → the
healthcheck **deploy autopilot** notices the pending range and dispatches a
`deploy-director` job (or send `/task deploy server` yourself) — the
self-healing `server-deploy` skill does the rest (ff-only pull, `pipenv sync`
against the committed lock, migrate, test gate, seed schedules, restart).

## Data stores

- **Postgres** (db `assistant`) — `jobs`, `schedules`, `projects`, `proposals`, `tasks`, `task_turns` + `alembic_version`. Six Alembic migrations (001–006); `jobs.status` is CHECK-constrained to the JobStatus enum.
- **Redis** — `jobs:queue` (BLPOP), `jobs:stream:<id>` (SSE), `jobs:cancel` (pub/sub), `jobs:done:<id>`, quota pause keys, `heartbeat:runner` (TTL ~15 min), `events:breaker`, circuit-breaker keys (`cb:...`).
- **Filesystem** — `volumes/audit_log/<job_id>.jsonl`, `volumes/workspaces/`, `volumes/logs/`, `volumes/state/deployed-sha-*`, `projects/<slug>/`, `skills/<name>/`.

## Auth

Subscription only. `claude login` once; the Agent SDK executes sessions via the
CLI bundled inside its own Python package using those stored credentials.
`ANTHROPIC_API_KEY` is explicitly unset in every process's environment and the
runner aborts at startup if it appears (INV-3).

## Session isolation (honest version)

Three tiers (`SKILL.md` frontmatter `isolation:`):

- **workspace** — per-job git clone (`volumes/workspaces/`) + PreToolUse guard
  hooks that hard-deny writes outside the clone and dangerous host commands,
  in-process, even under bypassPermissions. Fail-closed: no clone → job fails.
  All code-writing loop skills run here.
- **none** (the default) — no clone, **no guard hooks**; the session runs in
  the live checkout with its declared permission_mode. This is
  host-EQUIVALENT and is what the ops skills (`server-deploy`, `*-redeploy`)
  and most report skills use. Lint freezes the set of write-capable `none`
  skills as a debt register — new skills must isolate or be consciously
  allowlisted.
- **host** — `god` only (owner break-glass via Telegram `/god`; `kind=god` is
  rejected everywhere else).

Payloads can only TIGHTEN isolation (to workspace), never relax or promote;
generic unmatched `/task` runs are forced onto the workspace tier.

## Model defaults

- Global default: **Sonnet 4.6**.
- Skills override per-skill via YAML frontmatter in `SKILL.md`.
- Escalation rules (in frontmatter) promote (typically to an Opus tier) on failure.
- Routing: rule-based (`src/runner/router.py`), then LLM fallback
  (`llm_router`), then generic task (workspace-isolated). Atlas coverage in
  the rule table is thin (mostly redeploy) — scheduled atlas jobs carry
  explicit kinds instead.

## Concurrency

Code default 4 (`src/config.py`); **live prod runs 2** via `.env`
(`MAX_CONCURRENT_JOBS`) — owner headroom for direct Claude use. There is no
job priority lane yet: a weekly report fan-out can occupy both slots and delay
a deploy job (EVALUATION_2026-08-30 F2.5, open).

## Subscription quota behavior

Runner detects rate_limit / quota signals (typed SDK events first, string
heuristic fallback), pauses the queue until reset, requeues the current job at
the front. Telegram alert on pause and on resume.

## Invariants (enforced in code — and where they aren't)

See `.context/SYSTEM.md` for the full table, including which rows are code
hooks vs. skill-procedure vs. convention. Merge policy is **INV-4** (matching
MISSION §M): server code merges autonomously ONLY with gate-green + agent
code-review LGTM + owner notification; protected paths always need explicit
owner approval. Live money is **INV-22**: no order path exists on this server,
ever — see MISSION §M.

## What this server is NOT

- Not a general-purpose agent framework.
- Not multi-user. Single tenant, whitelisted chat IDs only.
- Not a replacement for Claude Code on your laptop for deep interactive work.
- Not highly available: one Mini, no failover; backups are nightly tarballs + off-site leg.
- Not a place where brokerage orders happen (INV-22 — the only order path lives in the atlas swing vertical behind its risk kernel, sandbox-pinned).
