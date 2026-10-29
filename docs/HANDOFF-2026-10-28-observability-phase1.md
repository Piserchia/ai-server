---
id: report-2026-10-28-handoff-observability-phase1
type: report
status: reference
date: 2026-10-28
supersedes: []
superseded_by: null
summary: >-
  Session handoff for Observability Phase 1 (Tier A deployed, Tier B unbuilt),
  verified against the tree and prod as of 2026-10-28; the second session of
  that day exercised the Codex lane (found and fixed a B3 defect), persisted
  per-job model_usage and merged the runtime learnings — read the UPDATE
  section first, then the recut plan's sections 0, 3, 7, 8 and 11.
---

# Handoff — ai-server, Observability Phase 1 (as of 2026-10-28)

> Written to reset a session's context. Read this, then
> `docs/superpowers/plans/2026-10-21-observability-phase1-recut.md` (§0 deltas, §3 decisions,
> §7 owner actions, §8 exit criteria, §11 deployment log). Everything below is verified against
> the tree and prod, not recalled.

## UPDATE — Tier B built 2026-10-29 (owner: "Go with number 1"); read this first

**All ten Tier B tasks (E1–E10) are built on branch `observability/phase-1-tier-b`**, one commit each
(`c4ed48f` E1 … `dc5c755` E10), tests first, full suite **3092 passed, 2 skipped**, `lint_docs` clean,
`lib.py check` OK. Per-task independent reviews for E1, E3, E6, E7 (all findings applied — see the
runner/gateway CHANGELOG entries dated 2026-10-29); E2/E4/E5/E8/E9/E10 rely on the whole-tier review.
**Merged `--no-ff` as `cba9c8b`, pushed 2026-10-29 21:55Z (owner: "Merge back to main locally") and DEPLOYED by the
autopilot at 22:12Z** (`server-deploy a6f374cc` completed `ok`; the runner restarted and stayed up through E7's and E8's
startup checks; `/health` ok). Every `Ruling:` the session made on the owner's behalf is copied into the recut plan's §10 review log
(the sdd workspace ledger was deleted after the merge, as the process prescribes).

| Task | What landed | Notable |
|---|---|---|
| E1 | settings-channel override refused before the session (`session.settings_override`, provenance-keyed; `SettingsOverrideRefused`) | observe arm **sized in code** (bingo→`hooks` + `permissions` in any project's `settings.local.json`); Q2 probe: project-scope `ANTHROPIC_BASE_URL` **is honoured** by CLI 2.1.139; lenient JSON is not parsed |
| E2 | `DEFAULT_REQUIRED_TOOLS`; `AskUserQuestion` off the default list | 7 explicit declarers untouched |
| E3 | `cancel_job_durable` — one cancel vocabulary at four sites; `/cancel`, `/proposals`; `/rate` off the copy | the runner's queued→running flip is still an unguarded write (recorded, GOTCHAS) |
| E4 | `/clear` asks (120 s token) and runs through the durable cancel | running rows now get the publish; deferred rows included |
| E5 | idle `review-and-improve` dispatcher deleted | alpha drainer pinned |
| E6 | always-on secret redactor, both lanes | review's 20-string bypass corpus pinned; derived `task_*` rows redacted |
| E7 | telemetry-off overlay on every subprocess; startup refusal on a planted key; utility `model_usage` audited | `CODEX_` is NOT a prefix (Settings knobs); **prod's plist is a login shell — run runbook §0b before the restart** (printed `[]` here) |
| E8 | alembic startup check + `alembic-current-check.sh` | "cannot tell" boots; a real gap refuses |
| E9 | dev `commit-msg` protected-path guard | armed in the dev checkout; renames/typechanges covered; `web.py`/`telegram_bot.py` guarded by auth hunk; D6 first half still owner-gated |
| E10 | daily credential canary 06:50 | hand-run **PASS** (`ok served=claude-sonnet-4-6 api_ms=1315`); any E7-set env variable is a FAIL; user scope = auth ∪ {hooks, env, apiKeyHelper}, `statusLine` allowed; timer reaches prod with `install-launchd.sh timers-only` (owner item 5) |

**Owner items this adds**: run runbook **§0b** (login-shell probe) before the deploy restart; **§5**
`install-launchd.sh timers-only` (now also installs the canary) then the full install for E7's plist flags;
**§8b** keep the dev guard armed; D6's first half still open. §8 exit rows 6–8 are now tests.

## UPDATE — second session, 2026-10-28 (read this first; the sections below it are the morning's state)

Four commits on top of `e43c397`, pushed as `ff61e56` and **deployed by the autopilot 2026-10-28 21:05Z**
(gate 2860 passed; the deploy job then records `failed`/exit 143 because its own runner restart kills its
session — a known once-per-deploy artefact that also spawns a `self-diagnose` escalation; plan §11).

| Commit | What |
|---|---|
| `94a057f` | **Merged `origin/runtime-learnings` into main** (20 syncs, docs only: runner/hosting CHANGELOGs, runner GOTCHAS, TROUBLESHOOTING, six atlas skill GOTCHAS/CHANGELOGs). Nine additive conflicts resolved as a union; one duplicated GOTCHAS entry deduplicated. |
| `9d31e28` | **The Codex lane was exercised and it was broken.** The handoff's "give the Codex lane one real job" item: smoke job `0e09233d` (web, `codex/gpt-6-luna`, pickem, read-only) did its work — 38,799 / 206 / 16,000 tokens, empty diff — and then **failed** at B3's post-session column stamp: `codex --version` reports `codex-cli 0.162.0-alpha.17.2` (28 chars) into `cli_version` varchar(24). B3's wiring test had faked `"0.162.0"`. Fix: `result_capture.cli_version_column` (+ `CLI_VERSION_MAX` pinned to the ORM) for both lanes, and the stamp is guarded — a failure is audited `result_stamp_failed{error}` and the job completes (the terminal transition re-stamps tokens/cost; `cli_version`, `duration_api_ms`, `sdk_cost_usd` stay NULL in that case). A `job_failed` DM for `0e09233d` went to the owner (message 954). The row is left as evidence; repairing its token columns from its JSONL `turn_completed` event is an owner call (see owner item 11). |
| `95e1ac5` | **`model_usage` persisted per job** (the other "smaller, unblocked" item): `job_completed.model_usage` and `result["model_usage"]` (→ `jobs.result`, no migration) carry the per-model breakdown normalised to the SDK key names plus the CLI's per-model `costUSD` as `sdk_cost_usd`; `pricing.price_model_usage` prices an Anthropic session per model when the breakdown **covers** the aggregate, else the old one-model figure. **The independent review read the bundled CLI (2.1.139) and found three things, recorded in the runner CHANGELOG as "stated, to be verified on the first rows"**: `usage` counts the main loop only while `modelUsage` counts every call (subagents and utility calls included), so the per-model figure covers tokens the five token columns do not; the CLI's own price table prices every cache write at 1.25× input (the 5-minute rate, no TTL notion); and `sdk_cost_usd` is Σ per-model `costUSD`, subagent tokens included. Together these plausibly explain §8's "NOT a single rate" row without a TTL mystery — the withdrawn '5-minute rate' reading may have been right. |

**Verified after the deploy (21:05–21:07Z; plan §11)**: (1) Codex smoke job `8cbabaab` completed `ok`, `cli_version`
`0.162.0-alpha.17.2`, tokens on the row, no `result_stamp_failed` — §8 row 1 is closed on both lanes; (2) first
per-model row `bdef2a99` (opus-4-7, single model): breakdown persisted on `job_completed` and in `jobs.result`,
equal to `usage`; **`cost_usd_list` $0.8813 vs SDK $0.6963, and the same tokens priced with cache writes at the
5-m rate give $0.69628725 = the SDK figure to 8 decimals** — the CLI's `total_cost_usd` prices cache writes at
1.25× input, full stop; it is not evidence of the billed TTL. Still to see: a session WITH subagents (expect
Σ breakdown > `usage`, `per_model_priced` in the reconcile). The verify list as it was written: (1) one more Codex smoke job — same curl shape as `0e09233d`
(`POST /api/jobs` with `{"model":"codex/gpt-6-luna","project_slug":"pickem", "description": "<read-only ls task>"}`
and the `WEB_AUTH_TOKEN` bearer) — must complete with `cli_version='0.162.0-alpha.17.2'`, tokens on the row
and no `result_stamp_failed`; (2) on the first Anthropic rows, per counter `Σ job_completed.model_usage` vs
`usage` (expect ≥, strictly > with subagents), `result["model_usage"]` on the row, and `cost_usd_list` vs
`sdk_cost_usd`; (3) the Monday `cost-reconcile` prints `N job(s) priced per model` — but note owner item 5:
that timer is **still not installed** until `install-launchd.sh timers-only` runs on prod, so run
`scripts/cost-reconcile.py` by hand if Monday passes without it. Then update plan §8's cost row from data.

Baselines for the next session: suite **2860 passed, 1 skipped**; `lint_docs.py` clean; `lib.py check` OK.
Owner items 1–9 below are unchanged (none done this session). New: **11.** decide whether to repair
`0e09233d`'s token columns from its JSONL (status stays `failed`; a `note` audit event would record the
source) — zero monetary effect (Codex is unpriced), it only buys an honest per-provider token view.

**Next task is still the owner's pick** — Tier B (needs the owner's word; E9 needs the D6 MISSION §M PR
first) or the trading-unblock plan (cut spec §7 items 3–8). Both "smaller, unblocked" items are done.

## STATE

**As of the morning session: everything built was merged, pushed and deployed; nothing in flight** —
`main` == `origin/main` == prod HEAD at `e43c397` (superseded by the UPDATE above); alembic head **008**; working tree clean apart from three items to leave
alone: modified `.claude/settings.local.json`, untracked `.superpowers/` and `AGENTS.md`.

- **Codex lane** — live since 2026-10-21 (migration 007, `ROUTER_PROVIDERS_ENABLED=anthropic,codex`
  in prod `.env`). ~~Still unexercised~~ **Exercised in the second session: broken, fixed in `9d31e28`, re-verification pending the deploy** (UPDATE above).
- **Protected bundle** (slice T8) — owner-approved 2026-10-21, merged as `2fb6012`, deployed. Prod's
  `guards.py` and `lint_docs.py` match the merge. Vendor-credential denies, INV-22 broker-order
  denies, lint rules 14/15 are all live. **This branch is done; do not re-merge it.**
- **Observability Phase 1, Tier A** — owner said *"go Tier A, D-P1-7 yes, merge the protected
  bundle"*. All 13 tasks (A1–A7, B1–B4, C1, D1) built test-first, each LGTM'd by an independent
  reviewer, then a six-dimension whole-tier review with two skeptics per major (7 majors confirmed,
  24 minors, all applied → `755a280`). Deployed `aa4499b` on 10-22; four follow-up fixes since.
  Live and verified: migration 008 (2244 of 2472 rows token-backfilled, every job has an origin),
  the notifications outbox, typed terminal reasons, token/cost stamps, the cost-reconcile CLI,
  backup hygiene, the scheduler provisioning pre-check.
- **Tier B (E1–E10) is NOT built and was not approved.** Tier A alone is a partial Phase 1 — §8
  exit rows 6–8 (settings-override refusal, startup key assertion, utility `model_usage` check) are
  Tier B. Do not start it without the owner's word; E9 additionally needs the D6 MISSION §M PR first.

### Verified working on prod (2026-10-28, first full week)

| | |
|---|---|
| Stamps | 111 completed jobs, **every one** with a typed `terminal_reason` (ok 76, error 27, max_turns 8); tokens and cost on all but the 3 that failed before skill resolution |
| New signal | **8 jobs hit `max_turns`** and are recorded `completed` + `max_turns` (D-P1-2). Before Phase 1 they looked like clean successes |
| Outbox | 11 notices, all `sent` first attempt, no errors: 3 `schedule_deferred`, 3 `job_failed`, 5 `ops_alert` (A7's alerters delivering through the outbox, not raw curl) |
| Provisioning pre-check | 4 deferrals, **0 sessions burned**: the two EDT swing rows defer daily on `TRADIER_SANDBOX_TOKEN` with a notice each and a `DEFERRED` line in the 07:15 DM |
| Backups | atlas `-Fc` dump **529 MB** in ≈35 s, tarball 19 MB; `restore-drill.sh` **PASS** both legs (2477 jobs; atlas ≈2.5 min), throwaway DBs dropped |
| Cost | Trailing 30 d ≈ **$1,802.07** list-equivalent (789 priced jobs, 09-28 → 10-28), 7 d ≈ **$231.68** — both measured *after* the `model_served` fix and the 39-row recompute. Computed vs SDK is **family-dependent**, not one rate: opus-5 −2.4 %, opus-4-8 −3.2 %, opus-4-7 −17.9 %, sonnet-4-6 −23.4 %, implied cache-write rates straddling the 1-h and 5-m rates. `cost_usd_list` at the 1-h rate is the figure of record |
| Entry probes | `WEB_AUTH_TOKEN` → 401; zero `CLAUDE_CODE_OAUTH_TOKEN` across the 14 `com.assistant.*` plists |

## WHAT WENT WRONG, AND WHAT IT COST

Both were found and fixed in-session; both are recorded in the plan's §11 and the runner GOTCHAS.

1. **A test wrote to production.** During the first deploy's own pytest gate, a test drove the
   dual-write `_notify_task` with only `src.db.redis` patched — `main.py` binds its own `redis` at
   import — and the dev `.env` points `POSTGRES_DSN` at the prod database even under
   `PIPENV_DONT_LOAD_ENV=1`. It inserted a real `notifications` row and the new bot DM'd the owner
   ("Task failed after 3 escalation attempts. Last error: boom"). Row deleted by hand. Fixed at the
   class level (`6e442a2`): `tests/conftest.py` points both DSNs at a closed port before `src.db`
   builds its clients unless `AI_SERVER_RUN_DB_TESTS=1`, and `tests/test_no_live_services.py` pins
   it. **A connection error on `127.0.0.1:1` in a test now means that test patched the wrong module.**
2. **`model_served` named the wrong model, and mispriced the ledger.** It took the first
   `model_usage` key, which is routinely the CLI's own small-model call. On 39 of 111 jobs it
   stamped the retired haiku utility id while `resolved_model` was opus-5/sonnet-4-6/opus-4-8 — and
   since `pricing.price_usage` keys on `model_served`, those jobs were priced at Haiku rates
   ($24.84 against the SDK's $121.89). Fixed by `dominant_model()` (`9a07ad4`, in `c4dbb0b`).
   `served_model_violation` could not have caught it: it asserts the requested model is *present*
   among the keys, which it was.

**Closed 2026-10-28 on the owner's instruction** ("fix the 39 rows and re-run the baseline"):
`pricing.job_cost_from_events` now prices the *request* when `model_served` names a different family,
counting and printing the mismatch rather than silently re-rating (a bare-alias request still prices
from the served id — that case is why the field is read). The 39 prod rows got `model_served = NULL`
(the true id is unrecoverable: `model_usage` was never persisted, and the JSONL is append-only) with
`cost_usd_list` recomputed at the requested model's price — $24.84 → $122.66 against the SDK's
$121.89. Baseline re-run: 30 d ≈ $1,802.07, 7 d ≈ $231.68. **One conclusion was withdrawn in the
process:** "the CLI prices cache writes at the 5-minute rate" was computed over a population the bug
had split; post-fix the divergence is family-dependent. The standing explanation is that
`ResultMessage.usage` is a per-session aggregate across every model a session touched while the
ledger prices it as one model, so multi-model sessions are mispriced by construction — per-model
attribution needs `model_usage` persisted per job, which Phase 1 does not do (Phase 3 work).
The reconcile will print `note: 39 job(s) reported a model_served of a different family` for about
30 days, because only the DB rows were corrected.

**Also noticed, unrelated:** no job ran between 2026-10-22 05:27 and 2026-10-26 09:44 — the host was
off for four days. `pmset autorestart` is still `0`, so nothing would have restarted it or alerted.

## OWNER ITEMS (manual; plan §7 — none of them block code work)

1. Entry set never answered: **D2** (the alpha-lab `budget.yaml` cap proposal, or the word
   "deferred") and **D3** (spend posture, one line). `WEB_AUTH_TOKEN` and the 401 probe are done.
2. `sudo pmset -a autorestart 1` — currently `0`.
3. **R2**: create the bucket + API token, then `rclone config` a remote named exactly `r2`
   (rclone 1.74.3 is installed, zero remotes). **Until then no off-site copy of anything exists** —
   every nightly run logs `offsite SKIP`.
4. Seal key: `mkdir -p ~/.config/ai-server && openssl rand -base64 48 > ~/.config/ai-server/backup-seal.key && chmod 600 …`, copy to the password manager.
5. `bash scripts/install-launchd.sh timers-only` on prod — **the `cost-reconcile` and
   `credential-canary` timers are not installed until this runs**; then one full
   `install-launchd.sh` outside market hours (it restarts runner/web/bot).
6. `TRADIER_SANDBOX_TOKEN` + `FINNHUB_TOKEN` into **`~/Documents/repos/atlas/.env`** (the dev clone
   — the file `provision_env_files` copies and D1 checks, *not* the prod runtime clone). Until then
   the two swing rows defer daily, as designed.
7. D4 confirmations (Max tier, credits $0 / auto-reload off / spend limit $0, "Help improve Claude"
   off, Devin's bundled `claude` on the owner's own login).
8. Ollama: 14 GB of weights untouched since ~April; spec D5 says delete.
9. Retire or relocate bingo's PostToolUse hook (`projects/baseball-bingo/.claude/settings.json`)
   through the bingo repo — **before E1**, which otherwise ships an observe-only carve-out (D-P1-12).
10. ~~Decide the 39-row cost recompute~~ — **done 2026-10-28** (approved and applied; see above).

## NEXT TASK — the owner picks; confirm before building

- **Tier B (E1–E10)**, in plan order starting with E1 (settings-override refusal, the one spec-§6
  item rated critical). Each task's design of record is a named line range of
  `docs/superpowers/plans/2026-09-25-multi-model-platform-p0.md`; the task's Deltas override it.
- **The trading unblock** (cut spec §7 items 3–8: per-vertical `env_files`, the broker-host deny as
  an owner PR, `db_row` DoD checks, the trading-health page, the two-repo skill drift lint, the
  atlas-side patches). This is the next plan to be *written*, and arguably worth more than Tier B
  now that the swing rows are visibly blocked on one token.
- ~~**Smaller, unblocked**: give the Codex lane one real job; persist `model_usage` per job~~ — **both done
  in the second session** (`9d31e28`, `95e1ac5`; see UPDATE). What remains of them is the post-deploy
  verification listed there.

## HOW TO BUILD HERE (each of these cost real time this session)

- **Build method that worked**: one task at a time on a branch — tests first (watch them fail),
  implement, full suite + lint, docs, an **independent `code-review` subagent before every commit**,
  commit with a `Reviewed-By:` trailer, then a whole-tier adversarial review before the merge.
  13 tasks took ~3.6 h of agent time; B4 needed 3 review rounds, A2 two.
- **Tests**: `PIPENV_DONT_LOAD_ENV=1 SERVER_ROOT="$PWD" pipenv run pytest -q -p no:cacheprovider`
  (baseline **2804 passed, 1 skipped**). The one opt-in DB test is
  `AI_SERVER_RUN_DB_TESTS=1 … tests/test_migrations.py::test_migrations_apply_cleanly` (throwaway
  `aiserver_test_<hex>` database, safe). Lint: `pipenv run python scripts/lint_docs.py` → `All clean!`.
- **The dev `.env` points `SERVER_ROOT` and `POSTGRES_DSN` at PRODUCTION.** Never start the
  runner/bot/web from dev, never run the `alembic` CLI from dev. `pydantic-settings` reads `.env`
  regardless of `PIPENV_DONT_LOAD_ENV`; `conftest.py` is what keeps tests off prod now.
- **Patch the module that bound the name**, never `src.db`: `main.py`, `jobs.py`, `telegram_bot.py`
  and `notify/outbox.py` each do `from src.db import redis / async_session` at import.
- **`psql` with no `-d`** fails on this host (no database named after the OS user). Catalog probes
  use `psql -d postgres -tAc …`; this bit the first nightly backup.
- **Pushing `origin/main` deploys.** Four gates first: origin unchanged or merged, pytest + lint,
  secret scan, CHANGELOG per `src/` commit. Origin moves under you — the fleet lands `server-patch`
  commits on its own (it did twice this session). Fetch, merge, re-run the gates, retry **once**.
- **The autopilot deploys on its own** from `healthcheck-all.sh` (5-min tick, 30-min cooldown, a
  quiet window on the tip age, and it stands down while any job is running) — expect ~10–30 min,
  and a `deploy-director` may stop at preflight and let the next tick retry. Don't dispatch a second.
- **Never** `git add -A`; stage by name. Never commit on prod. Leave the three untracked/modified
  items alone. Protected paths (`guards.py`, `lint_docs.py`, `.env`, `PROTOCOL.md`, MISSION §M, the
  three executor SKILL.md, `web.py:_check_auth`, `TELEGRAM_ALLOWED_CHAT_IDS`) need owner approval.
- **Fan-out discipline**: cap skeptic verification (all criticals + ~12 majors, 2 skeptics each).
  Three skeptics on every finding has exhausted the owner's credits before. Resume a dead workflow
  with `resumeFromRunId` rather than re-running it.
- `tests/test_cross_vendor_docs.py` and `tests/test_haiku_retirement.py` pin doc strings and ban the
  retired model literal under `src/` — read them before editing SYSTEM.md, INDEX.md, README.md,
  TROUBLESHOOTING.md or the runner/db CONTEXT files.
- **New since 2026-10-28 (landed from the fleet mid-session, `1457d0e`):** a docs *library* —
  `docs/LIBRARY.md`, `scripts/lib.py`, `tests/test_library.py`. Every `docs/**/*.md` and
  `.context/org/**/*.md` needs a front-matter block (id/type/status/date/summary); after adding or
  changing one run `pipenv run python scripts/lib.py index`, and `scripts/lib.py check` is now part
  of the deploy gate. `scripts/lib.py status <id>` / `show <id> --section <n>` reads a document
  without loading all of it — useful when context is tight. Read the updated `CLAUDE.md` §"Before
  you act" and its documentation-update map; this handoff and the recut plan are already compliant.
