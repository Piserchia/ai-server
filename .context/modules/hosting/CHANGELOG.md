# Changelog: hosting

<!-- Newest entries at top. Every session that modifies this module appends here. -->

## 2026-08-03 — healthcheck-all cadence-slip false positive (baseball-bingo, 44th recurrence)

**Files changed**: `docs/TROUBLESHOOTING.md` (recurrence note appended;
44+ occurrences counter bumped from 43+).

**Why**: self-diagnose fired for baseball-bingo unhealthy (`last_healthy_at`
age 21m09s at fire) though `/healthz` returned 200 in 6.1ms and `/` returned
200 in 5.4ms with full HTML on port 8790 (PID 71682 healthy).
`healthcheck.out.log` gap 13:47:17Z → 14:08:28Z (21-min slip, four missed
5-min ticks). `com.assistant.healthcheck-all` was not actively running (PID
`-`); kickstarted inline via `gui/$(id -u)/com.assistant.healthcheck-all`.
Cadence resumed 14:29:52Z, both baseball-bingo and atlas `last_healthy_at`
refreshed to 7s old (single kickstart, both projects refreshed —
shared-cadence pattern reinforced). No prevention patch landed yet;
`events.py` live-probe gate and `healthcheck-all.sh` psql-exit-status
surfacing both remain un-landed.

## 2026-08-03 — healthcheck-all cadence-slip false positive (atlas, 39th recurrence)

**Files changed**: `docs/TROUBLESHOOTING.md` (recurrence note appended;
39+ occurrences counter bumped from 38+).

**Why**: `_check_project_health` in `runner/events.py` fired for atlas
(`last_healthy_at` age 35m at fire time) though the project answered
`/` HTTP 200 in 74ms on port 8791. `healthcheck.out.log` last tick
06:08:09Z — seven missed 5-min ticks in a row (06:13/18/23/28/33/38/43).
Kickstarted `gui/$(id -u)/com.assistant.healthcheck-all` inline;
cadence resumed 06:44:14Z, both atlas and baseball-bingo
`last_healthy_at` refreshed to ~2s. All three atlas launchd processes
(atlas / atlas-dash-scheduler / atlas-pm-edge, PIDs 24233/81428/81432)
were up continuously — same PID trio as recurrences 35–38, confirming
no atlas restart was needed. The prevention patch (live-probe gate in
`events.py:_check_project_health`) still un-landed — spec captured in
TROUBLESHOOTING.md and referenced in prior CHANGELOG entries.

## 2026-08-03 — healthcheck-all cadence-slip false positive (baseball-bingo, 27th recurrence)

**Files changed**: `docs/TROUBLESHOOTING.md` (recurrence note appended;
27+ occurrences counter bumped).

**Why**: `_check_project_health` in `runner/events.py` fired for
baseball-bingo (`last_healthy_at` age 21m43s) though the project answered
`/healthz` 200 in 8.5ms. `healthcheck.out.log` last tick 23:59:21Z —
four missed 5-min ticks in a row. Kickstarted
`gui/$(id -u)/com.assistant.healthcheck-all` inline; cadence resumed
00:21:19Z, `last_healthy_at` refreshed to 3s. No project restart
needed (that would be the only real downtime of the incident). The
prevention patch (live-probe gate in `events.py` `_check_project_health`)
remains unimplemented — job `f74b7415`.

## 2026-07-31 — Atlas goes GitHub-canonical; first live delivery contract (Phase E, atlas half)

**Files changed**: `.context/PROJECTS_REGISTRY.md` (atlas source + delivery
table → ACTIVE), `skills/atlas-redeploy/SKILL.md` (origin is GitHub; wording
for multi-machine commits), `docs/TROUBLESHOOTING.md` (atlas divergence
section: correct origin is now the GitHub URL). Same-day follow-up — the
every-session multi-machine procedure: root `CLAUDE.md` (push-gates dev-repo
wording), `.context/PROJECT_PROTOCOL.md` (§1.4 rebase-before-work, §4.2
delivery-branch push), `skills/app-patch/SKILL.md` (STEP 0 rebase-first);
mirrored in atlas `CLAUDE.md` §Working-on-this-repo + `docs/DEVELOPMENT.md`
(surfaces + checklist). Non-repo state changes on the
Mini (owner-directed in an interactive session): runtime clone
`projects/atlas` origin repointed local-path → `https://github.com/Piserchia/atlas.git`;
the stale dev-checkout copy `~/Documents/repos/ai-server/projects/atlas`
repointed + fast-forwarded 99 commits.

**Why**: owner decision 2026-07-31 — develop atlas from multiple machines.
GitHub `Piserchia/atlas` (master) is the source of truth; single-writer is
superseded by rebase+push single-branch integration (atlas CLAUDE.md
§Deployment topology, atlas `docs/DEVELOPMENT.md`). The atlas manifest now
carries the `delivery:` block (dev-repo topology, pull-only runtime,
gated-auto) — the first project on the 2026-07-27 segregation contract, so
runner enforcement (cwd scoping + deploy-authority gate) is live for atlas.

**Verify**: `git -C "$HOME/Library/Application Support/ai-server/projects/atlas"
remote get-url origin` → GitHub URL; `pipenv run python -c "from pathlib import
Path; from src.registry.manifest import load;
print(load(Path.home()/'Documents/repos/atlas/manifest.yml').delivery.topology)"`
→ `dev-repo`; next `/task redeploy atlas` pulls from GitHub ff-only.

## 2026-07-27 — Manifest `delivery` block documented (segregation Phase D)

**Files changed**: `.context/modules/hosting/CONTEXT.md` (manifest schema now
documents the `delivery` contract); `skills/new-project/SKILL.md` (scaffolds
dev-repo topology by default: canonical repo at `~/Documents/repos/<slug>`,
GitHub backup, pull-only `projects/<slug>` runtime clone, writes the delivery
block). No code change — the schema is parsed by `src/registry/manifest.py`
(Phase A). See `docs/superpowers/plans/2026-07-27-project-delivery-segregation.md`.

## 2026-07-12 — Commit-topology enforcement (post-incident hardening)

**Files changed**:
- `scripts/install-prod-hooks.sh` (new) — installs a pre-commit guard in the
  PRODUCTION checkout that blocks commits on main (path-gated so dev/copies
  are never affected). Bypass: `AI_SERVER_ALLOW_MAIN_COMMIT=1` (god
  break-glass; push-in-same-session mandatory per god SKILL.md).
- `scripts/sync-learnings.sh` — stray-commit safety net: unpushed commits on
  prod main are auto-published to `origin/runtime-rescue-auto` with loud
  guidance, so a stray commit can never strand work or block deploys again.
- `skills/server-deploy/SKILL.md` — step 2 re-arms the hooks every deploy
  (hooks are untracked, so this keeps them self-healing).
- `skills/god/SKILL.md` — "Committing from the host lane" section: doc
  learnings stay uncommitted; emergency code commits require immediate push.
- `CLAUDE.md` — enforcement paragraph + dev-side fetch-before-work rule.

**Why**: same-day incident — prod held one unpushed commit (`7e22db9`),
blocking the first ff-only deploy; separately dev's push was rejected because
GitHub main had moved (07-10 remediation wave). Both failure classes now have
structural enforcement, not just convention.

**How to verify**: in prod, `git commit` on main → blocked with guidance;
`bash scripts/sync-learnings.sh --dry-run` with a synthetic local commit
reports it; dev `git fetch && git merge origin/main` before push.

## 2026-07-12 — P0: sync-learnings script + launchd timer, server-deploy skill

**Files changed**:
- `scripts/sync-learnings.sh` (new) — publishes runtime doc drift (allowlist:
  `.context/**/*.md`, `skills/**/*.md`, `docs/Troubleshooting.md`) from the
  production checkout to `origin/runtime-learnings` via git plumbing
  (temp index + commit-tree) — HEAD, index, and working tree untouched, safe
  while the runner is live.
- `scripts/install-launchd.sh` — installs `com.assistant.sync-learnings`
  hourly timer (+ uninstall support).
- `skills/server-deploy/SKILL.md` (new) — the server's own deploy pipeline:
  sync learnings → stash doc drift → ff-only pull → deps/migrations →
  pytest gate → restart web/bot, runner restart detached (+20s).
- `CLAUDE.md` — Single-writer topology section (dev repo = code writer,
  production = learnings writer only).

**Why**: kill the manual "rescue runtime-written docs" workflow and give the
server the same gated deploy path atlas already had.

**How to verify**: in production: `bash scripts/sync-learnings.sh --dry-run`;
then `/task deploy server` after a dev commit.

## 2026-07-11 — Fix nightly backup: launchd PATH; stop tracking volumes/ artifacts

**Files changed**:
- `scripts/backup.sh` — Added explicit `PATH` export after `set -euo pipefail` so launchd sessions find `/opt/homebrew/opt/postgresql@15/bin/pg_dump`. Backup was silently failing with exit 127 since 2026-04 (EVALUATION_2026-07-10 §3.7).
- `.gitignore` — Replaced narrow per-file `volumes/` entries with a single `volumes/` blanket ignore. Removed `volumes/jobs.db` entry.
- `volumes/backups/backup-2026-04-17.tar.gz` — Untracked from git (was committed by accident; runtime artifact).

**Why**: Nightly pg_dump failed for ~3 months because launchd starts with `/usr/bin:/bin:/usr/sbin:/sbin` only. The old tarball sitting in git was discovered during the July eval.
**Verified**: Kicked `com.assistant.backup` after the fix; `backup-2026-07-11.tar.gz` (1.5 MB) created, `LastExitStatus=0`.

## 2026-07-10 — Next.js ISR gotcha documented

**Agent task**: Write-back for job bfcab76c — atlas skill suite refactor and new skills
**Files changed**:
- `.context/modules/hosting/skills/GOTCHAS.md` — Added entry: Next.js ISR routes need `dynamic='force-dynamic'` to avoid build-time pre-rendering failures

**Why**: A deploy (job `15bbc829`) hit a build-time pre-rendering failure on a route that depended on runtime data. Next.js pre-renders by default; adding `export const dynamic = 'force-dynamic'` forces server-side rendering per request and prevents stale/broken HTML in deployed pages.
**Side effects**: None observed
**Gotchas discovered**: Without `force-dynamic`, a build may succeed but serve stale or broken HTML at runtime.

## 2026-07-06 — External dead-man's-switch heartbeat

**Change**:
- `Caddyfile.d/health.conf` (new) — exposes only `/health` at
  `health.chrispiserchia.com` (all other paths 404), an unauthenticated public
  liveness URL for the external monitor.
- `ops/heartbeat-worker/` (new) — Cloudflare Worker with a Cron Trigger (`*/5 * * * *`)
  that polls the health URL and Telegram-DMs after 2 consecutive failures, with an
  all-clear on recovery. State in KV. Files: `wrangler.toml`, `src/index.ts`,
  `package.json`, `tsconfig.json`, `README.md`.

**Why**: Every in-process alerter (server-upkeep, done-DMs, quota) runs inside the
runner; if the runner/Mac/tunnel dies, silence looks like health. This monitor lives
off-box on Cloudflare's edge and closes that gap. Pairs with the meaningful `/health`
(gateway) + runner heartbeat (runner) landed the same day.

**Human one-time setup** (see `ops/heartbeat-worker/README.md`): route
`health.chrispiserchia.com` on the `ai-server` tunnel; `wrangler kv namespace create
HEARTBEAT_KV` and paste the id into `wrangler.toml`; `wrangler secret put
TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID`; `wrangler deploy`. Reload Caddy for the new
vhost (`caddy reload --config Caddyfile`).

**How to verify**: `curl -s https://health.chrispiserchia.com/health | jq` → 200;
`launchctl stop com.assistant.runner` → 503 within ~90s and a Telegram alert after two
Worker ticks (`wrangler tail`); restart → all-clear DM.

## 2026-07-06 — Off-site backup replication to Cloudflare R2

**Change**:
- `scripts/backup.sh`: after building the local tarball, replicate it off-disk to
  Cloudflare R2 (`r2:ai-server-backups/`) via `rclone copy`. The push is guarded —
  if `rclone` isn't installed or the `r2:` remote isn't configured it logs
  `offsite SKIP`; a failed upload logs `WARN` but never fails the local backup
  (the local copy remains the source of truth). Added `backup.sh` to this module's
  Paths line (hosting now owns operational scripts).
- `skills/server-upkeep/SKILL.md`: new step 8b checks off-site backup freshness
  (`rclone lsl r2:ai-server-backups`); DMs an anomaly if the newest remote object is
  > 48h old while rclone is configured. `offsite-not-configured` is not an anomaly.
- `skills/restore/SKILL.md`: new "Locating a backup" section documents pulling a
  tarball from R2 when the local disk/copy is gone.

**Why**: Verified gap — local backups, the Postgres DB, and the append-only audit-log
institutional memory all lived on the same 2TB SSD. A single disk/hardware failure
would erase all three at once, against the mission's continuity goal. Off-site
replication + a freshness alarm closes the loop so a silently-broken upload is noticed.

**Human one-time setup required** (not automatable, no secrets in repo):
`brew install rclone`; create R2 bucket `ai-server-backups` + a scoped API token;
`rclone config` a remote named `r2` (S3-compatible R2 endpoint). Until then the push
logs `offsite SKIP` and upkeep reports `not configured` — both non-fatal.

**How to verify**:
- `bash scripts/backup.sh` writes `volumes/backups/backup-<date>.tar.gz`; with R2
  configured, `rclone lsl r2:ai-server-backups/` lists it and `backup.log` shows
  `offsite OK`. With the remote removed, the local backup still succeeds and
  `backup.log` shows `offsite SKIP`/`WARN`.
- Running `server-upkeep` with no recent remote object flags a stale-backup anomaly.

**Side effects**: None on local backup behavior (fully backward-compatible). Adds a
soft dependency on `rclone` (brew) for the off-site leg only.

**Change**:
- `projects/baseball-bingo/manifest.yml` edited from `type: static`/`web_root: web-legacy` to `type: service` with `port: 8790`, `healthcheck: /healthz`, and a `start_command` that sources a project-local `.env` for `SESSION_SECRET` before launching `uvicorn web.main:app` via the ai-server virtualenv.
- Ran `bash scripts/register-project.sh baseball-bingo`. This regenerated `Caddyfile.d/baseball-bingo.conf` from `root * web-legacy` / `file_server` to `reverse_proxy localhost:8790`, generated `~/Library/LaunchAgents/com.assistant.project.baseball-bingo.plist`, loaded it with launchd (KeepAlive on crash, RunAtLoad), reloaded Caddy, and upserted the projects row with `type=service`, `port=8790`.

**Why**: Phase 3 of the Baseball Bingo migration plan. Phase 1 (2026-04-20) built the FastAPI backend; Phase 2 (2026-04-21) added groups/shared-cards/marks + SPA; Phase 3 flips the public URL from the legacy static HTML to the live FastAPI service.

**How to verify**:
- `launchctl list | grep baseball-bingo` shows a running PID.
- `curl -sL https://bingo.chrispiserchia.com/healthz` → `{"status":"ok"}`.
- `curl -sL https://bingo.chrispiserchia.com/` returns the SPA shell.
- `curl -sI https://bingo.chrispiserchia.com/static/app.js` → `HTTP/2 200 content-type: text/javascript`.
- End-to-end POST/GET API smoke against `bingo.chrispiserchia.com/api/session` → `api/groups` succeeded with a seeded 25-cell card payload.

**Side effects**:
- `web-legacy/` remains in the project for reference but is no longer served. The reverse_proxy catches all traffic.
- `SESSION_SECRET` is stored in `projects/baseball-bingo/.env` (gitignored). Losing that file invalidates every existing session cookie; regenerate and users must re-login.
- Caddy config is now `http://` only (tunnel handles TLS); reload via `caddy reload --config Caddyfile` is idempotent.

## 2026-04-20 — Fix silent healthcheck failure + `www.` redirect

**Change**:
- `scripts/healthcheck-all.sh`: prepend `/opt/homebrew/bin` (and friends) to PATH so launchd-invoked runs can find `yq`. Previously every 5-minute tick logged `checked=0` because `yq` wasn't on launchd's bare PATH and `yq '.slug'` returned empty, causing the script to skip every manifest.
- `Caddyfile`: add a `www.chrispiserchia.com → https://chrispiserchia.com` 301 redirect. Previously `www.` (and any unmatched subdomain hitting the tunnel wildcard) fell through to a Caddy empty-200 response.

**Why**: User reported "cloudflare site appears to be broken". Investigation showed `last_healthy_at` in `projects` table hadn't been updated for 3 days (market-tracker) / ever (bingo), because the cron healthcheck wasn't actually checking anything. Separately, `www.` returned blank.

**How to verify**:
- `bash scripts/healthcheck-all.sh` reports `checked=3 healthy=3 failed=0`.
- `psql assistant -c "SELECT slug, last_healthy_at FROM projects;"` shows a fresh timestamp on `market-tracker` within the last 5 min.
- `curl -sI https://www.chrispiserchia.com/` returns `HTTP/2 301` with `location: https://chrispiserchia.com/`.
- Logs `volumes/logs/healthcheck.err.log` stop getting `yq: command not found` appended.

**Gotchas added**:
- `.context/modules/hosting/skills/GOTCHAS.md` now documents the launchd-PATH trap for shell scripts and the "blank Caddy host" trap for unmatched subdomains.

## 2026-04-18 — Seeded skills/ subdirectory per Rec 3 (§ 7 Seed module skills/ dirs)

**Change**: This module now has `.context/modules/hosting/skills/` containing stub `GOTCHAS.md`, `PATTERNS.md`, and `DEBUG.md` files. Stubs were created via `scripts/seed-module-skills.sh`; no source code modified.

**Why**: PROTOCOL.md directs sessions to append learnings to these files, but four of five modules had no skills/ directory at all, discouraging write-backs. Creating the directories with format-header stubs removes the friction and gives future sessions a template to append to. See `docs/EVALUATION_2026-04-18.md` § 7 Rec 3.

**Side effects**: None on module behavior. New lint check `check_module_skills_dirs` in `scripts/lint_docs.py` verifies these files continue to exist.


<!-- Newest entries at top. -->

## 2026-04-17 — Phase 3: Initial hosting infrastructure

**Agent task**: Build the hosting layer — Cloudflare tunnel, Caddy, project registration, healthchecks.

**Files created**:
- `scripts/setup-tunnel.sh` — One-time Cloudflare named tunnel setup (interactive)
- `scripts/setup-caddy.sh` — One-time Caddy install + Caddyfile + launchd service
- `scripts/register-project.sh` — Idempotent project registration: reads manifest.yml, generates Caddy snippet + launchd plist(s) + DB row. Supports static, service, and multi-service projects.
- `scripts/healthcheck-all.sh` — Probe all projects every 5 min, update `projects.last_healthy_at`
- `Caddyfile` (generated by setup-caddy.sh) — Base config with dashboard routing + per-project imports
- `Caddyfile.d/` (generated by register-project.sh) — Per-project Caddy snippets

**Why**: Phase 3 goal is multi-project hosting on a single public domain. The scripts automate the full lifecycle: tunnel → Caddy → register project → healthcheck.

**Design decisions**:
- Multi-service projects (market-tracker has 3 Flask servers) get separate launchd plists per sub-service and Caddy handle blocks for path-based routing. This keeps each service independently supervised and restartable.
- Manifest schema includes `mission`, `web_strategy`, and `platforms` fields so the AI server can distinguish "this IS a web app" from "this has a web shim for a native app."
- Healthchecks read from manifest files (source of truth) rather than the DB.
