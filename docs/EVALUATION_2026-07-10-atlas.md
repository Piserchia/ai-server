# Atlas project — deep evaluation (read-only audit, 2026-07-10)

> **Provenance**: produced by a dedicated parallel agent session during the
> 2026-07-10 system evaluation ([`EVALUATION_2026-07-10.md`](EVALUATION_2026-07-10.md),
> § 5 summarizes this). Scope: `projects/atlas` (runtime clone, HEAD `7f5b9e3`),
> dev repo `~/Documents/repos/atlas`, the 7 `atlas-*` server skills, launchd
> services, logs, and live DB spot-checks. No files modified.
> Remediation items are tracked as **T16** in
> [`superpowers/plans/2026-07-10-eval-remediation.md`](superpowers/plans/2026-07-10-eval-remediation.md).

---

## 1. What atlas is

**Mission** (from `CLAUDE.md`): a private, self-hosted financials/trading dashboard + agent platform. Priorities: (1) sharpen investment decisions, (2) educate via a glossary-linked UI, (3) clean sector navigation. Served at `atlas.chrispiserchia.com` behind Caddy + Cloudflare Access; port 8791.

**Architecture** (verified against code):

- **`web/`** — Next.js 15.5.20 (strict TS, app router). Routes: `/portfolio` (+ `[assetId]`), `/reports` (+ `[id]` with "Ask the analyst" chat), `/glossary`, `/indicators` (market risk dashboard + market chat), `/watchlist`, `/sectors/[sector]`, `/pm` (PM-Edge surface), plus `/api/atlas/*` typed routes. Data access via `web/lib/atlas/*` (queries.ts, engine-cli.ts which shells the Python CLI for sell/fix actions, report-gen.ts which enqueues ai-server jobs). Runs under launchd via `scripts/start-web.sh` (`next start -p ${ATLAS_WEB_PORT:-8791}`).
- **`dashboard/` (`atlas_dash`, CLI `atlas-dash`)** — the main Python 3.12 vertical: candle ingest (yfinance/ccxt), in-house golden-tested indicators, macro/on-chain feeds (FRED, bitcoin-data.com), signals, alerts (Telegram), tax lots + broker CSV importers, expert-report packet/save/evaluate pipeline, chat contexts, scout, portfolio transactions (FIFO sell, set-position, snapshots), and an APScheduler service (`atlas_dash.scheduler`: 15-min candle polls, 10s refresh-request drain, daily market-layers + outcome-scoring crons; the in-process weekly brief is **correctly gated off when `ANTHROPIC_API_KEY` is absent** and delegated to ai-server skills — clean subscription-auth design, `scheduler.py:80-95`).
- **`pmedge/` (`pm_edge`, CLI `pm-edge run|tick|status`)** — prediction-market scanner: declarative pipelines (Kalshi, Polymarket, rates-implied), deterministic ConsistencyScanner/CostGate/paper-trade Eval loop, runs under launchd.
- **`engine/`** — near-empty scaffold (`atlas_engine/__init__.py` + 1 test); shared services graduate here "on second use". Note: despite CHANGELOG prose saying "Engine (transactions.py...)", transactions actually live in `dashboard/atlas_dash/transactions.py`.
- **`crew/`** — autonomous build crew (foreman/builder/critic/librarian). **Dormant on the Mini**: no `crew/.venv`, not a hosted service (manifest: "Crew runs on demand only"), and BUILD_PLAN P3 item 0 says its LLM transport still needs the subscription-auth port.
- **DB** — Postgres 16, database `atlas`, dbmate-only schema, migrations `0001`–`0021`, sequential, no gaps. `db/schema.sql` is gitignored (runtime artifact).
- **Agent layers** — `.claude/` (12 agents, 7 commands, 6 skills incl. verify-frontend/pipeline/migration, glossary-audit, design-system), `knowledge/<sector>/` expert brains + coverage matrices, `dashboard/experts_charters/` (8 charters) + `experts_knowledge/` (6 knowledge files), `plans/` (feature plans with PROGRESS ledgers), `evaluation/` (SCORECARD + BACKLOG).
- **Deploy topology** — single-writer rule: commits born only in `~/Documents/repos/atlas`; runtime clone is pull-only (origin = dev repo); GitHub `alfredbot-ai-butler/pm-edge` is offsite backup. Deploys via `atlas-redeploy` skill (ff-only pull → dbmate → pytest gates → conditional `npm run build` → `launchctl kickstart` → healthcheck).

---

## 2. Documentation quality — verdicts per file

### Compliance with the server documentation standard

| Requirement | Status |
|---|---|
| Project `CLAUDE.md` | **Present, good** — but two stale claims (below) |
| `manifest.yml` | **Present, mostly accurate** — port/healthcheck/start commands verified; 2 stale fields |
| `.context/CONTEXT.md` (Mission/Platforms/Web Serving/Architecture/Status) | **MISSING — in both dev and runtime repos.** Atlas fails the standard outright |
| `.context/CHANGELOG.md` | **MISSING** — a root `CHANGELOG.md` exists instead (wrong path per standard, but genuinely maintained) |

Also: the server's `.context/PROJECTS_REGISTRY.md` atlas paragraph says "Three dedicated skills" — there are now **seven**. Registry is stale (server-side fix).

### Per-file verdicts

| File | Verdict | Rationale |
|---|---|---|
| `CLAUDE.md` | **keep (2 fixes)** | Excellent session directive: stack table, single-writer rule, verification-first, escalation. But (a) says "reached only over Tailscale" / Proxy row "Tailnet-only" — the live perimeter is Cloudflare Access; `docs/AI_SERVER_INTEGRATION.md` explicitly says to amend this row at go-live and it never was; (b) Models row "Anthropic API" — reports actually run via ai-server subscription skills; in-process API paths are key-less by policy. |
| `manifest.yml` | **keep (2 fixes)** | Port 8791, healthcheck `/`, start scripts all verified real. Stale: `env_required` lists `ANTHROPIC_API_KEY` (DEPLOY_RUNBOOK says "LEAVE EMPTY: subscription-only policy" — contradictory contract; not enforced by register-project.sh but misleading); `git.repo: "GitHub repo pending"` — GitHub origin exists (`alfredbot-ai-butler/pm-edge`). |
| `CHANGELOG.md` (root) | **keep + catch up** | Genuinely maintained through f8be812. **Missing entries for the last 4 code commits** (28efaae, 99f1244, 5f68c17, bfe011c, 7f5b9e3). Consider relocating/mirroring to `.context/CHANGELOG.md` per the standard. |
| `README.md` | **keep** | Best doc in the repo: accurate map table, quick start, operating runbook (ship/closeout/status), rules. Current. |
| `PROGRESS.md` (root) | **refactor/merge** | Verification-evidence log, stale since ~migration 0017 era; newer evidence lives in `plans/*/PROGRESS.md`. Either declare canonical and resume appending, or fold into SESSION_HANDOFF. |
| `docs/AGENT_SYSTEM.md` | **keep** | Map of the `.claude/` builder layer (11 agents/6 skills/7 commands — matches disk). |
| `docs/AI_SERVER_INTEGRATION.md` | **refactor** | Load-bearing living sections (scheduling-ownership rule, §Deploying changes — referenced from README and scheduler.py) mixed with a stale draft manifest and completed plan steps. Trim to the living contract. |
| `docs/BUILD_PLAN.md` | **keep** | Milestone ladder; §1 shipped / §2 current (P3) still plausible. |
| `docs/CREW.md`, `docs/INSTALL_CREW.md` | **keep, mark dormant** | Accurate docs for a subsystem not installed on the Mini (no crew/.venv; subscription port pending P3.0). A "DORMANT" banner would prevent wasted agent effort. |
| `docs/DASHBOARD.md` | **keep** | Accurate vertical description (0003 reconciling migration, doctor contract). |
| `docs/DATA_SOURCES.md` | **keep** | Dated research (July 2026), verified flags, still the reference for pm-edge feeds. |
| `docs/DEPLOY_RUNBOOK.md` | **archive/merge** | One-time go-live runbook, executed 2026-07-08. Now misleading ("Staged and waiting", "applies 0001..0004" vs 0021). Extract the CF Access recipe into AI_SERVER_INTEGRATION, mark historical. |
| `docs/EFFICIENCY_REVIEW.md` | **keep** | Short dated review + implementation record; all 5 steps landed, cross-referenced to commits. |
| `docs/INSTALL_DASHBOARD.md` | **keep** | Compose/dev-path install; consistent with "Docker = dev-only" decision. |
| `docs/MARKET_TRACKER_INTEGRATION.md` | **archive (mark DONE)** | Plan whose P4.1–P4.6 work shipped. Valuable rationale record; needs a COMPLETED banner so it stops reading as pending. |
| `docs/MERGE_PM_EDGE.md` | **keep** | Explicit historical merge record (decisions of record). |
| `docs/PM_EDGE.md` | **keep** | Vertical thesis + 3-layer architecture; matches code. |
| `docs/SESSION_HANDOFF.md` | **refactor (rotate)** | 536 lines / 37 KB append-only session log, ~20 dated sections in 3 days; "newest at BOTTOM" forces full reads. Rotate closed sections to an archive; keep current picture + last 2–3 sessions. |
| `plans/` | **keep** | Live planning system; both plans complete with PROGRESS ledgers. |
| `evaluation/SCORECARD.md`, `BACKLOG.md` | **keep** | Live; BACKLOG's open `[ops]` item corroborates the learn-loop finding below. |
| `knowledge/**`, `crew/README.md` | **keep** | Sector brains + coverage matrices, budgeted per CLAUDE.md. |

**CLAUDE.md effectiveness**: strong — concise, rule-dense, verification-first, encodes the 2026-07-09 incident as the single-writer rule. The two stale rows are the only defects; "Tailnet-only" matters because agents may make perimeter/security decisions from it.

**CHANGELOG vs git log**: maintained through `f8be812` (2026-07-10); the four subsequent feature commits have no entries (grep for "52-week", "watchlist tab", "indicator chips": 0 hits).

---

## 3. File hygiene — candidates

| Path (runtime clone) | Evidence | Recommended action (in DEV repo unless noted) |
|---|---|---|
| `.DS_Store` (root, **tracked in git**) | `git ls-files` hit; `.gitignore` has no `.DS_Store` entry | `git rm --cached .DS_Store`; add to `.gitignore` |
| `dashboard/atlas_dash.egg-info/`, `pmedge/pm_edge.egg-info/` | Untracked, generated by `pip install -e` | Add `*.egg-info/` to `.gitignore` |
| `.superpowers/sdd/` (progress.md + 6 task briefs) | Untracked scratch from a superpowers SDD session run **inside the runtime clone** (should have been dev) | Human: confirm mirrored/obsolete, then delete from runtime |
| Branch `backup-2026-07-09` @ 0bec2d2 (runtime clone) | Leftover from the 2026-07-09 divergence incident; recovery complete (dev==runtime at 7f5b9e3) | Human: confirm nothing unique, delete branch |
| `dashboard/experts_knowledge/crypto_analyst.md` (dirty, +1 line) | Runtime-written learn entry (2026-07-10) not yet rescued dev-ward; runtime is supposed to be pull-only | Port the line to dev (ship heal step); see rec #3 |
| `docs/DEPLOY_RUNBOOK.md` | Executed one-time runbook; "applies 0001..0004" (now 0021) | Mark historical / merge |
| `docs/MARKET_TRACKER_INTEGRATION.md` | Plan fully executed (P4.1–P4.6 shipped) | Add COMPLETED banner |
| `PROGRESS.md` (root) | Newest evidence ~0014–0017 era; superseded by `plans/*/PROGRESS.md` | Merge or declare canonical |
| `manifest.yml` `env_required: ANTHROPIC_API_KEY` | `.env` deliberately omits it (subscription policy); unenforced but misleading | Remove from `env_required` |
| `volumes/logs/project.atlas.err.log` (server side) | 5 stale `output: standalone` warnings from before the next.config fix (last write Jul 9 17:02) | None; ages out |
| `web/tsconfig.tsbuildinfo`, `.pytest_cache/`, `.ruff_cache/`, `db/schema.sql` | On disk but properly gitignored | No action |
| `docker-compose*.yml` (4 files) | Not in the Mini's boot chain, but documented dev/portable path | Keep |
| `dashboard/profiles_seed.json`, `scout_universe.json`, `glossary/terms.json` | All referenced (cli.py seed-profiles; scout.py; glossary-audit skill) | Keep |

No orphaned scripts in `scripts/` — all 8 are referenced by plists, manifest, skills, or README.

---

## 4. Skill ↔ project contract check

Every command/path the 7 skills invoke, verified against `dashboard/atlas_dash/cli.py` (cmd function / parser registration lines), scripts, and infra. **Result: no hard breaks — all CLI verbs and flags exist.** Four soft findings at the bottom.

| Skill expectation | Found where | Status |
|---|---|---|
| `dashboard/.venv/bin/atlas-dash` | pyproject `[project.scripts]`; scheduler service runs from this venv | OK |
| `atlas-dash packet [SYMBOL \| --sector \| --tax \| (none)=portfolio]` | cli.py:626 / parser :852–856 | OK |
| `packet` JSON names `charter_path` + `knowledge_path` | cli.py:655, 285, 317, 348, 402 | OK |
| `save-report --symbol/--sector/--tax --payload-file --packet-file --model` | cli.py:693 / :861–870 (+ `--expert`) | OK |
| `learn <expert> "<rule>"` | cli.py:662 / :857–859 | OK |
| `report-targets` | cli.py:676 / :860 | OK |
| `refresh` | cli.py:124 / :805 | OK |
| `scout-universe` / `scout-save --payload-file --snapshot-file --model` | cli.py:452, 463 / :871–875 | OK |
| `chat-context [<uuid> \| --asset S \| --market \| --portfolio]` | cli.py:356 / :876–884 | OK |
| `--portfolio` context carries `lots` + `realized_ytd` + charter | cli.py:334–348 | OK |
| `chat-save [<uuid> \| --asset \| --market \| --portfolio] --kind chat\|analysis --role --content-file` | cli.py:410 / :885–895 | OK |
| `sell SYM --qty --price --date --json` | cli.py:540 / :809–817 (+ `--account`) | OK |
| `set-position SYM --qty --json` | cli.py:567 / :818–823 (+ `--avg-cost`) | OK |
| `add-holding <SYMBOL> <QTY> <COST_PER_UNIT>` (per-unit basis) | cli.py:83 / :785–789 | OK |
| `portfolio` | cli.py:111 / :794 | OK |
| `signals` (daily-brief) | cli.py:525 / :832 | OK |
| `snapshot-portfolio` (auto after transactions) | cli.py:591 / :824 | OK |
| `psql atlas` + `scout_candidates.status='suggested'` (daily-brief) | table from `db/migrations/0016_scout.sql`; psql live | OK |
| `.env` at project root | present (no ANTHROPIC_API_KEY, by policy) | OK |
| redeploy: `dbmate --migrations-dir db/migrations up` | 21 migrations applied | OK |
| redeploy: pytest gates in dashboard/, pmedge/; `npm ci`/`npm run build` | venvs + package-lock.json present | OK |
| redeploy: `launchctl kickstart` the 3 labels | all three plists exist, services run | OK |
| redeploy: `scripts/atlas-status.sh`; curl :8791 → 200 | script exists; live curl 200 | OK |
| sweep: `enqueue_job` MCP fan-out | server-side runner; documented sequential fallback | OK (by design) |
| Reports at `atlas.chrispiserchia.com/reports` | Caddyfile.d/atlas.conf → :8791; web/app/reports | OK |
| **atlas-redeploy Gotchas → `docs/TROUBLESHOOTING.md` §diverged** | **No such file in atlas**; section lives in the SERVER repo's `docs/TROUBLESHOOTING.md:427` | **Broken pointer** |
| atlas-chat/daily-brief: "Read charter AND knowledge" (market scope) | charter exists; **`experts_knowledge/market_analyst.md` does not** (path still emitted); same for report_critic | Soft gap — seed empty file |
| sweep gotcha "Kraken BTC feed broken" | feed_status: ccxt:kraken success today, 0 errors → fixed | Cosmetic staleness |
| atlas-portfolio "web enqueues kind: atlas_portfolio" | web/app/api/atlas/portfolio-chat/route.ts + CHANGELOG (kind-routing post-incident) | OK |

---

## 5. Operational state

**Services**: all three loaded and running — `com.assistant.project.atlas` (PID 69944), `atlas-dash-scheduler` (PID 56742), `atlas-pm-edge` (PID 66736). Last-exit `-15` = SIGTERM from `kickstart -k` restarts (expected, not crashes).

**Plists**: consistent and correct — `bash -lc "cd <runtime clone> && ./scripts/start-*.sh"`, WorkingDirectory set, PATH incl. pyenv shims + homebrew, `RunAtLoad`, `KeepAlive={SuccessfulExit:false, Crashed:true}`, `ThrottleInterval 30`, logs to `volumes/logs/`. Start scripts source `.env` themselves (plists carry no secrets).

**Health**: `curl 127.0.0.1:8791/` → **200**; Next.js 15.5.20 "Ready in ~218ms". Manifest healthcheck `/` matches. Caddy: `http://atlas.chrispiserchia.com → localhost:8791` (TLS at the Cloudflare tunnel).

**Logs**:
- Web err: only 5 stale `output: standalone` warnings (config since fixed; last write Jul 9 17:02). Resolved.
- dash-scheduler: healthy `poll.ok` across ~30 symbols today; benign APScheduler noise (10s drain job occasionally skipped/missed by ~2s). One oddity: a 404 for symbol **ZZAGENT** — test-looking symbol polled in production; not in the live `assets` table now. *[Coordinator note: the jobs table shows the owner ran "atlas-portfolio: I sold 4 shares of ZZAGENT…" on 2026-07-10 — the symbol most likely entered as a real holding while the owner exercised the portfolio manager, then left via that sale. The test-isolation check below is still worth doing, but owner-testing is the likelier source.]*
- pm-edge err (70 KB): **hundreds of repeats** of `rates_implied: no ZQ quotes available from yfinance; skipping cycle` + `$ZQX26.CBT: possibly delisted`. The 28efaae fallback is deployed but the feed still yields nothing → the rates-implied pipeline (1 of 3) is dark and spams the err log every tick. Kalshi/Polymarket fine (14 ladders checked; CostGate/Eval ticking; 0 paper positions).
- `feed_status` (live DB): bitcoin-data.com, ccxt:kraken, yfinance — all success today, `error_count 0`.

**Schedules** (server `assistant` DB): `atlas-daily-brief` @ `0 12 * * *`, `atlas-weekly-reports` @ `0 18 * * 0` → kind `atlas-report-sweep`; both unpaused; matches skill docs. In-process weekly brief correctly self-disables without an API key (`weekly_brief.delegated`).

**Dev ↔ runtime divergence**: none — both at `7f5b9e3`; dev tree clean; GitHub remote in sync as of last fetch (cannot fetch read-only). Runtime dirt: 1 modified tracked file (`crypto_analyst.md`, +1 learn line pending rescue), untracked `.superpowers/` + 2 `egg-info/` dirs, leftover `backup-2026-07-09` branch.

**Dependency posture**: npm locked (`package-lock.json`, `npm ci`). Python range-pinned only (`anthropic>=0.40`, `yfinance>=0.2`, ...) with no lockfile — reinstalls can pull breaking majors; the pytest gate is the only net.

---

## 6. Ranked recommendations

1. **Create `.context/CONTEXT.md` (exact 5 sections) + `.context/CHANGELOG.md` in the dev repo.** Atlas — the flagship hosted project — fails the server documentation standard; cross-project agents reading the registry are told to drill into a file that doesn't exist. Distill from README + manifest (~30 min). Also fix the registry's stale "Three dedicated skills" → seven (server-side).
2. **Fix the two stale CLAUDE.md claims**: perimeter "Tailnet-only" → Cloudflare Access (the amendment was explicitly promised in AI_SERVER_INTEGRATION at go-live and never made — agents currently reason from a wrong security model), and Models row → subscription-auth reality.
3. **Close the learn-loop write-path tension permanently** (open BACKLOG [ops] item): `atlas-dash learn` writes to **tracked** files in a pull-only clone; `crypto_analyst.md` is dirty right now, and any dev-side edit to the same file will make the next ff-only deploy refuse. Move `experts_knowledge/` to an untracked var dir (packet already passes absolute paths) or run the ship heal eagerly; meanwhile rescue the pending line.
4. **Fix or silence the pm-edge rates_implied feed**: pipeline dark despite 28efaae (`ZQX26.CBT` yields nothing via yfinance); err-log spam buries real errors. Source ZQ quotes elsewhere (per DATA_SOURCES.md) or back off to hourly with one summary line.
5. **Manifest hygiene**: drop `ANTHROPIC_API_KEY` from `env_required`; update `git.repo` ("GitHub repo pending" → real remote).
6. **CHANGELOG catch-up + doc-rot pass**: append the 4 missing commit entries; banner DEPLOY_RUNBOOK and MARKET_TRACKER_INTEGRATION as historical/completed; rotate SESSION_HANDOFF (536 lines); merge or revive root PROGRESS.md.
7. **Git hygiene in dev**: untrack `.DS_Store`; gitignore `.DS_Store` + `*.egg-info/`. Human-confirmed runtime cleanups: `.superpowers/sdd/` scratch and the `backup-2026-07-09` branch.
8. **Skill text fixes** (server repo): atlas-redeploy's `docs/TROUBLESHOOTING.md` pointer → the server repo's `docs/TROUBLESHOOTING.md` §"atlas redeploy reports diverged"; soften the sweep's now-fixed Kraken gotcha.
9. **Test isolation check**: confirm deploy-gate pytest targets `atlas_test`, not live `atlas` — see the ZZAGENT coordinator note in § 5.
10. **Smaller wins**: Python lockfile (uv/pip-tools) for reproducible redeploy installs; seed empty `experts_knowledge/market_analyst.md` + `report_critic.md`; optional docs/README index.

**Overall**: atlas is in strong operational shape — services healthy, deploys gated and disciplined, dev/runtime in sync, and the skills' CLI contract fully intact (zero hard mismatches across ~25 checked verbs/flags/paths). The real gaps are documentation-standard compliance (`.context/` missing entirely), a few stale claims in high-authority files (CLAUDE.md perimeter, manifest env), one degraded data feed (rates_implied), and the structural learn-loop/pull-only tension currently patched only by the ship heal step.
