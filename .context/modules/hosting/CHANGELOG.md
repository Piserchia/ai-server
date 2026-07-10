# Changelog: hosting

<!-- Newest entries at top. Every session that modifies this module appends here. -->

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
