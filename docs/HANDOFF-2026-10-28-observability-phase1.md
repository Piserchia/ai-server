# Handoff — ai-server, Observability Phase 1 (as of 2026-10-28)

> Written to reset a session's context. Read this, then
> `docs/superpowers/plans/2026-10-21-observability-phase1-recut.md` (§0 deltas, §3 decisions,
> §7 owner actions, §8 exit criteria, §11 deployment log). Everything below is verified against
> the tree and prod, not recalled.

## STATE

**Everything built is merged, pushed and deployed. Nothing is in flight.** `main` == `origin/main`
== prod HEAD at `c4dbb0b`; alembic head **008**; working tree clean apart from three items to leave
alone: modified `.claude/settings.local.json`, untracked `.superpowers/` and `AGENTS.md`.

- **Codex lane** — live since 2026-10-21 (migration 007, `ROUTER_PROVIDERS_ENABLED=anthropic,codex`
  in prod `.env`). Unchanged by this work and **still unexercised since**: no `codex/*` job has run,
  so the executor-lane half of B3 (token columns, `cli_version` from `ExecResult`) is untested live.
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
- **Smaller, unblocked**: give the Codex lane one real job so B3's executor path is exercised; or
  persist `model_usage` per job so the ledger can attribute a multi-model session per model (the
  residual computed-vs-SDK divergence, and the only honest way to settle which cache-write TTL the
  vendor billed).

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
