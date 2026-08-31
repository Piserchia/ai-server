# EVALUATION 2026-08-30 — third-party ("grokbot") holistic evaluation

> Imported 2026-08-31 from `~/Downloads/ai-server-evaluation-2026-08-30.md`
> during the same-day remediation session. The original text is preserved
> verbatim below the disposition table. Findings were independently validated
> against the repo and the live machine before any fix — every code-level
> claim checked out (one was already-mitigated, one was overtaken by events).

## Remediation disposition (2026-08-31)

| Finding | Verdict | Disposition |
|---|---|---|
| F1 isolation/dispatch (payload promotion, kind=god, YAML fail-open, 3 corrupt skills) | CONFIRMED | **FIXED**: registry raises `SkillFrontmatterError` (fail closed); 3 descriptions quoted; `resolve_isolation` tighten-only + unknown→workspace; dispatch MCP rejects kind=god and strips isolation/permission payload keys; `/task --kind=god` rejected; generic tasks forced to workspace. Deferred: per-skill relabeling of the 44 `none` skills to workspace (behavioral, needs per-vertical validation) — frozen as a lint debt register instead. |
| F2 queue/status lies | CONFIRMED | **FIXED**: slot-before-BLPOP; `requeue_stranded_queued()` at startup; `/health` reports PG backlog (`queue_depth`=pg_queued + `redis_llen`/`pg_running`/`pg_deferred`); `run.sh` launchd-aware (status truth + start refusal); migration 006 repairs `succeeded` + CHECK-constrains `jobs.status`; 3 stale deferred rows cancelled. Deferred: priority/reserved slot for deploy jobs (F2.5). |
| F3 dual-checkout leaks | CONFIRMED | **FIXED**: runtime-learnings merged into main (incl. prod-born chat/momo SKILL.md contract edits) + 3 untracked prod GOTCHAS rescued; sync-learnings allowlist narrowed to learning files (SKILL.md excluded); README documents dual-checkout + cloudflared gap; `.env.example` SERVER_ROOT fixed; nested stale atlas + market-tracker quarantined (renamed); runtime atlas clone caught up via gated atlas-redeploy. Deferred: content-forge off-site remote, bingo delivery block (owner calls). |
| F4 doc/invariant drift | CONFIRMED | **FIXED**: SERVER.md rewritten against live reality; SYSTEM.md header/schema/tests/SDK-pin/workstreams updated; INV-13 row corrected to actual (flag-only post-hoc) behavior; INV-21 defined; INDEX "always PR-gated" + model-router status corrected; GETSTARTED/TEARDOWN banners hardened; lint_docs extended (frontmatter parse, isolation labels, INV cross-refs). Deferred: INV-13 fail-closed restore in code (owner decision); privilege_class backfill vs charters. |
| F5 mission/Atlas/live-money | CONFIRMED (overtaken in part: swing/value verticals were owner-accepted and BUILT 2026-08-30, sandbox-pinned) | **FIXED**: MISSION states Atlas as first-class; §M gains INV-22 (kernel-only order path, sandbox-pinned, creds never server-side, new order paths = protected change); §B/E promises marked deliberately on-demand; seed-schedules absorbs atlas-daily-brief + atlas-weekly-reports. Kind spellings: `_resolve_skill` already normalizes dash/underscore — documented, no DB migration. Deferred: router rules for atlas NL, atlas-redeploy→project-redeploy migration, server-side INV-22 code deny. |
| F6 Pipfile.lock | CONFIRMED | **FIXED**: lock committed (prod graph), .gitignore updated, server-deploy syncs against the tracked lock (no more re-lock on prod). |
| F7 ops holes | CONFIRMED (self-diagnose already breaker-limited in events.py) | **PARTIAL**: cloudflared + KeepAlive documented (install-launchd header, README, SERVER.md); httpx INFO silenced (the 46MB bot.err.log source). Deferred: atlas `*:8791`→loopback bind (atlas-side change, owner-visible), log rotation infra, mac-mini-ai-server archive deletion (owner). |

---

# ai-server holistic evaluation and cleanup brief

**Date:** 2026-08-30, inspection window ~15:45–15:50 America/New_York  
**Audience:** another agent that will remediate. Do not "summarize and move on." Fix or explicitly defer each item.  
**Scope:** the `ai-server` personal-assistant stack on Chris's Mac Mini (`AlfredblersMini`), plus how Atlas, hosted projects, skills, docs, and runtime actually hang together.  
**Do not:** print, commit, or echo `.env` values, Telegram tokens, `WEB_AUTH_TOKEN`, Alpaca/Tradier keys, or any other secrets. You may check that a key *name* exists.  
**Do not:** implement the Tradier live-money trader as part of this cleanup. Containment first.  
**Do not:** clone the repo onto a new machine. Both checkouts already exist on the Mini. Work in the **dev** checkout unless a step says otherwise.

---

## 0. Where things live (use these paths, not guesses)

| Role | Absolute path | Git |
|---|---|---|
| Dev (only birthplace of code, per `CLAUDE.md`) | `/Users/alfredbot.ai.butler/Documents/repos/ai-server` | `main` @ `032a1ce` = `origin/main` |
| Live / prod (launchd `WorkingDirectory`) | `/Users/alfredbot.ai.butler/Library/Application Support/ai-server` | `main` @ `fa41afd`, **behind origin/main by 2** (`9d3ebcf`, `032a1ce`) |
| Atlas canonical (sibling) | `/Users/alfredbot.ai.butler/Documents/repos/atlas` | `master` @ `c27e550` (2026-08-30 14:31 ET). Has `advisors/`, `tradingcore/`, `trader/`, `momentum/`, `integrations/` |
| Atlas runtime clone (what Caddy serves) | `/Users/alfredbot.ai.butler/Library/Application Support/ai-server/projects/atlas` | `master` @ `97bde6b` (2026-08-28 06:20 ET). **Missing `advisors/` and `tradingcore/`** |
| Atlas nested leftover | `/Users/alfredbot.ai.butler/Documents/repos/ai-server/projects/atlas` | `master` @ `57461ed` (2026-07-31). Missing trader, momentum, integrations, advisors, tradingcore |
| Archived predecessor | `/Users/alfredbot.ai.butler/Documents/repos/mac-mini-ai-server` | still on disk months after "delete after a week" |
| GitHub | `https://github.com/Piserchia/ai-server.git` (dev/live), `https://github.com/Piserchia/atlas.git` | |
| Public domain | `*.chrispiserchia.com` via Caddy + cloudflared named tunnel `ai-server` | |

OS user is `alfredbot.ai.butler`, **not** `chris`. `.env.example` still has `SERVER_ROOT=/Users/chris/Library/Application Support/ai-server` (wrong). `src/config.py` default uses `Path.home()…/ai-server` (correct for this Mini).

`.env` exists in **both** checkouts, is gitignored (`.gitignore` line 2), and is **not tracked**. Do not commit it. Live `SERVER_ROOT` already points at Application Support.

---

## 1. What the project claims vs what it is

### Claimed identity (still in the anchoring docs)

- `MISSION.md` + `pyproject.toml` + `README.md`: single-tenant personal assistant on a Mac Mini. Natural language in via Telegram/web. Claude Agent SDK on **subscription auth** (never `ANTHROPIC_API_KEY`). Hosts resulting projects on one public domain. Self-manages with gated self-improvement.
- Explicit non-goals (`SERVER.md`, `MISSION.md`): not a general-purpose agent framework, not multi-user, not a laptop Claude Code replacement, not a silent self-improver, not fine-tuning. `SERVER.md:75`: "Not auto-merging server code changes. Ever."

### Actual identity on 2026-08-30

A working assistant **kernel** (runner + web + bot + Caddy + cloudflared + Postgres + Redis) **plus an Atlas product org**:

- **54 skills**, **26 of them (~48%) `atlas-*`**
- **23 schedule rows, none paused**; most are Atlas. Last 14 days of jobs are dominated by `atlas-report` (69 completions, many as `kind=task`) and `self-diagnose` (64).
- Newest accepted-direction spec: live Tradier swing auto-trader, "real money day 1" (`docs/superpowers/specs/2026-08-27-two-trading-bots-design.md`, v3 2026-08-30, status `ACCEPTED-DIRECTION`). Spec body still says "Nothing implemented yet." Sibling Atlas already has a `tradingcore/` directory (treat as scaffold, not live).
- `MISSION.md` §M safety ceilings: protected files, no project/skill deletion, no cloud deploy, no email, no social. **Zero mention of brokerage orders, live equity, Tradier, or Alpaca.** `grep -i trad MISSION.md SYSTEM.md SERVER.md` → empty.

If you "clean up" without rewriting the mission, sessions (especially `system-manager`, whose charter is MISSION) will keep optimizing for "host projects well," not "don't lose money."

---

## 2. Runtime snapshot (facts, not docs)

Inspected with machine-local commands on AlfredblersMini. No secrets.

### Processes that are actually up

`bash scripts/run.sh status` from **both** trees prints:

```
runner: not running
web: not running
bot: not running
```

That is a **false negative**. Launchd owns the processes. `volumes/pids/` is empty in both trees. `run.sh` only looks at PID files launchd never writes.

Launchd **user** agents, all `state = running`, cwd = Application Support:

| unit | notes |
|---|---|
| `com.assistant.runner` | pid ~10979, python `-m src.runner.main`, `runs = 3` |
| `com.assistant.web` | uvicorn `:8080` |
| `com.assistant.bot` | telegram_bot |
| `com.assistant.caddy` | Caddyfile in App Support; listen `*:80` + admin `127.0.0.1:2019`. **No :443** (TLS is the tunnel) |
| `com.assistant.project.atlas` | node `*:8791` (all interfaces, unlike bingo/forge) |
| `com.assistant.project.atlas-dash-scheduler` | running |
| `com.assistant.project.atlas-pm-edge` | running |
| `com.assistant.project.baseball-bingo` | uvicorn `127.0.0.1:8790` |
| `com.assistant.project.content-forge` | uvicorn `127.0.0.1:8792` |
| `com.assistant.backup` | last tarball `backup-2026-08-30.tar.gz` 04:00 ET; 51 backups |
| `com.assistant.healthcheck-all` | last `2026-08-30T19:47:04Z`: `checked=3 healthy=3 failed=0` |
| `com.assistant.sync-learnings` | hourly; publishes then "already published"; **working tree still dirty** |

**Not installed by `scripts/install-launchd.sh`, but running:**

- `cloudflared tunnel run` via **LaunchDaemon** `/Library/LaunchDaemons/com.cloudflare.cloudflared.plist`
- Homebrew `postgresql@15` on `127.0.0.1:5432`
- Homebrew `redis` on `127.0.0.1:6379`
- `ollama serve` on `127.0.0.1:11434` (not in `SERVER.md` topology)

Live unauthenticated `GET http://127.0.0.1:8080/health` → HTTP 200:

```json
{"status":"ok","runner_ok":true,"runner_heartbeat_age_s":1.7,"queue_depth":0,"db_ok":true,"redis_ok":true}
```

`queue_depth: 0` is Redis `LLEN jobs:queue`. At the same moment Postgres had **15 `queued` + 2 `running`**. The 2 running were `atlas-report` (NBIS `b97699ab`, NVDA `316228f5`). Among the queued: weekly atlas-report fan-out plus `deploy-director` job `5b0aefe0` created 14:51 ET (description cites `9d3ebcf`). Live `.env` `MAX_CONCURRENT_JOBS=2`. Quota pause key absent.

Alembic head **005** is applied. Live tables: `jobs, schedules, projects, proposals, tasks, task_turns` + `alembic_version`. `SERVER.md` still says "3 tables, 1 migration."

Auth: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ALLOWED_CHAT_IDS`, `WEB_AUTH_TOKEN` all SET in live `.env`. Unauth `GET /` and `/api/jobs` → 401. `ANTHROPIC_API_KEY` ABSENT; launchd unsets it; runner `_check_subscription_auth()` exits if set. `/health` is intentionally unauth and published at `health.chrispiserchia.com` via `Caddyfile.d/health.conf`.

Caddy vhosts (runtime `Caddyfile` + `Caddyfile.d/`):

| Host | Backend |
|---|---|
| `chrispiserchia.com` | `/api/*` → :8080; else static landing |
| `www.` | redirect to apex |
| `dashboard.chrispiserchia.com` | :8080 |
| `health.chrispiserchia.com` | **only** `/health` → :8080 |
| `atlas.chrispiserchia.com` | :8791 |
| `bingo.chrispiserchia.com` | :8790 |
| `content-forge.chrispiserchia.com` | :8792 |

---

## 3. Findings (largest first)

Each finding has: what's wrong, why it matters, evidence, and what to change. Do them in this order unless a later item is a dependency.

---

### F1. Isolation is a label, not a boundary (INV-18 is a word game)

**What's wrong**

- `lint_docs.py` enforces: only skill `god` may have `isolation: host`. That check is **syntactic**.
- Runtime: `src/runner/workspaces.py` `VALID_ISOLATION`; `src/runner/session.py` attaches PreToolUse guards **only when `isolation == "workspace"`**.
- Histogram across 54 `SKILL.md` files: **`none` 42 · `workspace` 11 · `host` 1 (`god`)**. `SkillConfig.isolation` default is `"none"`.
- `none` means: no clone, **no guards**, skill runs against whatever cwd the runner has (live Application Support checkout). Combined with `permission_mode: bypassPermissions` (39 skills).
- Host-equivalent without the `host` label:
  - `god`: `isolation: host`, Opus max, 200 turns, bypass, **no PreToolUse guards**. First-class Telegram `/god`.
  - `server-deploy`: isolation omitted → `none`, bypass, Write+Bash, `privilege_class: prod-operator`. Runs in the live checkout. Workspace Bash denylist (`launchctl`, `sudo`, process kills) **does not apply**.
  - `atlas-redeploy`, `project-redeploy`: same pattern (none + bypass + Bash). They restart launchd by design.
  - 27 other bypass+none writers (`research-*`, `idea-generation`, `new-project`, most atlas report/k401/evaluate, `self-diagnose`, …).
- Payload overrides skill frontmatter, including **`isolation`**. Telegram `parse_flags` accepts `--kind=` and `--permission=bypassPermissions`. Dispatch MCP `enqueue_job` does **not** validate isolation or kind.
- Generic unmatched `/task`: **no skill body**, full tool set (Read/Write/Edit/Bash/Web…), `permission_mode=acceptEdits`, `isolation=none`. LLM router (`src/runner/llm_router.py`) fail-opens to this.
- The 11 skills that actually get clones + guards: `app-patch`, `new-skill`, `project-evaluate`, `server-patch`, `atlas-build`, `atlas-momo-research`, `atlas-momo-drift`, `atlas-trader-paper`, `atlas-trader-research`, `atlas-advisors-ingest`, `atlas-advisors-panel`.

**Why it matters**

A confused `atlas-evaluate`, a generic `/task fix the server`, or `/task --kind=god` can `launchctl kickstart` the runner, edit Application Support, or `git push` the runtime clone. That is the 2026-07-09 single-writer incident class, still open. Payload `isolation: host` promotes any skill to god without tripping lint.

**What to change (cleanup bot)**

1. Treat `isolation: none` as **equivalent to host** in docs, lint, and (if you touch code) in `workspaces.resolve_isolation`.
2. Extend `scripts/lint_docs.py` INV-18: fail if a skill has Bash or Write/Edit **and** isolation not in `{workspace, host}`; fail if `host` is used on anything except an allowlist (`god` today; decide explicitly whether `server-deploy` / `*-redeploy` belong on that list and **label them `host`**).
3. In `src/gateway/telegram_bot.py` `parse_flags` and `src/runner/mcp_dispatch.py`: reject payload overrides of `isolation` and `permission_mode` unless the caller is already in a god/admin path. Reject `--kind=god` from `/task` (keep `/god` as the one door).
4. Change `SkillConfig` default isolation from `"none"` to `"workspace"` **or** make missing isolation a load error. Do not silently default to host-equivalent.
5. Generic unmatched task: at minimum force `isolation: workspace` (a throwaway clone) and deny `launchctl`/`sudo` via the existing denylist. Do not leave it as unlabeled host.
6. Fix three skills whose YAML frontmatter is **unparseable** because of an unquoted `:` in `description`: `atlas-chat`, `atlas-k401-review`, `atlas-portfolio`. PyYAML drops all frontmatter → they silently run on defaults (wrong model/effort/isolation). Quote those descriptions.

**Do not** "fix" this by adding more prose to SKILL.md. The hole is missing hooks + lint that only checks the string `host`.

---

### F2. Queue + status tools lie; deploy is starved; crash can lose queued work

**What's wrong**

1. **Two control planes.** `scripts/run.sh` start/stop/status uses `volumes/pids/*.pid`. Launchd never writes those. Both trees report all three services down while they are up. README still leads with `run.sh status`.
2. **BLPOP-before-semaphore.** `src/runner/main.py` ~156–165: `_job_loop` BLPOPs Redis, then `create_task(_run_with_semaphore)` without waiting for a slot. Redis is drained into in-process waiters.
3. **`reconcile_orphaned_jobs` only heals `status=='running'`** (`src/runner/reconcile.py`). Jobs left `queued` in Postgres with no Redis entry are invisible forever.
4. **`/health` `queue_depth` is Redis `LLEN` only.** Postgres backlog does not appear. Live snapshot: Redis 0, PG 15 queued + 2 running, health `queue_depth: 0`.
5. **No job priority.** Weekly `atlas-report` fan-out (14:32 ET) filled both concurrency slots (`MAX_CONCURRENT_JOBS=2`). `deploy-director` `5b0aefe0` queued 14:51 ET still waiting at 15:45. Meanwhile origin grew a second commit.
6. **Illegal / stuck statuses.** From 2026-08-23 14:33 ET: 3 jobs still `deferred` (atlas-report sector/portfolio) and 1 job `status='succeeded'` which is **not in `JobStatus`**. `src/models.py` JobStatus = queued/deferred/running/awaiting_user/completed/failed/cancelled only. No sweeper. Weekly run today duplicated the same descriptions as new `queued` rows.

**Why it matters**

An operator or a skill following README will think the server is dead and `run.sh start` from **Documents**, hitting FDA and binding :8080 against live uvicorn. A Mini/kernel/launchd kill of the runner drops the 15 IDs from Redis; they stay `queued` in PG and **never run** (same class as the comment on job `e38d0028`, 2026-07-30, different window). Deploy cannot land. Health looks green.

**What to change**

1. Make `scripts/run.sh status` (and start/stop, or clearly refuse them) talk to **launchd** (`launchctl print gui/$UID/com.assistant.{runner,web,bot}`) when those units exist. Do not document PID-file status as production truth.
2. Change `/health` `queue_depth` to `COUNT(*) FROM jobs WHERE status IN ('queued','deferred')` **plus** Redis LLEN, or return both fields (`pg_queued`, `redis_llen`, `running`). Never report 0 when PG has 15.
3. Reconcile `queued` rows that are not in Redis and not assigned to a live waiter: re-RPUSH, or mark failed, or both (pick one and test it). Extend `src/runner/reconcile.py`.
4. Do not BLPOP until a semaphore slot is free, **or** keep a durable "claimed" state in PG before dropping the Redis entry. The current drain-to-waiters design is the crash hole.
5. Add a priority or a reserved slot for `deploy-director` / `server-deploy` / `server-patch` so weekly atlas-report cannot starve ops.
6. Sweep `status='succeeded'` → `completed`. Sweep week-stale `deferred` rows. Make the DB constraint / enum reject unknown statuses. Confirm JobKind vs free `String(64)` (see F5).

**Verify after:** `run.sh status` matches launchd; `/health` shows the PG backlog; a fake queued-not-in-Redis row is healed on runner start; a deploy-director is not stuck behind N atlas-reports.

---

### F3. Dual-checkout is real and already leaking; Atlas has three clocks

**What's wrong**

Documented topology (`CLAUDE.md` "Single-writer topology"): code is born only in `~/Documents/repos/ai-server`; prod is pull-only except GOTCHAS/CHANGELOG/Troubleshooting, published by `scripts/sync-learnings.sh`.

Reality:

| | Documents (dev) | Application Support (live) |
|---|---|---|
| HEAD | `032a1ce` = origin/main | `fa41afd`, behind 2 (both currently **docs-only**: trading-bots spec v3 + plan T1–T18) |
| Dirty | `.claude/settings.local.json` | 8 modified + 3 untracked: GOTCHAS/CHANGELOG/TROUBLESHOOTING **and two `SKILL.md` files** |
| `src/`, `scripts/`, `alembic/` | identical today (`diff -rq` empty, 36 `.py`) | same |
| Skills dir names | 54, same set | same |
| `Pipfile.lock` | **gitignored**, 116883 B Jul 27 | different hash/size, 116790 B Jul 31 |
| `projects/` (gitignored `projects/*/`) | atlas, bingo, content-forge, ideas, **market-tracker**, research-deep | atlas, bingo, content-forge, ideas, **research**, research-deep |
| `volumes/` | leftover 97 audit_log entries, empty pids | real runtime ~691 jsonl, backups, logs, leftover workspace `44d1bc6b-atlas` |

Specific leaks:

1. **README.md first-time setup clones straight to Application Support.** No "also clone to Documents/repos." A rebuild following README is a **single checkout that is production**.
2. **`scripts/sync-learnings.sh` allowlist includes `skills/*/*.md`.** That is `SKILL.md` (runner-read machine contract: model, tools, timeout, isolation), not just GOTCHAS. CLAUDE.md prose says the only runtime-born writes are GOTCHAS/CHANGELOG/Troubleshooting.
3. **Live working tree is dirty** including `skills/atlas-momo-research/SKILL.md` (+31/−13) and `skills/chat/SKILL.md` (+10/−1). Hourly sync publishes them to `runtime-learnings` **without cleaning the tree**, so `git pull --ff-only` on prod can still fail on local modifications. Next `server-deploy` fights this.
4. **Content topology is a third, poorly advertised writer:** `research`, `research-deep`, `ideas` are prod-written by design (`PROJECTS_REGISTRY`). `research/` exists **only on prod**. `content-forge` is in-place, local-only, `git remote` empty. `baseball-bingo` delivery block still **pending** (live site, in-place).
5. **`.env.example` `SERVER_ROOT=/Users/chris/...`** would point volumes at a non-existent user on this Mini.
6. **Triple Atlas checkout.** Canonical sibling is 2.5 days ahead of the hosted clone. Nested `ai-server/projects/atlas` is a month-stale third clone. Several SKILL.md bodies still say `$HOME/Library/Application Support/ai-server/projects/atlas` (e.g. `atlas-scout`, `atlas-redeploy`). Advisors skills are scheduled against `project_slug: atlas` (delivery contract = **dev sibling**) but `atlas.chrispiserchia.com` is the **stale runtime clone**. First advisors ingest is **Mon 2026-08-31 10:00 ET**. Runtime clone has **no `advisors/` directory**.
7. **`market-tracker` leftover in dev `projects/`**, retired in `_ports.yml` / `PROJECTS_REGISTRY.md`. No launchd plist (good). Absent from prod.
8. **`mac-mini-ai-server` still sits** at Documents/repos months after archive. Dockerfiles still there. `TEARDOWN.md` is the old docker/ollama system.

**Why it matters**

Next ff-only deploy fails or drops SKILL.md edits. Runtime-born skill-contract edits bypass INV-4. Monday ingest writes dossiers into the wrong tree; the public site 404s any new advisors UI until someone runs `atlas-redeploy`. Nested clone is a landmine. `content-forge` has no off-site canonical (disk loss kills it). Rebuild from README cannot restore timers, tunnel, or the Documents writer.

**What to change**

1. Align README setup with CLAUDE.md: clone **dev** to `~/Documents/repos/ai-server`, clone **or** document that prod is a second checkout at Application Support, installed via `scripts/install-launchd.sh`. Document cloudflared as a **system** LaunchDaemon that README does not install.
2. Narrow `sync-learnings.sh` allowlist to GOTCHAS/CHANGELOG/Troubleshooting (match CLAUDE.md). **Stop auto-publishing `SKILL.md`.** If a skill contract must change, it goes through `server-patch` in the dev tree.
3. Before any `git pull --ff-only` in `server-deploy`: stash or refuse if `SKILL.md` / `src/` is dirty. After a successful learnings publish of allowed files, **reset those files** so the tree is clean. Do not leave prod dirty by design.
4. Pull/ff the live checkout to `032a1ce` (or current origin/main) **after** the dirty SKILL.md question is resolved (either commit via server-patch from dev, or discard if they were meant to be learnings-only).
5. Delete or clearly quarantine nested `Documents/repos/ai-server/projects/atlas` (the July 31 clone). It is not the canonical Atlas repo and not the hosted clone.
6. Delete leftover `Documents/repos/ai-server/projects/market-tracker` (retired). Decide whether to delete `Documents/repos/mac-mini-ai-server` or leave a one-line README pointer; do not leave it looking live.
7. Run `atlas-redeploy` (or the delivery-contract path) so the **runtime** Atlas clone catches up to sibling `c27e550` **before Monday 10:00 ET advisors ingest**. Confirm `advisors/` exists on the served clone. Confirm skills that hardcode Application Support `projects/atlas` still make sense under the delivery contract (cwd = sibling for patch jobs, pull-only runtime).
8. Give `content-forge` a GitHub remote or an explicit "local-only, backups are the canonical" note in `PROJECTS_REGISTRY`. Same for `research/` (prod-only content).
9. Fix `.env.example` `SERVER_ROOT` to use `$HOME` or `alfredbot.ai.butler`, not `/Users/chris`.
10. `GETSTARTED.md` is bannered HISTORICAL but the body still says "You're on Phase 1." Either make the banner impossible to miss and skip the Phase 1 prompt, or replace the body with a pointer to README. `TEARDOWN.md` should say it tears down the **archived docker** stack, not current launchd.

---

### F4. Invariants are specified as fail-closed and implemented as prompts; lint is a false green

**What's wrong**

`python3 scripts/lint_docs.py` on **dev**: **All clean (13/13 PASS)**. The linter is structural only:

- registries, charter membership, `isolation: host` only for `god`, delivery YAML parse, oversight roles must be `read-only`, dispatch+read-only must be `acceptEdits`.
- It **does not read** `MISSION.md`, `SERVER.md`, the INV table, status flags, or "Enforced in" claims.

Hard contradictions (same fact, opposite claims):

| Topic | One source | Other source |
|---|---|---|
| Auto-merge | `SERVER.md:75` "Not auto-merging server code changes. Ever." | `MISSION.md` §M / INV-4: autonomous merge on gate-green + LGTM + notify (2026-07-31). `.context/INDEX.md:16` still "always PR-gated." |
| Concurrency | `SERVER.md` "Default 2" | `MISSION.md` / `.env.example` / `src/config.py` default **4**. Live `.env` is 2. |
| Schema | `SERVER.md` "3 tables, 1 migration" | Alembic **5** versions (`001`–`005`: proposals, tasks, thread ids, task_plan). Six tables in prod. |
| INV-13 | SYSTEM.md: review that can't run → `awaiting_user`, **never silently completes** | Runner `.context/modules/runner/CONTEXT.md` (2026-08-05): `_maybe_review` **only FLAGS**, job stays `completed`, runs **after the code is already pushed** |
| Model-router | Plan `Status: APPROVED 2026-08-17`; MISSION non-goals amended | `INDEX.md` + `docs/README.md` still "PROPOSED — owner sign-off pending." **INV-21 is named in MISSION, undefined in SYSTEM.md** |
| `/proposals` | SYSTEM.md: "there is no `/proposals` Telegram command yet." | Runner CONTEXT.md: "query helpers for the /proposals command." `Documents/AGENT_SUITE_OVERVIEW.md` treats it as live |
| Tests | SYSTEM.md "289+"; README "~750" | `pipenv run pytest --collect-only -q` → **1247 collected** in 0.88s; 638 `def test_*` |
| SDK pin | SYSTEM.md / SDK_MIGRATION `>=0.1.63,<0.2` | `pyproject.toml` `>=0.1.81,<0.2` |
| Isolation default | Docs read as if code-writing skills always isolate | Default `"none"`; 41–42 skills missing the field |

Frozen "living" docs (headers vs reality):

- `.context/SYSTEM.md` Last updated **2026-07-31**. Active workstreams still point at `docs/EVALUATION_2026-07-10.md` (T1–T17). No INV-21. No trader/advisors.
- `SERVER.md` frozen ~**2026-07-30**.
- `docs/EVALUATION_2026-07-28.md` still billed as "latest full audit" (`docs/README.md`, `INDEX.md`). File mtime Jul 28. A month of atlas-loop / momo / trader / advisors / trading-bots is invisible.
- `.context/INDEX.md` header **2026-07-27**, body has 2026-08-30 sections. Quick-nav still says server-patch is "always PR-gated." Model-router still "PROPOSED."
- `Documents/AGENT_SUITE_OVERVIEW.md` HEAD `fa1adea` Jul 31: 41 skills vs 54; claims `/proposals` exists.

INV table mixes:

- (a) real code hooks: INV-3 API key, INV-6/7 auth, INV-16/17/20 guards
- (b) SKILL.md procedures: INV-4, INV-13, INV-18 except the lint check for `isolation: host`
- (c) conventions: INV-14 ports (EVALUATION B7 already said "convention-only")

INV-8/9/13 were previously "claimed enforced, weren't" (EVALUATION B7). 8/13 marked DONE, 9/14 "doc-corrected" — `SERVER.md` was **not** corrected, and INV-13 was later **behaviorally weakened** without editing the invariant row.

`privilege_class` unset on **35/54** skills. INV-20 hooks only fire when the field is set to `read-only`. Charter tags (content / guarded-writer / prod-operator) are documentation. `atlas-redeploy` is chartered prod-operator but frontmatter omits the class. `atlas-trader-evaluate` is `privilege_class: guarded-writer`, `permission_mode: bypassPermissions`, **required_tools include Write and Edit**, while the body says "never edits code."

**Why it matters**

A new session reads SYSTEM.md as "source of truth" and will not know about INV-21, delivery topology, trader governors, or that INV-13 no longer gates. Lint trains people that "docs are in sync." You cannot write a test for "INV-4 holds" because the spec's enforcement column points at markdown. Self-healing skills recover the wrong system (wrong table count, wrong liveness signal, assumed workspace guards).

**What to change**

1. **Rewrite `SERVER.md` against live reality** (do not append a changelog at the bottom and leave the old sentences): process topology including launchd (not `run.sh` as the manager); Postgres 6 tables / alembic 005; concurrency "code default 4, live currently 2"; isolation default none unless you change the code (F1); auto-merge policy matching MISSION INV-4 (or revert MISSION to match SERVER — pick **one**); Redis keys that exist (`heartbeat:runner`, `events:breaker`, `cb:ollama:…` / `cb:claude_cli:…`); ollama is running on this Mini if it is still a dependency, else say it is leftover.
2. **Define INV-21 in SYSTEM.md** (model-router containment) or remove the dangling references from MISSION/INDEX.
3. **Either restore INV-13 fail-closed in code** (`_maybe_review` must park `awaiting_user` / fail the job if review cannot run, and must run **before** push) **or** rewrite the INV-13 row to describe flag-only post-hoc review. Do not leave both. Protected-path list is also prompt-only (`MISSION.md`, `guards.py`, `lint_docs.py`, executor SKILL.md); if INV-4 is real, move it into the hook.
4. **Pick one merge policy** and make SERVER, MISSION, INDEX, CLAUDE.md, and `server-patch` SKILL.md say the same sentence.
5. Extend `lint_docs.py` with checks that actually fail when docs lie:
   - alembic head count vs SERVER.md claim (or stop claiming a number in SERVER.md and have SERVER.md point at alembic)
   - test collect count vs README (or stop putting a number in README)
   - every `INV-N` referenced in MISSION/INDEX exists as a row in SYSTEM.md
   - `privilege_class` required on every skill that a CHARTER assigns
   - YAML frontmatter must parse
   - isolation missing + Write/Bash → fail (see F1)
6. Update SYSTEM.md header, drop "active workstreams = EVALUATION_2026-07-10", point at current work (advisors loop, trading-bots plan, isolation/queue debt). Either retire `EVALUATION_2026-07-28.md` as historical or refresh it. Stop calling it "latest" in `docs/README.md`.
7. Set `privilege_class` on the 35 unset skills to match CHARTER. Make `atlas-trader-evaluate` tools match the body (drop Write/Edit) **or** change the body. Do not leave prompt vs tools.
8. Sync SDK pin mentions to `pyproject.toml` (`>=0.1.81,<0.2`).
9. `AGENT_SUITE_OVERVIEW.md` in Documents/ is outside the repo; update or stamp it stale (41 vs 54, `/proposals`).

---

### F5. Mission never updated; Atlas is the center of gravity; live money has no ceiling

**What's wrong**

- Objectives A–M are still "assistant + host projects + self-manage."
- Atlas is a hosted project in the registry, but ~20–26 of 54 skills are atlas-*.
- 2026-08-30 spec (`docs/superpowers/specs/2026-08-27-two-trading-bots-design.md`): ACCEPTED-DIRECTION, Tradier live-small-day-1 auto-trader, "Tradier is the only brokerage." tastytrade withdrawn; value bot advisory-only.
- Two overlapping trading programs: `atlas-trader-*` (paper, **implemented, scheduled**) vs swing/value bots (spec says **nothing implemented yet**, sibling has `tradingcore/`). Agents will implement the wrong one or wire live money onto the paper executor.
- `god` is "the exception to every ceiling." Atlas CHARTER: `atlas-build` is `guarded-writer` that pushes GitHub master and dispatches deploy. Original non-goals freeze an April identity; since then: management hierarchy, autonomous merge, atlas sub-org, closed improvement loop that **builds and deploys Atlas**, paper trading, YouTuber shadow books, live Tradier plan.
- Router (`src/runner/router.py`) Atlas coverage is almost only **redeploy**. No rules for scout/brief/report/trader/advisors/k401. `/task scout stocks` does **not** hit `atlas-scout` by rule. Falls through to Haiku or generic host session.
- `src/models.py:JobKind` still only Phase 1–6 kinds (`backup`, `notify`, no atlas/god/deploy). Kind is a free `String(64)` so atlas jobs work; the enum is a lie. Prod already has two spellings: `deploy_director` vs `deploy-director` (19+13 completions), `atlas_redeploy` vs `atlas-redeploy` (8+8).
- `seed-schedules.sh` comments claim it is the ONLY writer. DB has extra rows **not in seed**: `atlas-daily-brief` (daily 12:00 UTC, ran today 8:00am ET), `atlas-weekly-reports` (`atlas-report-sweep`, Sun 18:00 UTC, ran today 2:00pm ET). A wipe + seed **drops the two most user-visible atlas jobs**. Skills with no schedule: `idea-generation` (MISSION §E), `project-update-poll` (MISSION §B), `atlas-scout`, `gap-auditor`.
- Deploy skill fork: charter still says "migrate onto generic `project-redeploy` once atlas has a delivery block." The block is **ACTIVE 2026-07-31**. Two pipelines remain. `atlas/manifest.yml` `deploy.skill: atlas-redeploy`. Router special-cases atlas.
- YouTube advisors: roster filled (5 public channel IDs in `advisors/config/roster.yaml`); skills + schedules exist; `last_et` empty; first ingest Mon 2026-08-31 10:00 ET. Tradier: docs-only. Alpaca: paper/data (atlas `.env.example` `ALPACA_*`; `trader/CLAUDE.md` rule 1 PAPER ONLY).

**Why it matters**

Quota, routing, and manager attention are captured by one product. A "research the NBA deadline" ask can be LLM-routed into an atlas skill. A live-money lane can be added as "just another atlas vertical" without tripping §M. Combined with F1, this is how a personal assistant grows an unsupervised trading desk.

**What to change**

1. Rewrite `MISSION.md` opening + §M:
   - State that Atlas is a first-class hosted product (reports, 401k, momentum, paper trader, advisors) running **on** this server, not a side project.
   - Add an explicit ceiling: **no live brokerage orders** until a named INV exists, a code-level deny (not a prompt), a paper-only grep tripwire in CI, and owner sign-off. Name Tradier/Alpaca. "Nothing about money" is the current hole.
   - Update non-goals: this is still not a multi-user framework; it **is** a personal assistant kernel plus one product org.
2. Do **not** implement the swing bot in this cleanup. Put a hard skip in `server-patch` / `new-skill` if the skill would place orders.
3. Pick a single trader: keep `atlas-trader-*` as the paper system; mark the swing/value spec as "future, blocked on F1+F4+mission," or vice versa. Document the choice in MISSION and the spec header. Do not leave "nothing implemented yet" next to a `tradingcore/` directory and scheduled paper skills.
4. Add router rules for the atlas skills you actually want reachable from `/task`, **or** require `--kind=` and stop claiming NL routing works. Collapse `deploy_director`/`deploy-director` and `atlas_redeploy`/`atlas-redeploy` to one spelling; migrate old rows or accept both in `_resolve_skill`.
5. Make `scripts/seed-schedules.sh` the real single writer: add `atlas-daily-brief` and `atlas-weekly-reports` to the seed (matching current cron), **or** delete those DB rows if they were experiments. Re-run seed is not enough if the script doesn't contain them.
6. Either schedule `idea-generation` and `project-update-poll` (MISSION promises) or strike those promises from MISSION.
7. Finish the `atlas-redeploy` → `project-redeploy` migration **or** delete the charter sentence that says you will. Don't leave both pipelines + a "once the block is active" TODO when the block has been active since 2026-07-31.
8. Update `.context/org/divisions/atlas/CHARTER.md` roster vs frontmatter (privilege_class, isolation) so lint can enforce it.

---

### F6. `Pipfile.lock` gitignored and already diverged

**What's wrong**

`.gitignore` line 17: `Pipfile.lock`. Not in `git ls-files`. Dev vs live hashes differ (`00882d82…` vs `e1afe161…`; 116883 B Jul 27 vs 116790 B Jul 31). `pyproject.toml` has `mcp<2` with an incident-quality comment: unbounded lock already caused a prod outage (2026-07-30).

**Why it matters**

`pipenv install` on deploy is not pinned to the same graph. Same class as the mcp 2.0.0 outage, waiting to recur.

**What to change**

Stop gitignoring `Pipfile.lock`. Commit **one** lockfile from the environment you actually run (live, after `pipenv lock` if needed). Deploy/bootstrap must `pipenv sync` (or equivalent) against that lock. Keep the `mcp<2` pin.

---

### F7. Single-machine ops holes that a rebuild or a quiet week will hit

**What's wrong**

- One Mini. No HA.
- Caddy HTTP :80 only; TLS is cloudflared. Cloudflared is a **system** LaunchDaemon **not** in `install-launchd.sh`. Rebuild from repo scripts does not restore the tunnel.
- Launchd `KeepAlive` is `Crashed=true`, `SuccessfulExit=false` — a clean `sys.exit(0)` **stays down**.
- `bot.err.log` **~46,164,695 bytes** of `httpx` INFO `getUpdates`. Almost no rotation (only `project.atlas-pm-edge.out.log.1.gz` observed).
- Documents checkout still has leftover `volumes/audit_log`.
- Atlas web binds `*:8791` (all interfaces); bingo/forge bind `127.0.0.1`. LAN can hit Atlas on 8791.
- Eval auto-loop / 64 `self-diagnose` completions in 14d (Telegram handler auto-dispatches on errors) is noise on quota.
- `notify` still in JobKind + SKILLS_REGISTRY "Deferred".
- Heartbeat Redis key is `heartbeat:runner` (TTL ~899s), not `runner:heartbeat` if anything still documents the latter.

**What to change**

1. Document the tunnel plist in README + `install-launchd.sh` comments (you probably should **not** auto-install a system daemon from a user script; say "install cloudflared as LaunchDaemon, path X").
2. Bind atlas to `127.0.0.1:8791` like bingo/forge, unless LAN access is intentional (then say so in CHARTER).
3. Cut bot httpx INFO (raise log level) and add log rotation for `volumes/logs/*.log` / launchd stdio.
4. Decide KeepAlive policy: if you want `run.sh stop` / clean exit to stay down, keep it; document it. If you want always-on, `KeepAlive true` unconditionally — and then `run.sh stop` must `launchctl kickstart -k` disable.
5. Delete leftover Documents `volumes/audit_log` or add it to a "dev tree must not have runtime volumes" check.
6. Cap or sample `self-diagnose` auto-dispatch so a flapping Telegram error cannot burn 64 jobs/2 weeks.
7. Remove or implement `notify`. Don't leave Deferred ghosts in the enum.

---

## 4. What is actually solid (do not "fix" these)

- Five-process topology is up from Application Support as intended. Heartbeat ~1.7s, `/health` 200, DB/Redis up, alembic 005, 1036 jobs historically (913 completed at inspect time).
- Subscription auth is defense-in-depth: no `api_key` field in `config.py`, scripts unset `ANTHROPIC_API_KEY`, runner aborts if set. SDK uses bundled CLI. Telegram allowlist: empty list ⇒ nobody authorized. Web token required (401 without it).
- Workspace isolation is **fail-closed when used** (clone failure aborts the job; documented 2026-07-09 hole closed for that path).
- `god` cannot be a subagent. Managers/connectors that *do* set `privilege_class: read-only` get hook-enforced mutation denial with dispatch still allowed (INV-20) — real, learned from the 2026-07-30 silent-MCP incident.
- Atlas delivery contract (cwd-scope patch jobs to sibling, pull-only runtime, `env_files` copy) is the one project that actually uses the 2026-07-27 segregation design. Deploy gates: red tests keep old code; `volumes/state/deployed-sha-*` markers (2026-08-18).
- Skill-as-data is real: no Python per skill; `load()` + `agents.skill_to_agent_definition`. 54 dirs, each has `SKILL.md`. Structural lint is good at what it does (13 checks, currently green).
- Trader/advisors/k401 constitutions are explicit on paper-only / no order path. Advisors roster is owner-filled, not placeholder.
- Caddy health vhost exposes only `/health`. Docker lane is actually gone from ai-server (`docs/CONTAINERS.md` historical; `isolation: container` maps to workspace). Atlas still has leftover `docker-compose.yml` (Postgres 16 overlay) — leftover, not the Mini runtime (Homebrew Postgres@15).
- Nightly backups (51, latest 04:00 ET the inspection day), 5-min project healthcheck all healthy, hourly learnings sync, prod pre-commit hook present.
- Test corpus is larger than advertised (1247 collected, fast collect). Migrations have a chain-consistency test that always runs. DB tests are opt-in `AI_SERVER_RUN_DB_TESTS=1`.
- `.env` is gitignored and untracked (the footgun is dual on-disk copies + stale example username, not secrets in git).
- Write-back culture is real: `PROTOCOL.md` is tight; runner `_writeback` is a backstop. Module CONTEXT/CHANGELOG for `runner` is the most honest file in the repo (documents INV-13 weakening, 0/516 review-never-fired bug, API-terminal 529, momo timeout). Prefer updating SYSTEM/SERVER to match runner CONTEXT rather than the other way around when they disagree about **behavior**.

---

## 5. Suggested cleanup sequence for the other bot

Work **only in the dev checkout** (`~/Documents/repos/ai-server`) for code/docs. Use `/task deploy server` (or the existing deploy-director path) to publish. Do not hand-edit Application Support `src/`.

**P0 — stop the bleeding (do before Monday 10:00 ET 2026-08-31 advisors ingest if still in the future)**

1. F3.7: catch up the **runtime** Atlas clone to sibling HEAD so `advisors/` exists on `atlas.chrispiserchia.com`.
2. F2: unstick `deploy-director` `5b0aefe0` if it is still queued (priority slot, or cancel+requeue after atlas-reports finish). Confirm `run.sh status` lie so you don't start a second runner from Documents.
3. F1.6: quote YAML on `atlas-chat`, `atlas-k401-review`, `atlas-portfolio`.
4. F5: do not ship Tradier live orders in this pass.

**P1 — make the safety story true**

5. F1: isolation default + lint + reject payload promotion + generic-task workspace.
6. F4.3: INV-13 code vs docs, pick one. F4.4: merge policy, pick one.
7. F5.1: MISSION rewrite + no-live-orders ceiling as an INV with a **code** deny, not a paragraph.
8. F3.2–3: stop publishing SKILL.md via sync-learnings; clean prod tree.

**P2 — make ops and docs match the machine**

9. F2: launchd-aware status, honest `/health`, queued reconcile, deploy priority.
10. F4: SERVER.md + SYSTEM.md + lint extensions + privilege_class backfill.
11. F6: commit Pipfile.lock.
12. F3: README dual-checkout, delete nested stale atlas + market-tracker leftovers, `.env.example` username, seed-schedules vs DB extras (F5.5).
13. F7: atlas bind address, bot log volume, KeepAlive docs, leftover Documents volumes.

**Out of scope for cleanup (product, not repair)**

- Implementing Tradier swing / value bots
- Building a second Mini for HA
- Multi-user
- Re-introducing Docker on ai-server

**Tests to run after code changes**

```bash
cd /Users/alfredbot.ai.butler/Documents/repos/ai-server
pipenv run python scripts/lint_docs.py
pipenv run pytest          # ~1247 collected; do not treat README "~750" as the pass bar
# isolation/guards/reconcile/health tests you add should go under tests/
```

Do not run destructive teardown. Do not `run.sh start` from the Documents tree while launchd is up.

---

## 6. File checklist (touch these, not a vague "docs")

| File | Why |
|---|---|
| `MISSION.md` | Identity + §M live-money ceiling + drop or keep §B/E schedule promises |
| `SERVER.md` | Full rewrite vs live topology (not a footer changelog) |
| `.context/SYSTEM.md` | INV-13 truth, INV-21 definition, header date, active workstreams, isolation, schema, concurrency |
| `.context/INDEX.md` | Header, PR-gated vs auto-merge, model-router status |
| `README.md` | Dual-checkout setup, launchd as process manager, test count, not `run.sh` as prod status |
| `GETSTARTED.md` / `TEARDOWN.md` | Historical bodies vs banners |
| `docs/README.md` | Stop calling EVALUATION_2026-07-28 "latest" |
| `.context/modules/runner/CONTEXT.md` | Already honest; keep in sync when you change `_maybe_review` / job loop |
| `scripts/lint_docs.py` | New semantic checks (F1, F4) |
| `scripts/run.sh` | Launchd-aware status; refuse start if launchd units exist |
| `scripts/sync-learnings.sh` | Drop `skills/*/*.md` from allowlist |
| `scripts/seed-schedules.sh` | Absorb DB-only schedules or delete them |
| `scripts/install-launchd.sh` | Comment the cloudflared system daemon gap |
| `.env.example` | `SERVER_ROOT` username / `$HOME`; concurrency comment matching live vs default |
| `.gitignore` | Stop ignoring `Pipfile.lock` |
| `Pipfile.lock` | Commit one |
| `pyproject.toml` | Already has mcp pin; leave it; sync docs to SDK lower bound |
| `src/config.py` | Isolation default if you change SkillConfig here vs registry |
| `src/registry/skills.py` | `SkillConfig.isolation` default; YAML parse must fail closed |
| `src/runner/session.py` | Guards, payload override policy, generic-task isolation |
| `src/runner/workspaces.py` | `none` vs `host` |
| `src/runner/main.py` | BLPOP vs semaphore |
| `src/runner/reconcile.py` | Heal `queued` not in Redis |
| `src/runner/router.py` | Atlas rules; kind spelling |
| `src/runner/mcp_dispatch.py` | Reject isolation/permission overrides |
| `src/gateway/telegram_bot.py` | `--kind` / `--permission` / `/task --kind=god` |
| `src/gateway/web.py` | `/health` queue fields |
| `src/models.py` | JobKind vs String; JobStatus reject `succeeded` |
| `src/runner/guards.py` | Residual bypass already documented; don't pretend Bash denylist is enough |
| `skills/atlas-chat/SKILL.md` (+ k401-review, portfolio) | Quote YAML `description` |
| `skills/atlas-trader-evaluate/SKILL.md` | Tools vs "never edits code" |
| `skills/server-deploy/SKILL.md` | Label isolation `host` if it stays host-equivalent, or isolate it |
| `skills/god/SKILL.md` | Keep as the one break-glass; do not add more gods |
| `.context/org/divisions/atlas/CHARTER.md` | privilege_class vs frontmatter; redeploy migration sentence |
| `projects/_ports.yml` / `PROJECTS_REGISTRY.md` | market-tracker leftover; content-forge canonical; bingo delivery pending |
| Atlas sibling `manifest.yml` | Still lists `ANTHROPIC_API_KEY` in `env_required` (charter open item X2) while ai-server INV-3 forbids that key on the **server**. Atlas dashboard may keep its own key; don't copy it into the runner env. |

---

## 7. Feature suggestions (after cleanup, not instead of it)

These are product moves that make the system better **once F1–F5 are not on fire**. Ranked by leverage.

### 1. Ops lane + honest control plane

A first-class **ops queue** (or a reserved concurrency slot) for `server-deploy`, `deploy-director`, `server-patch`, `restore`, with a status UI/Telegram `/status` that shows: launchd state, PG queued/deferred/running, Redis LLEN, who holds the slots, age of the oldest queued job. Today the weekly atlas-report fan-out can make deploys invisible and `/health` stays green. This is the difference between a server you can run and a server you hope is running.

### 2. Isolation as a real runtime product

Default `workspace`, fail closed on missing/invalid frontmatter, payload cannot promote isolation, generic `/task` always cloned. Add a `skills doctor` job that prints the histogram (none/workspace/host, privilege_class, YAML-parse errors) and fails CI. The 2026-07-09 incident will recur until this is a feature, not a GOTCHA.

### 3. Money containment rail (before any live trader)

A dedicated INV + guard: any Bash/Write that talks to Tradier/Alpaca **live** order endpoints is denied unless `LIVE_TRADING=1` is set in prod **and** the skill is on an allowlist of 0–1 skills. CI grep tripwire for order-placement URLs. Paper trader stays the default. Do not build the swing bot until this exists. The accepted-direction spec is otherwise a loaded gun next to unlabeled host sessions.

### 4. Atlas as a budgeted tenant, not an unbounded org

Quota and concurrency shares: e.g. max N atlas jobs at once, max M atlas-report/week, managers cannot stampede 15 weekly reports into both slots. Router: atlas NL goes to atlas skills; "research the NBA" cannot Haiku-route into `atlas-scout`. This is how the original assistant mission survives contact with a product that already owns 48% of skills.

### 5. Schedule-as-code, round-tripped

`seed-schedules.sh` generates from (or is generated from) a YAML/SQL file that is the only writer. `GET /api/schedules` vs seed diff is a lint check. Extra DB rows fail CI. Restores and new Minis then bring back `atlas-daily-brief` / Sunday sweep instead of silently dropping the two jobs the owner actually sees.

### 6. Delivery contract for every hosted project (finish bingo + content-forge)

Bingo is live in-place with a pending delivery block. Content-forge has no GitHub remote. Atlas is the only project on the 2026-07-27 segregation design. Promoting the other two means a disk loss or a bad `cd` no longer takes a public site with it, and `project-redeploy` can actually replace `atlas-redeploy`.

### 7. Single Atlas clock

One canonical sibling, one pull-only runtime clone, zero nested `ai-server/projects/atlas`. A `delivery doctor` skill that diffs the three SHAs and refuses advisors/trader deploys if runtime HEAD is behind sibling by more than T (hours). Monday 10:00 ingest is the concrete deadline that already proved this is not theoretical.

### 8. Self-diagnose budget and a real `/proposals` (or delete the stubs)

64 `self-diagnose` jobs in 14 days is the system talking to itself on quota. Cap it. Meanwhile SYSTEM.md, runner CONTEXT, and the suite overview disagree on whether `/proposals` exists. Either ship the Telegram command against the `proposals` table (alembic already has it) or delete the query helpers and the docs that advertise it. Ghost surface area is how sessions pick the wrong tool.

---

## 8. One-paragraph brief you can paste

> ai-server on AlfredblersMini is a working launchd-managed assistant kernel (runner/web/bot/caddy + cloudflared + Postgres/Redis) whose center of gravity is now Atlas (~half of 54 skills, most of 23 schedules, most recent jobs). Dev is `~/Documents/repos/ai-server` @ `032a1ce`. Live is `~/Library/Application Support/ai-server` @ `fa41afd`, dirty, behind 2. Isolation default is `none` (42/54 skills unlabeled host); guards only attach to `workspace`. `run.sh status` and `/health` queue_depth both lie; 15 PG queued jobs including a starved deploy, Redis LLEN 0. INV-13 is documented fail-closed and implemented as post-push flags. lint_docs is 13/13 green without reading MISSION/SERVER/invariants. Live Tradier trading is accepted-direction with no mission ceiling. Catch up the runtime Atlas clone before Monday advisors ingest; do not implement live money in the cleanup. Full findings: this document.

---

*End of evaluation. Inspection 2026-08-30 ~15:45–15:50 ET. No secret values included.*
