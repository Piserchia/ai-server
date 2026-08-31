# 2026-08-30 Evaluation Remediation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (inline execution chosen — many tasks touch shared files).

**Goal:** Validate and remediate the confirmed findings of `~/Downloads/ai-server-evaluation-2026-08-30.md` (grokbot), then redeploy.

**Architecture:** Fail-closed hardening of the skill registry / isolation / dispatch surfaces, queue-honesty fixes in runner+web+scripts, topology/doc truth restoration. No live-money implementation. All code born in the dev checkout, shipped via origin/main + deploy autopilot.

**Spec:** `docs/EVALUATION_2026-08-30.md` (the evaluation itself, imported in T-docs).

## Validation verdicts (evidence gathered 2026-08-31 09:23–09:45 ET)

| Finding | Verdict | Notes |
|---|---|---|
| F1 isolation/dispatch holes | **CONFIRMED** | 44/64 `none`; payload promotes isolation (`session.py:854`); unknown tier → `none`; MCP `enqueue_job` takes arbitrary kind+payload → any dispatcher can spawn `kind=god`; `/task --kind=god` works; YAML parse error fail-opens to FULL default toolset (`skills.py:_parse_frontmatter`); 3 skills unparseable |
| F2 queue/status lies | **CONFIRMED** | run.sh PID-only; BLPOP-before-semaphore (`main.py:157`); reconcile heals `running` only; `/health` = Redis LLEN only; 1×`succeeded` + 3 stuck `deferred` (parent marked `succeeded` → promotion never fired). Starved deploy from eval has since landed (prod @ 7f4854c) — design hole stands |
| F3 dual-checkout leaks | **CONFIRMED** | ~10 unmerged runtime-learnings commits incl. prod-born SKILL.md contract edits (chat permission_mode, momo gotchas); sync-learnings allowlist has `skills/*/*.md`; prod tree dirty; runtime atlas clone @ 97bde6b missing `advisors/`+`tradingcore/` (sibling @ a0df995 = origin/master); nested stale atlas + market-tracker leftovers; `.env.example` `/Users/chris` |
| F4 doc/invariant drift | **CONFIRMED** | SERVER.md "3 tables/1 migration/no auto-merge ever"; SYSTEM.md 289+/0.1.63/no INV-21; README ~750 vs 1247; INDEX "always PR-gated" |
| F5 mission/Atlas drift | **CONFIRMED with update** | MISSION has zero trading mentions. BUT: swing/value verticals were BUILT 2026-08-30 (owner-accepted spec v3, T1–T17 executed, sandbox-pinned, kernel-gated) — eval predates this. Ceiling must codify the kernel-only order path, not ban implementation. Kind spellings already normalized by `_resolve_skill` (dash/underscore) — cosmetic only. seed-schedules missing `atlas-daily-brief` + `atlas-weekly-reports`. |
| F6 Pipfile.lock | **CONFIRMED** | gitignored line 17; dev/live differ |
| F7 ops holes | **CONFIRMED** | atlas binds `*:8791`; bot.err.log 47MB (httpx INFO); cloudflared undocumented; KeepAlive semantics; self-diagnose already breaker-limited (events.py) — partially mitigated already |

New since eval: 64 skills / 33 schedules (swing+value verticals landed 7f4854c); uncommitted finished build-session work in dev (spec status, R18 watchdog, INDEX/CHANGELOG/supervise-status).

## Global constraints

- Work only in dev checkout; never hand-edit prod `src/`.
- No live-money/trading implementation in this pass.
- Protected paths touched (MISSION.md §M, lint_docs.py) — authorized by the owner's direct remediation instruction this session; call out in summary/notification.
- Every push: gates green (pytest + lint_docs), no secrets in diff, CHANGELOGs updated, fetch+merge before push, code-review LGTM before merge to main.
- Never delete a project dir: stale leftovers are **quarantined by rename**, not deleted.

## Tasks

### T0 — land in-flight work (tree hygiene)
- [x] T0.1 `git merge origin/runtime-learnings` into dev main (absorbs prod-born chat/momo SKILL.md + GOTCHAS learnings). Resolve conflicts preferring runtime content for learning files.
- [x] T0.2 Commit the trading-build session's finished dirty files as their own commit: `.context/INDEX.md`, `.context/modules/hosting/CHANGELOG.md`, `docs/superpowers/specs/2026-08-27-two-trading-bots-design.md`, `scripts/healthcheck-all.sh`, `skills/atlas-swing-supervise/SKILL.md`. Leave `.claude/settings.local.json` uncommitted.

### T1 — fail-closed skill registry (F1.6)
- Files: `src/registry/skills.py`, `src/runner/session.py`, `skills/{atlas-chat,atlas-k401-review,atlas-portfolio}/SKILL.md`, `tests/test_skill_contracts.py`
- [x] Quote the 3 unparseable descriptions.
- [x] `_parse_frontmatter`: YAML error → raise `SkillFrontmatterError`; `load()` propagates (returns None only for missing file, raises on corrupt).
- [x] `_resolve_skill`: explicit kind (≠task/chat) whose skill is missing/corrupt → raise (job fails; no silent generic fallback).
- [x] Tests: corrupt frontmatter → load raises; all real SKILL.md files parse (regression guard).

### T2 — dispatch hardening (F1.3–5)
- Files: `src/runner/workspaces.py`, `src/runner/mcp_dispatch.py`, `src/gateway/telegram_bot.py`, tests.
- [x] `resolve_isolation`: payload may only tighten (`none→workspace`); payload `host` never honored; unknown tier → `workspace` (fail closed, warn).
- [x] `mcp_dispatch`: reject `kind` ∈ {god}; strip `isolation`/`permission_mode` from payload (audit-log the strip).
- [x] telegram `parse_flags`/`/task`: reject `--kind=god` (point at `/god`).
- [x] Generic unmatched task (`kind=task`, no skill): force `isolation: workspace`.

### T3 — queue honesty (F2)
- Files: `src/runner/reconcile.py`, `src/runner/main.py`, `src/gateway/web.py`, `scripts/run.sh`, tests.
- [x] Reconcile at startup: `queued` rows absent from Redis → re-RPUSH (audit event `queued_requeued`).
- [x] Acquire semaphore slot BEFORE BLPOP (slot passed into task; released on completion) — Redis no longer drained into in-process waiters.
- [x] `/health`: `queue_depth` = PG queued count; add `redis_llen`, `pg_running`, `pg_deferred`.
- [x] `run.sh`: when launchd units are loaded, `status` reports launchd state and `start` refuses.
- [x] Migration 006: repair `succeeded` → `completed`, add CHECK constraint on `jobs.status`.
- [x] One-off: cancel the 3 stale deferred atlas-report rows (SQL, after deploy).

### T4 — topology & deps (F3, F6, F7)
- [x] `scripts/sync-learnings.sh`: allowlist `skills/*/*.md` → `skills/*/{GOTCHAS,CHANGELOG,DEBUG,PATTERNS}.md` (SKILL.md contract edits no longer auto-published).
- [x] `.gitignore`: un-ignore `Pipfile.lock`; commit dev lock (prod syncs on deploy).
- [x] `.env.example`: `SERVER_ROOT` → `$HOME`-relative comment + correct user; concurrency comment (code default 4, live 2).
- [x] `scripts/seed-schedules.sh`: add `atlas-daily-brief` (0 12 * * *) + `atlas-weekly-reports` (0 18 * * 0, kind atlas-report-sweep).
- [x] `src/gateway/telegram_bot.py`: silence httpx INFO (getUpdates spam, 47MB err log).
- [x] Quarantine (rename, don't delete): `projects/atlas` → `projects/atlas.stale-20260731.quarantined`, `projects/market-tracker` → `projects/market-tracker.retired.quarantined` (dev tree only, gitignored paths).
- [x] `scripts/install-launchd.sh`: comment documenting the cloudflared system LaunchDaemon + KeepAlive semantics.

### T5 — docs truth (F4, F5)
- [x] `MISSION.md`: Atlas first-class statement; §M live-money ceiling INV-22 (orders only via atlas swing kernel/executor path, sandbox-pinned until owner LADDER gate; no ai-server skill places orders; brokerage creds never in server env; new order paths = protected change); §B/E rows marked on-demand (unscheduled).
- [x] `SERVER.md`: rewrite against live reality (launchd manager, 7 tables/6 migrations, concurrency 4-default/2-live, INV-4 merge lane, isolation truth, Redis keys, ollama note, cloudflared).
- [x] `.context/SYSTEM.md`: header, schema, test count, SDK pin, INV-13 actual behavior (flag-only post-hoc), INV-21 definition, INV-22 row, isolation reality, active workstreams.
- [x] `.context/INDEX.md` + `docs/README.md` + `README.md`: merge-lane wording, latest-eval pointer, dual-checkout setup, launchd status, test count.
- [x] `GETSTARTED.md`/`TEARDOWN.md`: unmissable historical banners.
- [x] Import eval → `docs/EVALUATION_2026-08-30.md` + disposition table; INDEX/docs README entries.
- [x] `scripts/lint_docs.py` extensions: frontmatter must parse; write-capable skills need explicit isolation; `host` allowlist; `none`+write-tools frozen allowlist (debt register); INV cross-ref MISSION/INDEX ↔ SYSTEM.md.
- [x] Module CHANGELOGs (runner, gateway) + CONTEXT.md updates for changed interfaces.

### T6 — gates & deploy
- [x] `pipenv run pytest` green (1301 passed); `lint_docs.py` green (17/17).
- [x] code-review agent LGTM (INV-4 lane) — first pass CHANGES_REQUESTED with 2 real catches (web kind=god door, subagent frontmatter crash), both fixed (27526e6) + tested; final verdict LGTM.
- [x] Secrets scan on unpushed diff: doc-only mentions, clean.
- [x] Prod tree cleaned pre-deploy (all dirt verified byte-identical to origin/runtime-learnings, which is merged into main).
- [x] SQL sweep: 3 stranded deferred rows cancelled (fadedf6e/f48d89f0/f1211d52); `succeeded` row repaired by migration 006 at deploy.
- [x] fetch+merge origin (incl. 13:58Z learnings), push main `7f4854c..da83b24`.
- [x] Deploy: deploy-director cc1a747b → server_deploy a637cb1a. Range landed (prod HEAD da83b24), migration 006 applied (`ck_jobs_status_valid` present, 0 `succeeded` rows), services restarted, prod tree clean. The executor job row reads `failed` with "exit code 143" — that is the deploy's own `launchctl kickstart` of the runner SIGTERMing its session (director predicted it; all post-conditions verified green independently). Two auto self-diagnose jobs followed; expected to conclude the same.
- [x] Runtime atlas clone: atlas-redeploy eb4fde33 completed — 97bde6b→a0df995, 4 atlas migrations, 7 gates green, `/advisors` + `/trading` routes live, healthcheck 200.
- [x] Post-deploy verify: `/health` shows `pg_queued/pg_running/pg_deferred/redis_llen` and 200 ok; `run.sh status` reports launchd truth; `POST /api/jobs kind=god` → 403 live; public probes green (health 200, atlas 302→app).
- [x] Incident during deploy: the FIRST scheduled `atlas-advisors-ingest` (Mon 10:00 ET) was SIGTERM-killed by the runner restart → re-dispatched manually with the schedule's full payload (job 8b7db322). Next scheduled: Thu 10:00.
- [x] Owner notification: session summary (this session IS the owner channel) — protected paths touched under direct owner instruction: MISSION.md §M (+INV-22, tightens), scripts/lint_docs.py (+4 checks, tightens), skills/server-deploy/SKILL.md (sync against committed lock).

## Deferred (explicitly not this pass)
- INV-13 restore to pre-push fail-closed review (behavioral policy decision — documented as flag-only instead; owner call to restore).
- Atlas `*:8791` → loopback bind (needs atlas-side config; flagged to owner).
- `mac-mini-ai-server` archive deletion (owner-gated).
- content-forge GitHub remote / bingo delivery block (creates external repos — owner call).
- JobKind enum overhaul; DB kind-spelling backfill (cosmetic; `_resolve_skill` already normalizes).
- privilege_class full backfill on all skills (charter-driven sweep — follow-up; lint now enforces frontmatter parse + isolation labels).
- BLPOP durable-claim redesign beyond semaphore-first + startup heal.
- Live trading arming (owner P0: Tradier sandbox tokens, funding).
