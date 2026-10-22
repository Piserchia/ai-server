# MoneyMachine Company — a bucketed, self-running agent company for making the owner money (design)

**Date:** 2026-10-21 (review round 1 folded in the same day — see Amendments)
**Status:** BUILT-IN-SESSION under the owner's delegation ("Here is the spec for a
new project. Create it", 2026-10-21). The owner opted out of the question round,
so every how-it-gets-made choice below is the designer's call and is marked as
such; the items only the owner can settle are in §16 and are *not* assumed.
Nothing in this design touches money, credentials, or a protected path. It is
an instance of the atlas loop constitution (`evaluation/LOOP.md`) and the
server org (`.context/org/ORG.md`), not a parallel organisation.

> Reading order for a builder: §3 (binding constraints) → §4 (the company) →
> §5 (repo layout) → §6 (the loop) → §7 (skills) → §8 (information passing) →
> §9 (shared tooling) → §10 (governance) → §14 (ai-server touchpoints and
> landing order). §16 is for the owner.

## 0) What this is, and what it is not

**It is** a new project repo, `moneymachine`, that organises money-making work
into domain buckets, gives every bucket the same six-officer hierarchy (CEO,
Research, Bridging, Architect, Engineering, Execution) expressed as *shared*
ai-server skills parameterised by bucket, and runs itself on three schedule
rows (a weekly CEO, a weekly reporter, a daily cheap resumer) that fan out
through dispatch chains. It produces, per bucket: a knowledge library answering
"what is the best way to make money in this domain", sealed actionability
cards, architecture plans, implementations with quant-law validation reports,
shadow execution reports, grades, and a weekly owner memo.

**It is not** an order path. Under MISSION §M / INV-22 nothing in this repo
places, modifies, or cancels an order, holds a broker or exchange credential,
mounts a broker tool, or widens any existing kernel. Paper executors count as
order paths (MISSION §M INV-22 last bullet; 2026-10-05 spec §7), so this
company builds no executor of any kind, crypto included. A validated strategy
leaves this company only as a **graduation offer** to the owner (§10.3),
exactly as alpha-lab's GO does. The owner's phrase "autonomy to greenlight
anything to reach the goal" is honoured for everything that cannot lose money
(research, builds, shadow books, reports, dispatch) and is bounded, in the
owner's own standing rules, for everything that can (§10.4).

**Credentials, stated honestly:** this repo holds none and requests none, but
credentials are ambient on the box — the atlas dev clone's `.env` carries
Alpaca keys for every job on the Mini. The enforceable boundary is therefore
the *code surface* (what this repo imports and calls) plus the tripwires
(§10.2), exactly as atlas `value/CLAUDE.md` states it. The Atlas bridge
imports only pure `quantlab` modules and never `quantlab.data` or
`tradingcore` (§9.3).

**It does not duplicate Atlas.** Atlas already holds paper/shadow/report-only
verticals for three of the four buckets plus the shared validation stack
(`quantlab`), the trading library (`tradingcore`), the feed engine
(`atlas_engine.feeds`) and the only sanctioned order path (`swing/`).
MoneyMachine *wraps* those as read-only substrate (§9.3) and builds only what
no vertical covers (today: the whole crypto bucket, every arbitrage lane except
prediction markets, and the cross-bucket company layer).

## 1) Intent and the why

The owner's spec (verbatim, `~/Downloads/MoneyMachine Company-2.md`, 2026-10-21):

> A company that splits money into five buckets: ETF investing; long term
> investing; short term investing/trading; crypto trading. Keep arbitrage as
> one of many but always primary opportunity within each space. Each bucket
> contains the same agent hierarchy inside but built out specific to the
> domain of that bucket. Build out/schedule these agent hierarchies to run by
> themselves and build out their domain projects with 1 goal in mind:
> Maximizing making me money. [Hierarchy: CEO; Research EO; Bridging EO;
> Architect EO; Engineering EO; Execution EO — each "organizes, creates,
> evaluates, optimizes" the agents under it.] Be explicit about documenting
> goals/intention/feedback loops & contracts … reporting should be required
> out of most systems … suites should ask "how can I get better as a system"
> … share tools/data that many of them need.

The reading this design takes (designer's call; the one real gap is §16 D1):

- **"Five buckets"** — four are named. The fifth is reserved as a templated
  slot (`buckets/_TEMPLATE/`) and is owner decision **D1**; the recommended
  candidate is *prediction-market / event arbitrage*, because it is the only
  arbitrage machinery the estate already owns (`pmedge/`) — but that scanner
  is currently structurally unable to emit (§3.2), so the slot stays empty
  until the atlas-side defects are fixed.
- **"Arbitrage … always primary opportunity within each space"** — every
  bucket's hypothesis-family registry opens with an `arbitrage` family that
  the Research officer must address first each cycle (§6.5). It is a
  *priority*, not a promise: the inherited evidence (§3.2) already shows
  ETF-NAV arbitrage dead on free daily data; the officers inherit those
  lessons instead of re-learning them, and only an untested arbitrage sub-lane
  or an owner-closed note lets a cycle look elsewhere.
- **"Same hierarchy, built out specific to the domain"** — one skill per
  officer, shared by all buckets, reading the bucket's own charter, officer
  specialisations, library, families and ledger. Domain specificity lives in
  the bucket directory, not in duplicated skills.
- **"Run by themselves"** — three scheduled rows (`mm-ceo-weekly`,
  `mm-report-weekly`, `mm-resume-daily`) drive everything else by dispatch,
  inside owner-owned caps (§12).
- **"Maximizing making me money"** — honoured as *the company's objective
  function*, reported honestly: the estate's standing evidence is that the
  reliable money is cash yield plus broad-market beta, that LLMs are not an
  alpha source, and that the money in a validation desk "is in not deploying
  noise" (§3.2). The CEO memo leads with that expectation every week.

## 2) Goals, non-goals, anti-goals

**Goals**

1. Four live buckets (`etf`, `longterm`, `shortterm`, `crypto`) each with a
   charter, an officer hierarchy, a knowledge library, a hypothesis-family
   registry that leads with arbitrage, an append-only ledger, trials
   registry, lessons file, backlog and chain state.
2. A closed loop per bucket: research → bridge → architect → engineer (with
   quant-law validation) → execute → grade, one stage per job, resumable from
   committed state, capped by an owner-owned budget, with every handoff a
   committed artifact.
3. A company layer: a read-only CEO that allocates attention across buckets
   weekly and dispatches; a scheduled reporter that records CEO decisions and
   writes the owner memo even when the CEO failed; a daily resumer that keeps
   chains moving; a company ledger and lessons file.
4. Shared tooling (`mmcore`, stdlib + pyyaml; `shared/adapters`, keyless
   urllib) for ledgers, state, budgets, trials, shadow-book accounting,
   reports, free daily closes and the read-only Atlas bridge — used by every
   bucket, owned by none.
5. Every contract written down: goals, intentions, feedback loops, handoff
   formats, ceilings, graduation, front door for self-change, and the apply
   path for an owner-approved `[system]` item.
6. Lint-clean, gate-green landing on the INV-4 lane with no `src/` change.

**Non-goals (this build)**

- No hosted web page; owner-facing output is committed memos, job summaries,
  and the on-demand Telegram pull (§11). A dashboard is a later `[design]`
  item.
- No data adapters beyond the Stooq daily-closes adapter, a CSV loader and
  the Atlas bridge; Engineering officers build further adapters per
  architecture plan, under the free-data rule.
- No server-side changes: no new router rule, no new event trigger, no DM
  publisher, no dispatch allowlist (deferred, §17).
- No fifth bucket content (D1).

**Anti-goals (would make this a failure even if it "works")**

- Any file in this repo or any `mm-*` skill that can reach a broker,
  exchange private endpoint, or order tool. Enforced by tripwire tests
  (§10.2).
- A second knowledge store that forks Atlas's `knowledge/<sector>/` and the
  Knowledge division's `projects/research`. The library format is Atlas's
  claim format and cites Atlas's libraries by path.
- Thirty scheduled opus jobs a week. The envelope is §12.
- A CEO that can be talked into writing. The CEO is `privilege_class:
  read-only`, hook-enforced (INV-20).
- Payload-only inputs. The runner never injects `job.payload` into a prompt
  (live job f8204991 proved it); every input rides in `job.description`
  (§8.1).
- A dispatch of any non-`mm-*` kind. Prose today, a test on every skill body
  (§10.4), a server-side allowlist later (D7).

## 3) Binding constraints

### 3.1 Mechanical and governance constraints

| Constraint | Source | Consequence for this design |
|---|---|---|
| No ai-server skill/session ever places, modifies or cancels a brokerage order; any new order path (a trading skill, a second executor, widened limits, un-pinned sandbox) is a protected-path change — owner approval, never autonomous; brokerage creds live only in the atlas project env; the paper trader stays paper | `MISSION.md` §M INV-22 (incl. last bullet); `.context/SYSTEM.md` INV-22 | No executor, no paper executor, no exchange keys in this repo. Crypto "trading" = shadow book from public data. Strategy hand-off is an owner-facing graduation offer (§10.3) |
| The subscription lane is never the decision step for a live order; broker MCPs stay off the box; "mounting even a paper-order tool is an LLM-reachable order path"; read-only data MCPs are a separate decision, default no; "market data keeps flowing through code" | `docs/superpowers/specs/2026-10-05-observability-and-trading-unblock-design.md` §7 | No MCPs mounted; keyless urllib adapters in deterministic code are market data flowing through code (§9.2) |
| Free / keyless data only; paid data is a rejected lane, never budgeted | atlas `CLAUDE.md` § Repo conventions (owner 2026-08-03); atlas `evaluation/LOOP.md` §6 | Bridging cards verdict `BLOCKED-ON-DATA` instead of designing around a paid feed |
| Skills holding Bash/Write/Edit must declare `isolation: workspace`; the unisolated allowlist lives in the protected lint file; read-only guard hooks win over workspace hooks when both apply | `scripts/lint_docs.py` `check_unisolated_writers`; `src/runner/session.py` guard-profile selection | Every skill with Bash is workspace-isolated, *including* the read-only CEO and resumer (read-only hooks still bind; the workspace only gives them `git fetch` + psql SELECT) |
| `role: manager|ceo|connector|auditor` ⇒ `privilege_class: read-only` + `permission_mode: plan|acceptEdits`; read-only + `needs-dispatch-mcp` ⇒ `acceptEdits`; charter Role/Privilege must match frontmatter character-for-character; `governor` is outside the oversight set | `scripts/lint_docs.py` `check_role_privileges`; precedent `atlas-swing-evaluate` | `mm-ceo` is `role: manager`, read-only, acceptEdits. Bucket governors are `role: governor` + `guarded-writer` because a writing CEO cannot be expressed in lint's vocabulary |
| Every skill: parseable frontmatter, `## Gotchas`, ≥10 body lines, existing `context_files`, model in the gateway alias table (`_MODEL_ALIASES`, `src/gateway/telegram_bot.py`; becomes `models.yml` when the cross-vendor branch lands), one charter roster row, one SKILLS_REGISTRY row; `post_review` is a **mapping** (`post_review:\n  trigger: always`) — a bare scalar is swallowed silently at runtime | `scripts/lint_docs.py`; `tests/test_doc_lint.py`; `tests/test_skill_contracts.py`; `src/runner/main.py` `_maybe_review` | §14 checklist; the new `tests/test_mm_skills.py` pins the mapping form |
| `tests/test_skill_contracts.py` resolves `settings.skills_dir` from `.env`'s `SERVER_ROOT`, which points at PRODUCTION — plain `pytest` in a dev checkout validates prod's skills, not the branch's | `src/config.py`; dev `.env` line 35 | Gate step: `SERVER_ROOT="$PWD" … pytest tests/test_skill_contracts.py tests/test_doc_lint.py tests/test_mm_skills.py` from the worktree |
| A job is scoped to a project only by `payload.project_slug`; the PROD checkout must hold `projects/<slug>/manifest.yml` or the job silently runs unscoped (a workspace job would clone ai-server itself) | `src/runner/session.py` `_resolve_project`; `src/runner/delivery.py` | Every schedule row and every dispatched child carries `{"project_slug":"moneymachine"}`; the prod runtime clone is created *after* the registry row deploys and *before* the first Saturday slot (§14.3) |
| Manifest `type` ∈ {static, service, api}; `dev-repo` requires `dev_repo` + `runtime_clone: pull-only`; `deployable: false` needs no gates; `delivery-ops-reconciler` keys drift on "a `projects/<slug>/` with a manifest but no projects DB row / Caddy conf" and routes to `new-project` register-only, which for `type: static` would publish the directory with `file_server` and no CF Access | `src/registry/manifest.py`; `skills/delivery-ops-reconciler/SKILL.md` §3–§4; `scripts/register-project.sh` | §5.2 manifest has no `web_root`, its description's first line says NOT HOSTED; the registry row says "do not register"; Gotcha appends on the reconciler and `new-project` register-only mode (§14.1) |
| `job.payload` is never injected into the prompt; `session_timeout_seconds` is the ONLY timeout source (payload, clamped [60, 5400], default 1800); a workspace clone survives only via `git push`; max_turns exhaustion = job **completed**, workspace deleted, no escalation | `src/runner/session.py`; `src/runner/main.py` `_session_timeout`; INV-16 | §8.1 description grammar; §6.4 chain mechanics with per-target timeouts; push before the turn reserve |
| The runner does not DM scheduler- or dispatch-created job summaries; a Telegram `/task --kind=<skill>` creates a TASK (task preamble, `_evaluate` on `TASK_COMPLETE`, auto-continue of the same kind without it; children inherit `task_id`); `/schedule` offers list/add/pause/resume only | `src/gateway/telegram_bot.py`; `src/runner/main.py` `_update_task_after_job`; `src/runner/mcp_dispatch.py` | Owner reporting = committed memo + on-demand `mm-report` pull (never dispatches, ends with `TASK_COMPLETE:`); manual CEO trigger = a `next_run_at` nudge, never `/task --kind=mm-ceo` (§11, OWNER.md) |
| Sessions inherit the runner's PATH: `python` = the ai-server prod venv, `python3` = Apple 3.9.6, `python3.12` = the venv's 3.12 | `~/Library/LaunchAgents/com.assistant.runner.plist`; live audit `2d4dba59` | Every skill creates a per-job venv: `python3.12 -m venv .venv && .venv/bin/pip install -q pytest pyyaml`; never writes `python`/`python3`; `mmcore preflight` asserts ≥ 3.12 and `import yaml` |
| The dev clone is fast-forwarded only after a SUCCESSFUL workspace session; a workspace clone starts from the dev clone's HEAD (origin re-pointed, no fetch) | `src/runner/workspaces.py`; `src/runner/session.py` `sync_canonical` | §6.4 step 0: every session fetches first; writers `git pull --ff-only origin main`, read-only sessions read `git show origin/main:<path>`; `mmcore preflight` fails when behind origin |
| Only `scripts/seed-schedules.sh` writes schedule rows (cadence); it never un-pauses; a push to `origin/main` is auto-deployed by the healthcheck autopilot within ~10–40 min; `schedule_adherence` DARK keys on a *missing* job, FAILURE_STREAK on 3 — a weekly row that fails is silent for three weeks | `scripts/seed-schedules.sh`; `scripts/healthcheck-all.sh`; `src/runner/schedule_adherence.py` | Three rows seeded at verified-free slots; the reporter is scheduled (not dispatched) so a failed CEO is written into a memo the same evening; kill switch `/schedule pause mm-ceo-weekly` |
| The idle-queue drainers are suppressed by any stranded `queued` row; no server-side per-vertical dispatch valve or per-spawner kind allowlist exists (`_FORBIDDEN_KINDS = {"god"}` only) | `src/runner/events.py`; `src/runner/mcp_dispatch.py` | Caps are enforced in-skill by `mmcore budget` + psql counts of exact stage kinds (§12.2); the `mm-*`-only dispatch rule is a body sentence pinned by `tests/test_mm_skills.py` until D7 |
| The in-flight `multi-model/cross-vendor-writer` branch (local, unpushed, 11 ahead) owns `src/`, runner docs, `skills/README.md`, `skills/TEMPLATE.md`, `tests/test_skill_contracts.py`, SYSTEM.md's module graph, SKILLS_REGISTRY line 24, INDEX.md line 98; local `main` carries an unpushed stray commit and is behind origin | `git diff --stat origin/main..multi-model/cross-vendor-writer`; `git branch -vv` | This build touches none of those; shared-registry edits are append-only at EOF anchors; the push goes from the worktree branch straight to `origin main` (§14.2) |
| Managers/CEO are chartered by the org CEO through the proposal lane; every skill lives in exactly one division; the Delivery charter's "atlas is the only one today" sentence drifts silently | `.context/org/ORG.md` § How to extend the org; `.context/org/divisions/delivery/CHARTER.md` | A new division `moneymachine` chartered under the owner's 2026-10-21 delegation (§16 D0); `mm-ceo` added to `system-manager`'s roster query; the Delivery sentence updated |
| Learning extractor drops `module=project` learnings | `src/runner/learning.py` | Lessons live in-repo (`LESSONS.md` per bucket + company), one line per terminal decision |

### 3.2 Inherited evidence the Research officers may not re-learn

Quoted or summarised from the estate's own documents (`docs/research/llm-landscape-2026-09/crosscut-finance-trading-ai.md`;
`docs/superpowers/plans/2026-08-26-autonomous-trading.md`; atlas `plans/trader/DESIGN.md`;
atlas `alpha-lab/evaluation/LESSONS.md`; atlas `quant/evaluation/LEDGER.md`; atlas `CHANGELOG.md`):

- LLMs are not an alpha source: post-cutoff decay of 50–72 % ("Profit
  Mirage"), population-scale fleets with no directional edge, an
  honest-evaluation study that rejected every LLM-discovered strategy. The
  Alpha Arena result (four of six frontier models lost 42–59 % on crypto
  perps) is a *secondary source with unverified dates* — grade C, carry the
  caveat.
- Short-horizon retail trading is reliably negative-EV (Taiwan, Brazil).
- The grade-A money is cash yield on idle capital plus broad-index beta; a
  slow trend overlay is grade B for drawdown truncation and grade C for
  return edge; "expected return edge vs SPY ≈ 0 or slightly negative".
- The quant desk has run 28 validations and issued 28 REJECTs. Alpha-lab
  holds 22 structured lessons; the dominant one is the "hollow-gross law" (a
  not-fired gross clause measured against zero is not a mechanism).
- Arbitrage specifically:
  - ETF-NAV / levered-ETF rebalance arbitrage is tested and dead on free
    daily data (A-0007, A-0013, A-0015, A-0016); primary-market AP arbitrage
    is behind the free-data ceiling.
  - Prediction-market arbitrage is **UNMEASURED**, not null: the `pmedge`
    scanner has emitted 0 rows in 76 days because two detectors iterate an
    empty `STRUCTURES` map ("empty by construction; never able to emit") and
    the one committed event-map pair expired 2026-09-15/16 (atlas CHANGELOG
    2026-09-29 and 2026-10-19). A scanner structurally unable to emit says
    nothing about the market — grade F / unmeasured, and the inverse of the
    hollow-gross lesson if ever cited as evidence.
  - Equity stat-arb has no direct trial; its nearest priors are alpha-lab
    F-04's pairs-residual kills (A-0017, A-0018, A-0021, A-0023, A-0024): a
    pair residual that is the traded leg's own return in disguise dies at the
    "0.5643 contamination line" — any pairs/residual conditioner must show
    corr(conditioner, traded leg's own return) < 0.5643 on the card or it is
    a re-mine.
  - Cross-exchange crypto arbitrage and funding/basis carry are not
    addressed anywhere in the estate — those lanes start with zero priors and
    must say so.
- Crypto substrate status (atlas): `dashboard/atlas_dash/perps.py` (OKX
  public funding/OI via ccxt) was BUILT 2026-10-16 but refused `built → live`
  (no `feed_status` row); the ccxt:kraken candle feed sat STALE for about
  four weeks from 2026-08-23 (`error_count` 118 → 3,264; root cause one
  never-listed symbol, CBETH, pinning an all-symbol-success rule; fixed by
  partial-symbol success, atlas `6d0464a`). The crypto bucket starts with
  data *patterns*, not live data.
- "Live statistical significance is unreachable on our timescale (SR≈1 needs
  ~15 years of monthly observations)"; a well-documented null result is a
  process success.

Every bucket `knowledge/LIBRARY.md` ships seeded with these claims (graded,
sourced, dated) so the first research cycle starts from the estate's
knowledge, not from zero.

## 4) The company

### 4.1 Buckets

| Slug | Name | Mandate | Arbitrage lane (first family) | Atlas substrate it wraps (read-only) | Cycle-1 question (seeded in the charter) |
|---|---|---|---|---|---|
| `etf` | ETF investing | Best way to make money with ETFs: allocation, trend overlays, cash sleeves, costs | ETF premium/discount, rebalance-flow, creation/redemption — sub-lanes premium/discount and levered-rebalance are `saturated` by A-0007/13/15/16; an untested sub-lane or an owner-closed note is required to look elsewhere | `trader/` (SPY↔SGOV paper policy, Alpaca PAPER), `quant/` validation desk, `k401` review | "Which ETF allocation rule beats SPY/BIL after costs on free daily data, and what is the honest expectation?" |
| `longterm` | Long-term investing | Multi-year holdings: value, quality, retirement sleeves, tax-aware | Closed-end-fund discounts, merger/SPAC arbitrage (likely `BLOCKED-ON-DATA`), index-inclusion effects | `value/` advisor (theses + shadow ledger), `advisors/` persona books, `k401`, alpha-lab families | "What long-horizon factor or discount mechanism survives the quant law on free data?" |
| `shortterm` | Short-term trading | Days-to-weeks horizons | Stat-arb / pairs (inherits the F-04 contamination line), index-rebalance flows, post-earnings drift (PEAD is twice-blocked on a missing Finnhub token — inherited) | `swing/` (Tradier sandbox-pinned, the only order path), `momentum/` lab, `quant/` | "Which short-horizon mechanism has a named loser and clears costs on free data?" |
| `crypto` | Crypto trading | Spot and perp *shadow* positioning from public data; advisory forever unless the owner opens a venue (D2) | Cross-exchange spot spreads (public order books), funding-rate / basis carry (public OKX funding) — both zero-prior lanes | atlas `dashboard/atlas_dash/ingest/crypto.py` and `perps.py` as *reference patterns*; `knowledge/crypto/` | "Measure, from public data, whether any cross-venue or basis spread clears fees + withdrawal friction — shadow only" |
| `_TEMPLATE` | (reserved) | Owner decision D1 | — | — | `.venv/bin/python -m mmcore new-bucket <slug> --name "<Name>"` stamps a bucket from it |

Every bucket also inherits the **company families** that are not domain-
specific: `cash-yield` (the grade-A baseline every grade is measured against)
and `cost-model` (costs always modelled, never cost-free).

### 4.2 The hierarchy, mapped onto the server's vocabulary

| Owner's role | What it does here | Implementation | Server archetype |
|---|---|---|---|
| **CEO** (manager of managers) | Weekly: fetches origin, reads every bucket's committed state, grades and ledgers plus liveness (psql SELECT over `mm-*` jobs, `schedule_adherence.json`) and spend (audit `usage`); decides which buckets run this week and what each governor should focus on; dispatches governors; its final text is the directive the reporter records. Owns the looping-workflow constitution (`company/LOOP.md`) and the information-passing paradigm (§8). Greenlights by dispatching. | `mm-ceo` (one skill) | Division manager under `system-manager`: `role: manager`, `privilege_class: read-only`, acceptEdits, `isolation: workspace` (read-only hooks bind; Bash only for `git fetch`/`git show`/psql SELECT/`cat`), `needs-dispatch-mcp`, subagents `[gap-auditor]` |
| **Bucket CEO** (the spec's per-bucket CEO) | The bucket's frozen evaluator: grades the last cycle from artifacts (recomputing DSR from `metrics.json`), rewrites the bucket backlog, opens the next cycle, dispatches the next stage within caps, files `[system]` improvements and DECISION-REQUESTs; applies an owner-approved `[system]` item on request (`mode=apply-system`). Never researches or builds. | `mm-govern` (shared, `bucket=` parameter) | Governor: `role: governor`, `privilege_class: guarded-writer`, workspace |
| **Research EO** | Maintains `knowledge/LIBRARY.md` ("best way to make money in this domain") and writes one Research Brief per cycle; arbitrage family first; prior-art across *all* atlas ledgers and all buckets; cites sources with dates; grades claims. | `mm-research` | Researcher archetype (`atlas knowledge/roles/researcher.md`) |
| **Bridging EO** | Turns a brief into ONE sealed Actionability Card under `company/PROTOCOL.md`: deterministic rules, free-data probe (live, fenced), cost model, success/kill criteria with observables, placebo plan, trials registration; verdict ACTIONABLE / NOT-ACTIONABLE / BLOCKED-ON-DATA. | `mm-bridge` | New archetype "actionability judge" (`company/officers/bridge.md`), built from `atlas-gap-scout`'s builder-acceptance row + alpha-lab card discipline |
| **Architect EO** | Turns an ACTIONABLE card into an Architecture Plan: module tree under `buckets/<b>/projects/<name>/`, interfaces, tests, acceptance rows (including the validation report row), reuse table (mmcore / adapters / quantlab), no new deps. | `mm-architect` | Sector-architect charter (`atlas .claude/agents/sector-architect.md`): deterministic acceptance criteria, plan only on specced ground |
| **Engineering EO** | Implements the plan: code + tests + the quant-law validation report + acceptance evidence, ONE commit, in-session `code-review` LGTM, push, then dispatches execute only on a validation PASS. 2-attempt cap per cycle, blocker format. | `mm-engineer` | Engineer charter (`atlas .claude/agents/engineer.md`), `atlas-build` shape |
| **Execution EO** | Runs the implementation's deterministic entrypoint, verifies outputs, marks the shadow book vs SPY/BIL, writes an Execution Report, routes issues to the governor/CEO. Touches nothing. | `mm-execute` | Supervisor archetype (`atlas knowledge/roles/supervisor.md`), `atlas-trader-paper` shape |
| **Resumer** (the loop's daily heartbeat) | Daily, cheap: fetches origin, finds stale or cap-stalled cycles, re-dispatches the exact stage (double-dispatch guarded), writes nothing. | `mm-resume` | Read-only + dispatch, workspace (Bash for fetch/psql), sonnet |
| **Reporting suite** (the CEO's suggested extra) | Scheduled 2.5 h after the CEO: records CEO decisions as company ledger entries, writes the weekly owner memo (including "CEO FAILED" when it did), answers on-demand Telegram pulls, computes the monthly scoreboard from audit usage. Never dispatches. | `mm-report` | Writer (guarded-writer, workspace); Telegram-triggerable with `--project=moneymachine` |

Why nine shared skills and not 24–30: the quota envelope (§12) cannot fund a
scheduled opus job per role per bucket, lint cannot express a writing CEO, and
the spec's own "share tools, don't duplicate" wish applies to the agents
themselves. Domain specialisation is data (the bucket directory), not code.

### 4.3 Org placement

A new division **`moneymachine`** (`.context/org/divisions/moneymachine/CHARTER.md`)
with manager `mm-ceo`, one row in ORG.md's Division index (not its protected
sections), `mm-ceo` added to `system-manager`'s roster query so the monthly
org CEO reads MoneyMachine's weekly reports, and the Delivery charter's
"atlas is the only one today" updated to "atlas and moneymachine today".
Rationale: the Delivery charter says a project stays in Delivery "unless the
project is big enough to have its own division"; the atlas charter is already
40 rows and its manager's roster list has drifted; and the money ceilings are
the same either way (INV-22 is estate-wide). Chartering a division normally
goes through the org CEO's proposal lane; here it is done under the owner's
direct delegation (§16 D0).

## 5) Repo layout (`~/Documents/repos/moneymachine`, GitHub `alfredbot-ai-butler/moneymachine`, private)

### 5.1 Tree

```
moneymachine/
├── CLAUDE.md                     # directive: Rule 1 (§10.1), topology, interpreter contract, verification-first, contracts index
├── README.md                     # human overview + how to read a week of output
├── manifest.yml                  # §5.2 — runner-scoping only; dev-repo, pull-only runtime clone, deployable: false, NOT HOSTED
├── .gitignore                    # .env, .venv, __pycache__, .pytest_cache, *.tmp
├── .context/
│   ├── CONTEXT.md                # standard 5 sections (Mission, Platforms, Web Serving, Architecture, Status)
│   └── CHANGELOG.md              # newest-first, every loop run appends
├── skills/GOTCHAS.md             # project gotchas (PROJECT_PROTOCOL §3.4 location)
├── company/
│   ├── COMPANY.md                # mission, objective function, the honest expectation, the hierarchy, contracts index
│   ├── LOOP.md                   # the looping-workflow constitution (§6) — binding; skills defer to it
│   ├── PROTOCOL.md               # research protocol (child of atlas momentum/alpha-lab/quant PROTOCOL) — binding
│   ├── MM_AUTHORITY.md           # graduation runbook, owner-only (§10.3)
│   ├── LEDGER.md                 # company ledger, C-#### entries (CEO decisions, recorded by mm-report)
│   ├── LESSONS.md                # cross-bucket lessons, one line per terminal decision
│   ├── officers/                 # role handbooks the skills read first
│   │   ├── README.md             # how a handbook is layered: company handbook + bucket specialisation; the rotation default
│   │   ├── ceo.md  govern.md  research.md  bridge.md  architect.md  engineer.md  execute.md  resume.md  report.md
│   └── config/
│       ├── budget.yaml           # OWNER-OWNED caps (§12.2); agents propose via DECISION-REQUEST
│       └── settings.yaml         # OWNER-OWNED `enabled:` flag, fail-closed (§12.3)
├── buckets/
│   ├── _TEMPLATE/                # stamped by `mmcore new-bucket`; same tree as a live bucket, placeholders
│   ├── etf/  longterm/  shortterm/  crypto/
│   │   ├── CHARTER.md            # domain mission, universe, arbitrage lane + sub-lanes, data policy (free sources), ceilings, substrate map, cycle-1 question
│   │   ├── officers/             # domain specialisations: research.md bridge.md architect.md engineer.md execute.md govern.md (≤60 lines each)
│   │   ├── knowledge/
│   │   │   ├── LIBRARY.md        # L-#### claims: text | source URL | checked date | grade A–F | status (live/stale/refuted/unmeasured)
│   │   │   └── FAMILIES.md       # hypothesis families; `arbitrage` first with sub-lanes; status open|proposed|saturated|owner-closed; `opened_by: owner` on every open row
│   │   ├── evaluation/
│   │   │   ├── LEDGER.md         # B-#### entries (§8.4)
│   │   │   ├── trials.jsonl      # every evaluated variant, rejects and grid cells included (lifetime N)
│   │   │   └── LESSONS.md        # `- [<cycle>] <family> | <kill-class> | <reusable constraint>`
│   │   ├── BACKLOG.md            # governor-written, ≤8 open items, each with done-evidence; `[system]` items numbered
│   │   ├── research/RB-####.md   # Research Briefs
│   │   ├── cards/AC-####.md      # Actionability Cards (sealed: never edited after seal)
│   │   ├── plans/AP-####.md      # Architecture Plans
│   │   ├── projects/<name>/      # implementations: code + tests + README + run.py + validation/R-####/{metrics.json,report.md,manifest.json}
│   │   ├── runs/<date>-<name>.json  + manifest.json per run (provenance)
│   │   ├── shadow/book.json      # shadow book state (positions, marks, pessimistic fills) + manifest.json
│   │   └── state/
│   │       ├── cycle.json        # the ONE active cycle (§8.2)
│   │       └── history/<cycle_id>.json
├── reports/
│   ├── weekly/YYYY-MM-DD.md      # owner memo (mm-report), ≤1 page
│   └── monthly/YYYY-MM.md        # scoreboard (jobs by kind vs structural ceiling, failures, cap-stalls, spend, verdict mix, top lessons)
├── shared/
│   ├── mmcore/                   # stdlib + pyyaml package (§9.1) — no network, no psql
│   ├── adapters/                 # keyless urllib adapters (§9.2): stooq.py (daily closes); public-path-only guard
│   ├── tests/                    # pytest incl. tripwires (§10.2)
│   └── pyproject.toml            # optional `pip install -e shared`; `.venv/bin/python -m mmcore` with PYTHONPATH=shared is the contract
├── integrations/ai-server/README.md   # the two-repo contract (skills live in ai-server; schedules in seed-schedules.sh; what this repo must keep true)
└── docs/
    ├── DEVELOPMENT.md            # multi-machine rules (from atlas), the python3.12 + per-job venv contract, how to run a stage locally
    └── OWNER.md                  # one page: read the memo, pause/resume, manual CEO trigger, stop in-flight chains, apply a [system] item, decisions outstanding
```

### 5.2 `manifest.yml` (a builder validates it with `src.registry.manifest.load` before commit)

```yaml
slug: moneymachine
name: MoneyMachine Company
mission: "A bucketed, self-running agent company that researches, validates and shadow-runs ways to make the owner money — reports only, no order path"
type: static            # manifest.py has no 'content' type; static is the accepted not-hosted shape. NO web_root on purpose.
subdomain: moneymachine # placeholder required by the schema — NOT hosted, never registered
description: >
  NOT HOSTED — runner-scoping manifest only; never run scripts/register-project.sh.
  Company layer over the estate's money-making work: four domain buckets
  (etf, longterm, shortterm, crypto), one shared officer hierarchy expressed
  as ai-server mm-* skills, append-only ledgers, owner memos. Reads Atlas
  read-only; INV-22: no order path. delivery.deployable is false and there is
  no port: reconciliation must treat this like the content projects, never as
  hosted-not-registered drift.
created_at: "2026-10-21"
git:
  repo: "https://github.com/alfredbot-ai-butler/moneymachine"
  branch: main
delivery:
  topology: dev-repo
  dev_repo: ~/Documents/repos/moneymachine
  runtime_clone: pull-only
  branch: main
  deployable: false       # nothing to deploy; the prod clone exists only so the runner can read this manifest
```

No `env_files`: the repo holds no secrets and needs none (D2).

## 6) The loop (`company/LOOP.md` — binding; this section is its summary)

### 6.1 Stages and movers

| # | Stage | Skill | Reads | Writes (single writer) | Terminal outcomes |
|---|---|---|---|---|---|
| 0 | ALLOCATE | `mm-ceo` (Sat 17:00) | everything, read-only (after `git fetch`) | nothing (dispatches ≤2 governors; its final text is the directive) | — |
| 1 | GOVERN | `mm-govern` | bucket state, ledger, trials, runs, validation reports, LESSONS, FAMILIES, last grades | `evaluation/LEDGER.md` (GRADE/AUDIT/DECISION-REQUEST/LESSON/PROTOCOL-VIOLATION/GRADUATION-OFFER), `BACKLOG.md`, `state/cycle.json` (open/close), `knowledge/FAMILIES.md` (append `proposed`; `open → saturated` with ≥2 terminal ids only); in `mode=apply-system`: `company/officers/*`, `buckets/<b>/officers/*`, `BACKLOG.md` | — |
| 2 | RESEARCH | `mm-research` | LIBRARY, FAMILIES, LESSONS (all buckets), Atlas libraries and ledgers, web | `knowledge/LIBRARY.md` (append/grade), `research/RB-####.md`, ledger BRIEF entry | — |
| 3 | BRIDGE | `mm-bridge` | the brief, PROTOCOL, data sources (live probe, fenced) | `cards/AC-####.md` (sealed), `trials.jsonl` (registration), ledger CARD entry | `not_actionable`, `blocked_on_data` |
| 4 | ARCHITECT | `mm-architect` | the card, mmcore/adapters/quantlab APIs, existing projects | `plans/AP-####.md`, ledger PLAN entry | `plan_rejected` (needs a new dep / paid data / order surface) |
| 5 | ENGINEER | `mm-engineer` | the plan | `projects/<name>/**` incl. `validation/R-####/`, ledger IMPL entry, acceptance evidence | `blocked` (2 attempts); `rejected` (validation FAIL — the quant law said no; LESSON) |
| 6 | EXECUTE | `mm-execute` | the project, shadow book, adapters | `runs/*.json` + manifest, `shadow/book.json`, ledger EXEC entry | `halted` (issue report) |
| 7 | RESUME | `mm-resume` (daily 10:30) | `git show origin/main:` state files, psql | nothing (re-dispatches) | — |
| 8 | REPORT | `mm-report` (Sat 19:30) | all ledgers, state, CEO summary file, audit summaries, jobs table | `company/LEDGER.md` (C-####), `reports/weekly/*.md`, `reports/monthly/*.md` | — |

Rhythm (phase 0): **Sat 17:00 UTC** `mm-ceo-weekly` dispatches ≤2 governors
(rotation default in `company/officers/README.md`: week 1 `etf` + `crypto`,
week 2 `longterm` + `shortterm`, thereafter an open non-terminal cycle outranks
a new one; the CEO may deviate with a stated reason) → each governor
dispatches one stage job → stages chain themselves, one per job, until the
day cap or the bucket's weekly cap is hit ("cap-stalled") or the cycle reaches
a terminal or graded state → **Sat 19:30** `mm-report-weekly` writes the memo
from whatever has landed → **daily 10:30** `mm-resume-daily` re-dispatches
stale or cap-stalled stages within caps → next Saturday the CEO grades the
week. With the §12.2 caps a cycle runs two stages per bucket per Saturday
(research + bridge; architect + engineer; execute; grade), so a full cycle is
about four weeks and the four buckets complete a first cycle in about eight.

### 6.2 Cycle state machine (`state/cycle.json`, one active cycle per bucket)

```
open ─govern─► research ─research─► bridge ─bridge─► architect ─architect─► engineer ─engineer(PASS)─► execute ─execute─► graded ─govern─► closed
                                     │                │                    │                            │
                                     └─► not_actionable / blocked_on_data  └─► plan_rejected            └─► blocked (2 attempts) / rejected (validation FAIL)   └─► halted
```

| Edge | Mover | Required evidence (in the artifact + ledger entry) |
|---|---|---|
| `open → research` | governor | cycle question written, family named (arbitrage sub-lane first unless every sub-lane is `saturated`/`owner-closed` with ledger ids) |
| `research → bridge` | research | `RB-####` committed with ≥3 sourced claims graded, candidate mechanism naming who loses, prior-art ids across all atlas ledgers + all buckets |
| `bridge → architect` | bridge | `AC-####` sealed AND pushed with: live free-data probe output + timestamps (fence respected), cost model, success/kill `Criteria observables:`, placebo plan (M ≥ 200), `Prior-art check:`, `Survivorship probe:` where applicable, TRAIN/VALIDATION/FORWARD windows, ≤2 parameters, `trials.jsonl` registration |
| `bridge → not_actionable|blocked_on_data` | bridge | verdict + reason; LESSON line; killed-elsewhere ⇒ `not_actionable` same day; LLM-signal mechanism ⇒ `blocked_on_data` (INADMISSIBLE) |
| `architect → engineer` | architect | `AP-####` with acceptance rows incl. the validation-report row and reuse table; no new deps |
| `engineer → execute` | engineer | pushed commit with tests green, in-session `code-review` LGTM recorded, acceptance evidence, `validation/R-####/metrics.json` with verdict PASS under the quant law |
| `engineer → rejected` | engineer | validation verdict REJECT recorded (IMPL entry + LESSON); no execute |
| `execute → graded` | execute | `runs/<date>-<name>.json` + provenance manifest + shadow marks vs SPY/BIL, EXEC entry |
| `graded → closed` / `* → closed` | governor only | GRADE entry citing artifacts and the DSR recompute; LESSON line; BACKLOG rewritten |

Nobody flips a stage they did not execute; the governor is the only mover
into `closed`. A `cycle.json` write always refreshes `last_advanced_at` and
`last_job_id`. Staleness is judged by the daily resumer: a non-terminal
cycle whose `last_advanced_at` is > 6 h old with no queued/running job for
its id (psql on `kind` + `description LIKE '%cycle=<id>%'`) is re-dispatched
at the same stage.

### 6.3 Correlation keys (the audit spine)

- **Cycle id** `<bucket>-C####` — in every description, every artifact header,
  every commit footer `MM-Cycle: <id>`.
- **Artifact ids** `RB-/AC-/AP-/IM-/XR-####` per bucket; validation reports
  `R-####` per project — in ledger entries and the next stage's description.
- **Job id** — footer `Job: <id8>` (the job id is injected into the system
  prompt) and `cycle.json.last_job_id`.
- **Ledger ids** `B-####` (bucket), `C-####` (company) — strictly increasing,
  append-only; corrections are new entries citing the old id.

### 6.4 Chain mechanics (every stage, verbatim in each skill)

0. **Sync first.** Writers: `git pull --ff-only origin main` (the workspace
   clone starts from the dev clone's possibly-stale HEAD). Read-only sessions
   (CEO, resumer): `git fetch origin` and read state via `git show
   origin/main:<path>`. `mmcore preflight` fails when `HEAD..origin/main` is
   non-empty or the branch is not `main`.
1. **Interpreter + timer.** `python3.12 -m venv .venv && .venv/bin/pip install
   -q pytest pyyaml`; `date +%s > /tmp/mm-stage-start-<job-id8>`. Seal and
   close out at 45 min (engineer: 70 min); reserve ~15 turns for close-out.
   max_turns exhaustion is recorded as *completed* and deletes the workspace
   — push before the reserve, not after. Read-only sessions (CEO, resumer)
   cannot create a venv or write `/tmp` under the read-only guard profile:
   they run `PYTHONPATH=shared python3.12 -m mmcore …` on the runner's
   `python3.12` (the ai-server venv, which carries pyyaml) and keep the clock
   in the summary, not in a file.
2. **Gates.** `PYTHONPATH=shared .venv/bin/python -m pytest shared/tests -q`
   green (plus the project's own tests for ENGINEER/EXECUTE); secrets grep on
   the diff; ONE commit with footers `MM-Cycle:` + `Job:`; `cycle.json`
   updated.
3. **Push.** `git pull --rebase origin main`, push; on reject rebase and
   retry ONCE; still failing → report divergence, do **not** dispatch.
4. **Budget.** Two psql counts (exact stage kinds only — never governors,
   resumer, CEO or reporter):
   - jobs-today: `SELECT count(*) FROM jobs WHERE kind IN
     ('mm-research','mm-bridge','mm-architect','mm-engineer','mm-execute')
     AND created_at > now() - interval '24 hours'`
   - jobs-week (this bucket): same kind list `AND description LIKE
     'mm-%: bucket=<b> %' AND created_at > now() - interval '7 days'`
   then `PYTHONPATH=shared .venv/bin/python -m mmcore budget --bucket <b>
   --jobs-today <N> --jobs-week <M> --active-cycles <K>`. `DENY` → skip the
   dispatch, say "cap-stalled" in the summary and set
   `cycle.json.blocked_reason = "cap"`; the daily resumer picks it up.
5. **Dispatch AFTER the push** — only kinds matching `mm-*`, always with
   `payload.project_slug = "moneymachine"` and the TARGET stage's timeout:

   | Target kind | `session_timeout_seconds` |
   |---|---|
   | `mm-govern` | 3600 |
   | `mm-research` | 3600 |
   | `mm-bridge` | 3600 |
   | `mm-architect` | 3600 |
   | `mm-engineer` | 5400 |
   | `mm-execute` | 1800 |

   Description per §8.1. Any other kind — `server-patch`, `new-skill`,
   `atlas-*`, anything — is a DECISION-REQUEST ledger entry, never a dispatch
   (§10.4).
6. **Close-out.** Final text = the job summary (§8.6); when the job is
   task-linked (Telegram-originated) it ends with `TASK_COMPLETE: <one line>`
   so the task resolves through one evaluator run instead of an auto-continue.

### 6.5 Arbitrage-first rule

Each `FAMILIES.md` lists `arbitrage` first, with named sub-lanes. The
governor's cycle question must address an arbitrage sub-lane first unless
every sub-lane's status is `saturated` or `owner-closed` *with a dated reason
and the ledger ids that saturated it* (≥2 terminal verdicts from this bucket
or atlas per sub-lane). The family row itself is never closed by an agent.
"Primary opportunity" is therefore enforced as ordering and justification,
never as a promise of edge.

### 6.6 Recovery matrix

| Failure | Detection | Recovery |
|---|---|---|
| Stage job dies before push | `cycle.json` stale > 6 h (as of the daily resumer), no queued/running job for the cycle | resumer re-dispatches the same stage (double-dispatch guarded) |
| Stage job pushed but did not dispatch | state advanced, no child job | resumer dispatches the next stage |
| Push rejected twice | job summary says divergence | governor files `[system]` item; owner nod; no force-push ever |
| Cap-stalled | summary + `cycle.json.blocked_reason = cap` | resumer retries daily within caps |
| CEO row dark (no job) | `scripts/schedule-monitor.sh` DARK finding DMs the owner | owner `/schedule resume mm-ceo-weekly` or investigates |
| CEO job FAILED (not dark) | `mm-report` (Sat 19:30) finds no completed `mm-ceo` job since the slot → memo headline "CEO FAILED: <reason from the summary file>"; the owner reads it on demand or in the repo | owner nudges the row (`UPDATE schedules SET next_run_at = NOW() WHERE name='mm-ceo-weekly'`) after reading the failure; FAILURE_STREAK DMs after 3 weeks regardless |
| Reporter failed | no `reports/weekly/<Saturday>.md` by Sunday | on-demand pull `/task --project=moneymachine --kind=mm-report latest` rebuilds it |
| Repo contract broken (tripwire red) | pytest red at any stage | stage stops, no push, `[system]` item; nobody pushes around a red tripwire |
| Prod manifest missing | first job's `project_cwd_resolved` audit event shows the server root | provisioning order in §14.3 prevents it; otherwise the owner re-creates the prod clone |
| `enabled: false` not yet seen | a session started before the flag landed | every session syncs at step 0, so the flag takes effect at the next job start; `/schedule pause` is immediate for new rows but does not cancel queued children |

### 6.7 Ceilings (LOOP.md §6, restated for this company)

Human-only, always: any order path, broker/exchange credentials, paid data,
new external dependency, editing `company/config/*.yaml`, `CLAUDE.md` Rule 1,
`MM_AUTHORITY.md`, any tripwire test, `LOOP.md`/`PROTOCOL.md`, any `mm-*`
SKILL.md beyond a Gotchas append, any schedule row, any new bucket beyond the
template stamp (D1), any hosting change, flipping a family to `open` or
`owner-closed`. Front door (LOOP.md §7, adopted verbatim): `[system]` backlog
item or DECISION-REQUEST ledger entry → owner nod → applied either by the
owner's own reviewed commit or, for in-repo handbooks/officer specialisations/
BACKLOG only, by `mm-govern mode=apply-system item=<n>` triggered by the
owner from Telegram (§8.1).

## 7) Skills (all under ai-server `skills/mm-*/SKILL.md`; division `moneymachine`)

| Skill | Model / effort (→ `escalation.on_failure`) | permission / isolation / privilege / role | required_tools | tags | subagents / post_review | Dispatches | max_turns |
|---|---|---|---|---|---|---|---|
| `mm-ceo` | claude-opus-5 / high (→ opus-5 / xhigh) | acceptEdits / workspace / **read-only** / manager | `[Read, Glob, Grep, Bash]` | `[moneymachine, management, scheduled-capable, needs-dispatch-mcp]` | `[gap-auditor]` / none | `mm-govern` ×≤2 | 40 |
| `mm-govern` | claude-opus-5 / high (→ opus-5 / xhigh) | bypassPermissions / workspace / guarded-writer / governor | `[Read, Write, Edit, Bash, Glob, Grep]` | `[moneymachine, evaluation, needs-dispatch-mcp]` | none / none | one stage | 60 |
| `mm-research` | claude-opus-5 / high (→ opus-5 / xhigh) | bypassPermissions / workspace / guarded-writer / worker | `[Read, Write, Edit, Bash, Glob, Grep, WebSearch, WebFetch]` | `[moneymachine, research, needs-dispatch-mcp]` | none / none | `mm-bridge` | 80 |
| `mm-bridge` | claude-opus-5 / high (→ opus-5 / xhigh) | same as research | `[Read, Write, Edit, Bash, Glob, Grep, WebSearch, WebFetch]` | `[moneymachine, research, needs-dispatch-mcp]` | none / none | `mm-architect` or terminates | 80 |
| `mm-architect` | claude-opus-5 / high (→ opus-5 / xhigh) | same, no web tools | `[Read, Write, Edit, Bash, Glob, Grep]` | `[moneymachine, research, needs-dispatch-mcp]` | none / none | `mm-engineer` | 50 |
| `mm-engineer` | claude-opus-4-8 / high (→ opus-5 / xhigh) | bypassPermissions / workspace / guarded-writer / worker | `[Read, Write, Edit, Bash, Glob, Grep]` | `[moneymachine, engineering, needs-dispatch-mcp]` | `[code-review]` / `post_review:` `trigger: always` | `mm-execute` (PASS only) | 100 |
| `mm-execute` | claude-sonnet-4-6 / medium (→ opus-4-8 / high) | bypassPermissions / workspace / guarded-writer / worker | `[Read, Write, Bash, Glob, Grep]` | `[moneymachine, execution]` | none / none | nothing | 40 |
| `mm-resume` | claude-sonnet-4-6 / low (→ sonnet-4-6 / medium) | acceptEdits / workspace / **read-only** / worker | `[Read, Glob, Grep, Bash]` | `[moneymachine, evaluation, scheduled-capable, needs-dispatch-mcp]` | none / none | the stalled stage | 25 |
| `mm-report` | claude-opus-5 / medium (→ opus-5 / high) | bypassPermissions / workspace / guarded-writer / worker | `[Read, Write, Edit, Bash, Glob, Grep]` | `[moneymachine, reporting, scheduled-capable]` | none / none | nothing | 40 |

Common frontmatter: `division: moneymachine`; `context_files` =
`[".context/org/ORG.md"]` for `mm-ceo`, omitted for the others (the runner's
directive already injects the absolute PROJECT_PROTOCOL path for
project-scoped jobs); `## Gotchas (living section)` in every body; no skill is
named `*-redeploy`. Model ids are in the gateway alias table today and in
`models.yml` once the cross-vendor branch lands.

**Every skill body carries, verbatim (pinned by `tests/test_mm_skills.py`):**

> Dispatch only kinds matching `mm-*` with `payload.project_slug` =
> `moneymachine`. Any other kind — `server-patch`, `new-skill`, `atlas-*`,
> anything — is a DECISION-REQUEST ledger entry, never a dispatch.

Per-skill duties are specified in `company/officers/<role>.md` (the handbook
the skill reads first) and summarised in the SKILL.md body; the SKILL.md is
the system prompt, the handbook is the contract. Each stage skill body
carries: Inputs (description grammar §8.1), Procedure (sync → interpreter →
preflight → read handbook + bucket specialisation → do the one stage → chain
mechanics §6.4), Write surface, Forbidden, Close-out, Gotchas.

**Preflight, every skill with Bash, after step 0/1:** `PYTHONPATH=shared
.venv/bin/python -m mmcore preflight --bucket <b>` — exits 0 only when
`settings.enabled` is true, python ≥ 3.12 with `yaml` importable, the clone is
on `main` and not behind `origin/main`, the bucket exists, and the tripwire
tests pass. Read-only sessions run `mmcore preflight --read-only` on the
runner's `python3.12`: it reads `origin/main:company/config/settings.yaml`
via `git show`, fetches, and skips the behind-origin check (they never pull;
every state read goes through `git show origin/main:<path>`).

## 8) Information-passing paradigm (set by the CEO; binding)

### 8.1 Description grammar — inputs ride in `job.description`, never only in payload

```
mm-<stage>: bucket=<slug> cycle=<bucket>-C#### [artifact=<ID>] [mode=<word>] — <one line of human context>
mm-govern:  bucket=<slug> mode=weekly|resume — <CEO focus line>
mm-govern:  bucket=<slug> mode=apply-system item=<n> — <owner note>      # owner-triggered from Telegram
mm-report:  mode=weekly — <scheduled>                                     # the Saturday row
mm-report:  latest                                                        # Telegram on-demand pull (flags stripped; bare text)
```

The `mm-<stage>:` prefix is optional (Telegram strips flags and leaves bare
text). Skills parse `key=value` tokens before the em dash; unknown keys are
ignored; a missing required key is a hard stop with a clear summary (never a
guess). Payload carries only `project_slug` and `session_timeout_seconds`.

### 8.2 `state/cycle.json`

```json
{"bucket":"etf","cycle_id":"etf-C0001","question":"…","family":"arbitrage","sublane":"premium-discount",
 "stage":"bridge","artifacts":{"brief":"RB-0001","card":null,"plan":null,"impl":null,"validation":null,"exec":null},
 "stage_attempts":{"engineer":0},"cycles_used":1,"blocked_reason":null,
 "last_job_id":"a1b2c3d4","last_advanced_at":"2026-10-25T17:42:00Z","opened_at":"…","closed_at":null,"outcome":null}
```
`mmcore cycle` validates every transition against §6.2 and refuses illegal
edges; `history/` holds closed cycles; `cycles_used` is checked against
`max_cycles_per_card` ("budget death" ⇒ automatic `not_actionable`).

### 8.3 Artifact headers (machine-parseable, first lines of every RB/AC/AP/IM/XR file)

```
id: AC-0003
cycle: etf-C0001
bucket: etf
family: arbitrage
sublane: premium-discount
stage: bridge
job: a1b2c3d4
sealed: 2026-10-25T18:10:00Z        # cards only; sealed cards are never edited
verdict: ACTIONABLE                 # bridge/architect/engineer/execute verdicts
```

### 8.4 Ledger entry format (`evaluation/LEDGER.md`, `company/LEDGER.md`)

```
## [B-0007] GRADE · etf-C0001 · 2026-11-01 · job a1b2c3d4
Artifacts: RB-0001 AC-0003 AP-0002 IM-0001 R-0001 XR-0001
Grade: C — process-compliant; validation PASS (DSR 0.961 vs N=7, recomputed 0.961; worst fold 0.12; critic clean); shadow +0.4% vs SPY +1.1% / BIL +0.08% over 6 sessions (pessimistic fills)
Lesson: [etf-C0001] arbitrage/premium-discount | hollow-gross | premium/discount on free daily closes is unmeasurable intraday
System: [system] #3 bridge probe should record quote timestamps (proposed)
```
Bucket-ledger kinds: BRIEF, CARD, PLAN, IMPL, EXEC, GRADE, AUDIT,
DECISION-REQUEST, GRADUATION-OFFER, LESSON, PROTOCOL-VIOLATION. Company-ledger
kinds: DECISION, AUDIT, DECISION-REQUEST, LESSON. `mmcore ledger append` allocates
the id and refuses non-monotonic or edited history; `mmcore ledger audit` is
run by the governor.

### 8.5 Handoff artifacts (what each stage must leave for the next)

| From → To | Artifact | Must contain |
|---|---|---|
| CEO → governor | job description | focus line; whether to open a new cycle; budget remaining for the bucket this week |
| governor → research | `cycle.json` + description | the cycle question, family + sub-lane, prior-art ids (LIBRARY L-ids, LESSONS lines from every bucket and atlas) |
| research → bridge | `RB-####` | ≥3 graded sourced claims; ranked mechanisms; who loses; free-data availability per mechanism; `Prior-art check:` across all atlas ledgers/trials and all buckets; recommended mechanism (deterministic rules only — LLM-signal ideas are INADMISSIBLE and must be flagged) |
| bridge → architect | `AC-####` (sealed, pushed before any backtest dispatch) | deterministic rules (≤2 parameters per confirmatory cycle; every grid cell is a trial); universe; data sources with LIVE probe output and timestamps (the probe may not compute any signal × forward-return statistic — the pre-seal fence); cost model (≥3 bps/side + spread); `Success criterion:` and `Kill criterion:` with `Criteria observables:`; placebo plan (random-entry, M ≥ 200, candidate must beat the 95th percentile); `Prior-art check:`; `Survivorship probe:` for any universe-selection idea; TRAIN / VALIDATION / FORWARD windows named (validation touches logged, ≤3/yr, a failed validation is dead); regime tags; trials registration; shadow sizing; `max_cycles_per_card` budget noted |
| architect → engineer | `AP-####` | file tree under `projects/<name>/`; interfaces; tests; acceptance rows (deterministic, artifact-computable) including "validation report `validation/R-####/metrics.json` produced by quantlab with DSR vs `distinct_n`, worst-fold Sharpe, 8-check critic"; reuse table (mmcore / `shared/adapters` / quantlab pure modules); "no new deps" attestation |
| engineer → execute | `IM-####` + code + `validation/R-####/` | green tests; `code-review` LGTM line; acceptance evidence per row; validation verdict PASS (DSR > quant `dsr_threshold` — owner-owned, 0.95 today — AND worst-fold Sharpe > 0 AND no critic FAIL AND placebo 95th percentile beaten); `run.py --date <d>` entrypoint contract (writes `runs/<date>-<name>.json` + `manifest.json` with source_url, fetch timestamp, sha256, row counts, adjustment note; exit 0 ok / 2 halt / 1 error); frozen rules hash recorded before session 1 |
| execute → governor | `XR-####` + `runs/*.json` + `shadow/book.json` | run outcome; shadow marks vs SPY/BIL (pessimistic fills); DSR / worst-fold / critic carried forward from `metrics.json`; HALT reasons; anomalies; regime tag |
| governor → CEO | GRADE entry + BACKLOG | grade with artifact citations and the independent DSR recompute (mismatch > 1e-6 ⇒ PROTOCOL-VIOLATION); `[system]` items; DECISION-REQUESTs; next cycle question |
| CEO → reporter | the CEO job's summary file (`volumes/audit_log/<id>*.summary.md`, found via psql) | decisions (one per line, `DECISION:` prefix) → `C-####` entries + memo |

### 8.6 Job summary (final text) contract

Every skill's final text is structured: first line `<kind> <bucket|company>
<cycle|week> <outcome>`; then ≤8 sentences; then, for the CEO, one
`DECISION:` line per decision and one `ASK-OWNER:` line per open ask; when
task-linked, the last line is `TASK_COMPLETE: <outcome>`.

## 9) Shared tooling

### 9.1 `shared/mmcore` (stdlib + pyyaml only; tests in `shared/tests`)

| Module | Public surface | Used by |
|---|---|---|
| `settings.py` | `is_enabled(root=None) -> bool` (fail-closed: missing file/key = False) | every preflight |
| `budget.py` | `load(root) -> dict`; `decide(budget, bucket, jobs_today, jobs_week, active_cycles) -> tuple[str, str]` returning `("ALLOW"|"DENY", reason)`; counts are stage kinds only (documented in the yaml header) | chain mechanics |
| `cycle.py` | `STAGES`, `TERMINAL`, `TRANSITIONS`, `load(root, bucket)`, `open(root, bucket, question, family, sublane, job_id)`, `advance(root, bucket, to_stage, job_id, artifact=None)`, `close(root, bucket, outcome, job_id)`, `validate(root, bucket)`; `is_stale(cycle, now, hours=6)` | governor, every stage, resumer |
| `ledger.py` | `next_id(path, prefix)`, `append(path, kind, cycle, job, body, date)`, `parse(path) -> list[Entry]`, `audit(path) -> list[str]` | all writers |
| `trials.py` | `append(root, bucket, family, sublane, params_hash, verdict, note, cycle, ts=None)`, `distinct_n(root, bucket)` (distinct `(family, params_hash)` per owner decision D-0001-RESOLVED) | bridge, engineer, governor |
| `shadow.py` | `Book.load/save`, `mark(book, closes, spy_closes, bil_closes, fill="pessimistic", cost_bps=3.0)`, `excess_vs(book) -> dict` — long/flat/short units, no leverage, costs applied | execute, governor |
| `artifacts.py` | `parse_header(path) -> dict`, `new_artifact(root, bucket, prefix, header, body) -> Path`, `next_artifact_id(root, bucket, prefix)` | all stages |
| `families.py` | `parse(path)`, `assert_owner_opened(path)` (every `open` row carries `opened_by: owner`), `saturate(path, family, sublane, ids, reason)` (requires ≥2 ids), `propose(path, family, sublane, note)` | governor, tests |
| `data.py` | `load_closes(csv_path) -> dict[date, float]` | execute, engineer, shadow |
| `report.py` | `weekly_skeleton(root, saturday) -> str` (scoreboard table per bucket from state/ledgers), `monthly_skeleton(root, month, jobs_rows, usage_rows) -> str` (jobs/week vs the structural ceiling) | reporter |
| `atlas_bridge.py` | `atlas_root()` (`$ATLAS_ROOT` or `~/Documents/repos/atlas`, read-only), `quantlab()` → adds `quant/` to `sys.path` and returns a namespace exposing ONLY `engine, metrics, dsr, walkforward, leakage, trials, health, sizing, report` (never `quantlab.data`, never `quantlab.cli`; raises `AtlasUnavailable`), `library_paths()` (atlas `knowledge/<sector>/*.md`), `ledger_paths()` (every atlas vertical's LEDGER.md + trials.jsonl) | research, bridge, architect, engineer, governor |
| `cli.py` | `.venv/bin/python -m mmcore` with subcommands `preflight [--bucket b] [--read-only]`, `budget`, `cycle show|open|advance|close|validate|block|unblock` (`block --reason cap` is the cap-stall write; `advance` takes repeatable `--artifact KEY=ID`), `ledger append|audit`, `trials append|n`, `families next|saturate|propose|assert`, `shadow trade|mark|report` (`mark --close SYM=PX` repeatable), `report weekly|monthly`, `new-bucket`, `check` | skills |

Design rules: no network calls in `mmcore`; no psql (the skill passes counts
in); every write is append or whole-file replace with validation; every CLI
command prints a one-line machine-readable verdict last.

### 9.2 Data policy and `shared/adapters`

Free, keyless, probed live before a card is sealed. Market data flows
through *code*, never an MCP: the 2026-10-05 spec §7 rules that "mounting even
a paper-order tool is an LLM-reachable order path" while "market data keeps
flowing through code"; keyless `urllib` adapters in deterministic bucket or
shared code are the latter. Phase 0 ships two keyless daily-closes adapters:
`shared/adapters/yahoo.py` (Yahoo chart v8 JSON, `fetch_daily_closes(symbol,
range_)`; the working benchmark source for SPY/BIL as probed 2026-10-21) and
`shared/adapters/stooq.py` (its keyless CSV endpoint has been behind a
JavaScript browser-verification page since 2026-10-21; kept, live probe
marked xfail). Both write the CSV `mmcore.data.load_closes` reads, with
fixture-based unit tests and live probes gated by `MM_LIVE_PROBE=1`. The host
allowlist lives in `shared/mmcore/forbidden.py` (`stooq.com`,
`query1`/`query2.finance.yahoo.com` `/v8/finance/chart/`, `api.kraken.com`
`/0/public/`, `api.exchange.coinbase.com` `/products/`, `www.okx.com`
`/api/v5/market/` + `/api/v5/public/`).
Engineering cycles add adapters under `shared/adapters/` (second use) or
`projects/<name>/adapters/` (first use) using `urllib` against public
endpoints (Kraken and Coinbase public order books and candles, OKX public
funding) — each adapter is an acceptance row in its plan and lands with a
probe test. Public and private endpoints share hosts
(`api.kraken.com/0/public` vs `/0/private/AddOrder`;
`api.exchange.coinbase.com/products/*/book` vs `/orders`;
`www.okx.com/api/v5/market` vs `/api/v5/trade/order`), so
`shared/adapters/_guard.py` hard-codes allowed public path prefixes and
rejects any URL containing `/private/`, `/trade/`, `/orders`, `/asset/`,
`/accounts/`; every adapter routes through it (tested). Third-party packages
(`ccxt`, `yfinance`) are a DECISION-REQUEST, not an import. If the planned
server-side broker-host deny (2026-10-05 §7 item 4) lands host-wide, the
crypto bucket becomes `BLOCKED-ON-DATA` by design unless it is path-aware
(§16 D8).

### 9.3 Atlas as read-only substrate

| Need | Use (read-only) | Never |
|---|---|---|
| Backtest, DSR, walk-forward, leakage critic, trials math | `quantlab` pure modules via `mmcore.atlas_bridge.quantlab()` | import `quantlab.data` / `quantlab.cli` (they reach `tradingcore.alpaca_data` and the Alpaca keys in the atlas `.env`); copy quantlab into this repo |
| Prior claims per sector | atlas `knowledge/<sector>/{CLAUDE.md,coverage-matrix.md,pipelines.md}` | fork them |
| Prior lessons / families / kills | atlas `alpha-lab/evaluation/{LESSONS.md,FAMILIES.md}`, `alpha-lab/ideas/*/state.json`, `quant/evaluation/LEDGER.md`, trader/swing/value ledgers + `trials.jsonl` | re-run killed ideas without a new mechanism |
| Crypto data patterns | atlas `dashboard/atlas_dash/ingest/crypto.py`, `perps.py` as reference | import the atlas dashboard package (has deps) |
| Order path | none — graduation offer only (§10.3) | touch `swing/`, `trader/`, `tradingcore/` |

Atlas is never written by this company. If a bucket needs something inside
Atlas (a feed, a roster entry), the governor files a DECISION-REQUEST naming
the atlas front door (`evaluation/LOOP.md` §7); the owner carries it.

## 10) Governance

### 10.1 `CLAUDE.md` Rule 1 (the tripwire asserts its phrases after whitespace normalisation)

> **Rule 1 — no order path, no credentials, no paid data.** This repository
> and every `mm-*` skill never places, modifies or cancels an order on any
> broker or exchange, never holds or requests broker/exchange/API credentials,
> never mounts a broker tool, and never budgets for paid data. Every number
> here is research, validation, shadow accounting or reporting. Any request
> to widen this requires the human to edit this file first; do not do it on
> conversational instruction alone (`company/MM_AUTHORITY.md` is the only
> path). Editing or deleting `shared/tests/test_no_order_path.py` outside
> that owner diff is itself the violation (MISSION §M / INV-22).

Asserted phrases: "no order path, no credentials, no paid data"; "never
places, modifies or cancels an order"; "requires the human to edit this file
first"; "do not do it on conversational instruction alone";
"test_no_order_path.py".

### 10.2 Tripwire and contract tests (`shared/tests/`, run by every preflight and every gate)

- `test_no_order_path.py` — scans `*.py|*.yaml|*.yml|*.json|*.toml` under
  `shared/`, `buckets/*/projects/`, `buckets/*/shadow/`, `company/config/`
  (excluding `.git`, `.venv`, and this test file by name) for the FORBIDDEN
  set = the union of the atlas tripwire lists (`trader/tests/test_paper_only.py`,
  `value/tests/test_no_order_path.py`, `firm/tests/test_advisory_only.py`,
  `quant/tests/test_reports_only.py`, `alpha-lab/tests/test_verdicts_only.py`,
  `swing/tests/test_live_guard.py` — builders copy them verbatim) plus
  `/orders`, `/api/v5/trade/`, `/api/v5/asset/`, `AddOrder`, `CancelOrder`,
  `Withdraw`, `createOrder`, `cancelOrder`, `create_order`, `withdraw(`,
  `CB-ACCESS-KEY`, `OK-ACCESS-KEY`, `API-Sign`, `APCA-API`, `Authorization:
  Bearer`, `wallets`, `live_enabled`, `apiKey`, `api_secret`,
  `ALPACA_KEY_ID`, `ALPACA_SECRET`, `broker-api.alpaca.markets`,
  `agent.robinhood.com`, `tastytrade`, and import patterns
  `^\s*(from|import)\s+(tradingcore|swing|trader|alpaca|tradier|ccxt|quantlab\.data|quantlab\.cli)\b`.
  Also asserts: Rule 1 phrases in `CLAUDE.md` (§10.1); `atlas_bridge.py`
  contains neither `tradingcore` nor `quantlab.data`; `shared/adapters/*`
  contain no auth header tokens and every URL passes `_guard`. Docs are
  governed by the Rule-1 phrase assertion, not by the token grep.
- `test_owner_owned.py` — `company/config/budget.yaml` and `settings.yaml`
  carry exactly the documented keys with the owner header; `MM_AUTHORITY.md`
  exists with its five section headings; every `open` family row in every
  `FAMILIES.md` carries `opened_by: owner`.
- `test_protocol_phrases.py` — `company/PROTOCOL.md` contains:
  "momentum/evaluation/PROTOCOL.md", "Criteria observables:", "Success
  criterion:", "Kill criterion:", "Prior-art check:", "Survivorship probe:",
  "trials.jsonl", "INADMISSIBLE", "BLOCKED-ON-DATA", "budget death", "95th
  percentile", "Deflated Sharpe", "distinct (family, params_hash)",
  "pessimistic fills", "pre-seal fence"; `company/LOOP.md` contains "one
  writer per artifact", "dispatch AFTER the push", "cap-stalled", "Dispatch
  only kinds matching `mm-*`".
- `test_cycle_state.py`, `test_ledger.py`, `test_trials.py`, `test_shadow.py`,
  `test_budget.py` (incl. "governor/report counts are ignored"),
  `test_settings_fail_closed.py`, `test_artifacts.py`, `test_families.py`,
  `test_report.py`, `test_new_bucket.py`, `test_adapters_guard.py`,
  `test_stooq.py` — `mmcore` and adapter behaviour.

### 10.3 Graduation (`company/MM_AUTHORITY.md`, owner-only; skeleton per `firm/FIRM_AUTHORITY.md`)

§0 decide honestly whether anything should ever graduate (advisory may be the
permanent right answer; for `crypto` it is, unless D2 changes) · §1 evidence
preconditions: a card whose validation report PASSed the quant law (DSR >
quant `dsr_threshold`, owner-owned, 0.95 today, vs lifetime `distinct_n`;
worst-fold walk-forward Sharpe > 0; no critic FAIL) AND beat its random-entry
placebo's 95th percentile (M ≥ 200), plus ≥ 60 shadow sessions / 100+ marked
decisions with frozen rules (hash recorded), excess vs BIL ≥ 0, zero
PROTOCOL-VIOLATIONs in the window, independent DSR recompute matching ·
§2 the offer: the governor writes a `GRADUATION-OFFER` ledger entry that
**names a target vertical per alpha-lab PROTOCOL §5 or states "none exists"**;
the CEO memo carries it; **applying stays a human action** — the owner replies
"graduate <card>" and carries it through the target's own front door:
`trader` → `trader/GO_LIVE.md`; `swing` → quant re-validation roster → owner
plan line → `atlas-build` additive strategy under the existing kernel →
sandbox evidence → `swing/LADDER.md`; `value` → advisory only, no order path
ever; `crypto` → none — memo only, a new venue or path is MISSION §M protected
· §3 automatic demotion: any PROTOCOL-VIOLATION or false claim in the window
voids the offer · §4 standing controls: `/schedule pause mm-ceo-weekly`,
`settings.yaml enabled: false`, the tripwires · **§5 Decision log** appended by
the owner only.

### 10.4 "Autonomy to greenlight anything", reconciled

The CEO greenlights, by dispatch, every research cycle, card, plan, build,
validation, shadow run, report and `[system]` proposal within the caps. It
cannot greenlight an order path, a credential, paid data, a dependency, a cap
change, a schedule row, a new bucket, a family opening, or any edit to a
ceiling file — those are the owner's by the owner's own standing rules
(MISSION §M, LOOP.md §6). Mechanically, today, a dispatch-capable skill could
enqueue any kind; the `mm-*`-only rule is therefore a sentence in every skill
body pinned by `tests/test_mm_skills.py`, and the per-spawner kind allowlist
in `src/runner/mcp_dispatch.py` is owner decision D7. The weekly memo states
which of its asks are waiting on the owner, so "greenlight" never silently
becomes "blocked forever" (the pm-edge / swing failure mode).

## 11) Reporting to the owner

- **Weekly memo** `reports/weekly/<Saturday>.md` (≤ 1 page), written by the
  scheduled `mm-report-weekly` (Sat 19:30 UTC): (1) the honest expectation
  line; (2) CEO status (completed / FAILED with reason / dark) and the
  decisions it recorded (C-ids); (3) a scoreboard table — bucket · cycle ·
  stage · last verdict · validation (DSR/N) · shadow excess vs SPY/BIL · jobs
  used / cap · liveness; (4) graduation offers (if any); (5) asks waiting on
  the owner; (6) system improvements proposed/adopted; (7) spend
  (list-equivalent from audit usage) vs the structural ceiling. Stage jobs
  dispatched that Saturday appear in the following week's memo.
- **On demand:** `/task --project=moneymachine --kind=mm-report latest` —
  Telegram-originated, so the summary is DM'd by the runner; the reporter
  reads the latest memo (rebuilding it if missing), answers in ≤ 8 sentences,
  dispatches nothing, and ends with `TASK_COMPLETE:` (the task machinery then
  runs one cheap evaluator; those extra Telegram lines are the known cost of
  the pull).
- **Manual CEO trigger (owner, from the Mini):** `psql assistant -c "UPDATE
  schedules SET next_run_at = NOW() WHERE name='mm-ceo-weekly'"` — fires
  within one 30 s tick as a scheduler job (no task, no DM; read the summary
  file or `/jobs`). Never `/task --kind=mm-ceo`: the task id would propagate
  down the whole chain and every child would spawn evaluators.
- **Monthly scoreboard** `reports/monthly/<YYYY-MM>.md`: jobs by kind against
  the structural ceiling, failure and cap-stall rates, verdict mix, spend
  recomputed from audit usage the way the 2026-10-05 spec §2.5 does, top
  three lessons — the input to D3.
- **Liveness:** `scripts/schedule-monitor.sh` already DMs DARK/STUCK on any
  row, including the three MoneyMachine rows, with no change.
- **Deferred (D4):** a server-side push of scheduled `mm-report` summaries
  and failed-job cards to the owner's chat.

## 12) Scheduling, budget, and the turn-on switch

### 12.1 Phase-0 cadence (designer's call; §16 D3)

Three rows, all with payload `{"project_slug":"moneymachine"}`:

| Row | Cron (UTC) | Kind | Why this slot |
|---|---|---|---|
| `mm-ceo-weekly` | `0 17 * * 6` | `mm-ceo` | Saturday 15:15–20:09 is the measured free band; after `atlas-advisors-panel` 15:00, clear of Sunday's governor/report-sweep block |
| `mm-report-weekly` | `30 19 * * 6` | `mm-report` | 2.5 h after the CEO: CEO (≤60 min) and two governors (≤45 min each at concurrency 2) have landed; the memo is written whether or not the CEO succeeded |
| `mm-resume-daily` | `30 10 * * *` | `mm-resume` | free: `alpha-governor` 09:30, `atlas-build` 10:00 Tue/Fri, the 11:00 loop block |

Expected weekly load at measured medians (prod audit usage, 35 days):
1 CEO ($4–9) + 2 governors ($4–10) + 4 stage jobs ($9–16 for two research-
class + two cheaper) + 1 reporter ($3) + 7 resumer runs (≤ $0.3 each) ≈
**$25–45/week (median ≈ $35)**, about 5–9 % of the trailing-4-week fleet
(≈ $490/week, 2026-09-21..10-18). The structural ceiling if every cap is
ignored is 1 + 2 + 2×6 + 1 + 7 = 23 jobs ≈ $90: caps are enforced by the
capped session's own count until D7, and the monthly scoreboard reports jobs
per week against that ceiling, not the expectation.

### 12.2 `company/config/budget.yaml` (owner-owned)

```yaml
# Owner-owned caps. Agents may PROPOSE changes via a DECISION-REQUEST ledger
# entry; they never edit this file (CLAUDE.md rule 3). Set 2026-10-21, phase 0.
# Counts are over STAGE kinds only (mm-research, mm-bridge, mm-architect,
# mm-engineer, mm-execute) in rolling windows: jobs_today = last 24 h,
# jobs_week = last 7 days for the bucket. Governors, the resumer, the CEO and
# the reporter are never counted.
max_stage_jobs_per_day: 4             # company-wide → two stages per bucket per Saturday
max_stage_jobs_per_bucket_per_week: 2
max_active_cycles_per_bucket: 1
max_governors_per_ceo_run: 2
max_engineer_attempts_per_cycle: 2
max_cycles_per_card: 6                # "budget death" ⇒ not_actionable
weekly_list_spend_target_usd: 45
```

### 12.3 Three-layer turn-on switch (quant-desk pattern)

1. `company/config/settings.yaml` `enabled: true|false` — fail-closed in
   `mmcore.settings.is_enabled()`; every session syncs then preflights it, so
   a flag pushed from any machine takes effect at the next job start.
   Immediate stop for in-flight chains is not possible; the next stage sees
   it.
2. The schedule rows — `/schedule pause mm-ceo-weekly` (and the other two)
   from Telegram; immediate for new firings, does not cancel queued children;
   the seeder never un-pauses.
3. `CLAUDE.md` Rule 1 + the tripwire suite.

Ships **armed** (`enabled: true`, rows unpaused) under the owner's "create it
and schedule it" delegation, at the phase-0 cadence above; D0 lets the owner
reverse that with one Telegram line.

## 13) How the system gets better

- **Per job:** every stage ends with a structured final text (§8.6); the
  engineer gets `post_review` where code lands; `## Gotchas` appends are the
  one permitted self-edit of a skill.
- **Per cycle:** one `LESSON` line per terminal decision in the bucket
  `LESSONS.md` (and a copy in `company/LESSONS.md` when cross-bucket);
  `FAMILIES.md` moves only as §6.5 allows, always with ledger ids.
- **Per week (governor):** the GRADE entry must answer three questions — what
  did the system do wrong this cycle, which contract or handbook line would
  have prevented it, and what is the proposed fix — filed as a numbered
  `[system]` backlog item or a DECISION-REQUEST. The governor also audits:
  ledger monotonicity, trials-before-verdict ordering, the independent DSR
  recompute, and family-status discipline.
- **Apply path:** the owner approves a `[system]` item by editing the repo
  by hand (alpha-lab precedent) **or** by sending `/task
  --project=moneymachine --kind=mm-govern bucket=<b> mode=apply-system
  item=<n>`; the governor applies it only to `company/officers/*`,
  `buckets/*/officers/*` and `BACKLOG.md`, records an AUDIT entry, and ends
  with `TASK_COMPLETE:`. SKILL.md files, `LOOP.md`, `PROTOCOL.md`,
  `config/*.yaml` and tripwires stay owner-by-hand.
- **Per week (CEO):** reconciles governors' `[system]` items across buckets,
  reads `schedule_adherence.json`, the audit summaries of every `mm-*` job
  since its last run (`psql` → `volumes/audit_log/<id>*.summary.md`), and
  spend; its own summary is read by `system-manager` monthly.
- **Per month (reporter):** the scoreboard from `jobs` + audit usage, with
  the top three lessons and the cap-stall rate — the input to the owner's D3.
- **Quarterly (deferred):** a decoy round against the bridge/execute
  judgement (answer key must live outside the repo — momentum lesson).

## 14) ai-server touchpoints and landing

### 14.1 Files changed in ai-server (branch `moneymachine/bootstrap` off `origin/main`; no `src/`)

| File | Change |
|---|---|
| `skills/mm-{ceo,govern,research,bridge,architect,engineer,execute,resume,report}/SKILL.md` | new (9) |
| `tests/test_mm_skills.py` | new: every `mm-*` body contains the `mm-*`-only dispatch sentence; `post_review` (where present) is a mapping; every dispatching skill carries `needs-dispatch-mcp`; every Bash-holding skill is `isolation: workspace`; `mm-ceo`/`mm-resume` are `privilege_class: read-only`; the `mmcore` subcommands quoted in skills ⊆ the pinned list |
| `.context/SKILLS_REGISTRY.md` | 9 rows appended at the end of the Installed table (before `## Deferred`); cells minimal — frontmatter is the source of truth |
| `.context/org/divisions/moneymachine/CHARTER.md` | new. First lines `**Manager:** \`mm-ceo\``; the roster is the ONLY table whose rows begin with a backticked name; Role/Privilege cells are bare tokens (`manager`, `governor`, `worker`; `read-only`, `guarded-writer`) |
| `.context/org/ORG.md` | one Division-index row (`| MoneyMachine | \`mm-ceo\` | [moneymachine](divisions/moneymachine/CHARTER.md) | weekly |`) — outside the protected sections |
| `.context/org/divisions/delivery/CHARTER.md` | "(atlas is the only one today)" → "(atlas and moneymachine today)" |
| `skills/system-manager/SKILL.md` | `'mm-ceo'` added to the roster `IN (...)` list |
| `skills/delivery-ops-reconciler/SKILL.md` | Gotchas append: a manifest with `delivery.deployable: false` and no `port` whose registry row says not hosted is a runner-scoping manifest, not drift — never route it to register-only |
| `skills/new-project/SKILL.md` | Gotchas append: register-only mode STOPS if `delivery.deployable` is false or the registry row says not hosted |
| `.context/PROJECTS_REGISTRY.md` | hosted-table row with Type `static (not hosted — do not register)`, Subdomain `(none — runner-scoping manifest only)`, Source `github.com/alfredbot-ai-butler/moneymachine` (canonical, private; Mini dev clone `~/Documents/repos/moneymachine`); a paragraph stating the manifest exists ONLY for `payload.project_slug` scoping; a Delivery-topology row (`dev-repo`, deployable no) |
| `scripts/seed-schedules.sh` | `# ── MoneyMachine` block with the three `upsert` rows before the final echo |
| `.context/INDEX.md` | `## Additions 2026-10-21 (MoneyMachine Company)` section at EOF |
| `docs/README.md` | rows for the spec and plan |
| `docs/superpowers/specs/2026-10-21-moneymachine-company-design.md` | this file |
| `docs/superpowers/plans/2026-10-21-moneymachine-company.md` | the implementation plan |

### 14.2 Landing lane (INV-4)

In the worktree: `git diff origin/main --name-only` protected-path check
(must be empty of the eight) → `scripts/lint_docs.py` all clean →
`SERVER_ROOT="$PWD" <venv>/bin/python -m pytest tests/test_skill_contracts.py
tests/test_doc_lint.py tests/test_mm_skills.py -q` green (plain `pytest`
validates prod's skills, not the branch's) → full pytest green → in-session
`code-review` subagent LGTM on `git diff origin/main` → `git fetch origin &&
git merge origin/main` → `git push origin moneymachine/bootstrap:main`
(straight from the worktree; the stale local `main` with its unpushed stray
commit is left alone and named in the notification) → owner notification
(what/why, `diff --stat`, LGTM, gates, pushed sha, the provisioning step
below, watch items, the pending cross-vendor rebase). The push is picked up
by the deploy autopilot; the rows first fire at their next slots.

### 14.3 Provisioning order (prevents both the red-lint window and the silent-unscoped-job trap)

1. Canonical repo: scaffold + tests green + `git init -b main` + commit +
   `gh repo create alfredbot-ai-butler/moneymachine --private --source=.
   --remote=origin --push`.
2. ai-server push (14.2) carrying the PROJECTS_REGISTRY row — a row with no
   directory is not linted, so prod stays green.
3. Wait for the autopilot deploy to go green (it also seeds the three rows
   with `next_run_at` = their next slots).
4. Prod runtime clone, **before the first slot** (`mm-resume-daily` 10:30
   UTC the next day is the earliest): `git clone
   https://github.com/alfredbot-ai-butler/moneymachine "$HOME/Library/Application
   Support/ai-server/projects/moneymachine"` — pull-only, never committed in,
   never registered. Verify: `ls "$SRV/projects/moneymachine/manifest.yml"`;
   `pipenv run python -c 'from pathlib import Path; from src.registry.manifest
   import load; print(load(Path("projects/moneymachine/manifest.yml")).delivery)'`
   from `$SRV`; `psql assistant -c "select name,next_run_at,paused from
   schedules where name like 'mm-%'"`.
5. Nothing ever pulls the prod clone (deployable: false): after any manifest
   change run `git -C "$SRV/projects/moneymachine" pull --ff-only` by hand
   (OWNER.md).
6. Watch the first `mm-resume` and `mm-ceo` jobs' `project_cwd_resolved`
   audit events: cwd must be `~/Documents/repos/moneymachine`, and
   `workspace_created`/`workspace_synced` must appear.

## 15) Testing and acceptance

- **Repo:** `PYTHONPATH=shared .venv/bin/python -m pytest shared/tests -q`
  green (tripwires, protocol phrases, owner-owned shapes, mmcore, adapters
  guard); `.venv/bin/python -m mmcore check` (preflight + ledger audit +
  cycle validation + family discipline over all buckets) exits 0; manifest
  loads via `src.registry.manifest.load`; the live Stooq probe passes once
  with `MM_LIVE_PROBE=1`.
- **Server:** `scripts/lint_docs.py` all clean; the `SERVER_ROOT="$PWD"`
  contract tests and `tests/test_mm_skills.py` green; full pytest green;
  `code-review` LGTM.
- **Dry run before push:** a builder walks the governor's procedure by hand
  against the dev clone (`mmcore cycle open etf …`, `ledger append`, `budget`
  ALLOW/DENY, `families saturate` refusal with one id, `report weekly`) and
  records it in the plan's acceptance task; the demo artifacts are removed
  afterwards (ledger and trials restored byte-for-byte, the history entry
  deleted) so the first live CEO starts from empty ledgers.
- **First live acceptance (after deploy and the prod clone):** the first
  `mm-resume-daily` run reports "nothing to resume" with
  `project_cwd_resolved` → the dev clone; the first `mm-ceo-weekly` summary
  names the two governors dispatched (`etf`, `crypto`); each governor opens a
  cycle and dispatches one `mm-research`; each research job pushes an
  `RB-0001` and dispatches `mm-bridge`; `mm-report-weekly` commits
  `reports/weekly/<date>.md` carrying the CEO's decisions; every workspace
  job's audit log shows `workspace_synced`. The first memo is the acceptance
  artifact.

## 16) Owner decisions (each answerable in one line)

| # | Decision | Designer's recommendation |
|---|---|---|
| **D0** | Armed on landing. This ships `enabled: true` and all three rows unpaused (first fires: `mm-resume-daily` the next 10:30 UTC, `mm-ceo-weekly` Sat 2026-10-24 17:00 UTC) under "create it and schedule it", whereas the quant desk shipped dark. It also charters a new org division directly rather than via the org CEO's proposal lane. Reply `pause` to reverse either | Stay armed; the kill switch is one Telegram line |
| **D1** | The fifth bucket. Prediction-market / event arbitrage wrapping `pmedge`, or none? | None until the atlas-side `STRUCTURES` defect and the expired event map are fixed (owner-owned map); then stamp `predmarket` from the template |
| **D2** | Crypto venue and credentials. Shadow-only from public data ships; a crypto graduation offer is advisory forever. Should any venue ever get a key, and which? | No keys. Revisit after 8 weeks of shadow evidence; a key is a new order path (protected) |
| **D3** | Cadence and spend. Phase 0 = two stages per bucket per Saturday, ≈ 4-week cycles, ≈ $25–45/week. Alternatives: `max_stage_jobs_per_day: 2` (6-week cycles, ≈ $28) or daily execution rows once a bucket shadow-runs (+ ≤ $0.7/day each) | Hold phase 0 for four weekly memos, then decide with the monthly scoreboard |
| **D4** | Owner push digest: a server-patch so scheduled `mm-report` summaries and failed-job cards are DM'd (today only Telegram-originated jobs are). Non-protected `src/gateway` change owned by the in-flight branch | Yes, after the cross-vendor branch lands; until then the Saturday memo + on-demand pull |
| **D6** | GitHub ownership: the canonical is under `alfredbot-ai-butler` (the only credential on the Mini). Transfer to `Piserchia` later? | Optional; if transferred, update `manifest.git.repo` and both clones' origins |
| **D7** | A per-spawner dispatch-kind allowlist in `src/runner/mcp_dispatch.py` (today any dispatch-capable skill can enqueue `server-patch`, `atlas-build`, …; `seed-schedules.sh` is not a protected path) and a generalised per-vertical valve in `events.py`. Both `src/` owner PRs | Yes — the allowlist before the first D3 raise, the valve before any cadence beyond phase 0 |
| **D8** | If the planned server-side broker-host deny (2026-10-05 §7 item 4) lands, must it be path-aware so keyless public Kraken/Coinbase/OKX endpoints stay reachable, or is the crypto bucket meant to be `BLOCKED-ON-DATA` by design? | Path-aware (deny `/private/`, `/trade/`, `/orders`, `/asset/`, `/accounts/`), mirroring `shared/adapters/_guard.py` |

(D5 — "do paper executors count as order paths?" — is already decided in
writing: MISSION §M INV-22 last bullet and the 2026-10-05 spec §7. This design
builds none.)

## 17) Deferred, and what would reopen it

| Item | Reopens when |
|---|---|
| Hosted dashboard (`/moneymachine` page, CF-Access) | four weekly memos exist and the owner wants a page instead of a file |
| Daily execution rows per bucket (sonnet, ≤ $0.7 each) | a bucket has a PASSed, shadow-running implementation and D3 funds it |
| Push digest + failed-card DM (D4) | cross-vendor branch landed |
| Dispatch-kind allowlist and generalised valve (D7) | before the first cadence raise |
| Decoy rounds for bridge/execute judgement | first GRADE with grade ≥ B |
| Fifth bucket (D1) | pm-edge `STRUCTURES` + event map fixed, or the owner names another domain |
| Atlas-side asks (feeds, roster entries, the stale kraken feed, perps `built → live`) | filed as DECISION-REQUESTs; carried by the owner through atlas LOOP.md §7 |

## 18) Provenance

Owner spec `~/Downloads/MoneyMachine Company-2.md` (2026-10-21). Understand
workflow `wf_2bf47d39-57b` (eleven readers + completeness critic) and review
workflow `wf_0a9ed0ab-bee` (builder check + four refuting lenses), both
2026-10-21; journals in the session's workflow transcript dirs. Patterns and
constraints cited by path throughout; the accepted specs this one instances:
`2026-09-01-atlas-firm-org-design.md`, `2026-09-14-alpha-lab-design.md`,
`2026-09-23-alpha-flywheel-design.md`, `2026-09-16-quant-stack-design.md`,
`2026-10-05-observability-and-trading-unblock-design.md` (§7, §14);
`.context/org/ORG.md`; atlas `evaluation/LOOP.md`.

## Amendments

- **2026-10-21 (review round 1, before any build).** Five reviewers (builder
  check, lint/org, runner mechanics, money/evidence, quota/ops) returned one
  blocker and twenty-odd confirmed problems; all folded in above. The
  load-bearing changes: budget counts stage kinds only with rolling windows
  (the original query counted governors and would have starved every chain);
  CEO and resumer run `isolation: workspace` under read-only hooks so they
  can `git fetch` and run psql SELECTs instead of reading a stale dev clone;
  `mm-report` is scheduled (Sat 19:30) rather than dispatched, so a failed
  CEO is written into a memo the same evening; a daily sonnet `mm-resume` row
  replaces the 7-day re-dispatch latency; caps raised to 4/day + 2/bucket/week
  (two stages per bucket per Saturday, ≈ 4-week cycles) with the honest
  structural ceiling stated; the manifest lost `web_root` and gained a NOT
  HOSTED first line, plus reconciler/new-project Gotchas, because the research
  precedent (no manifest) did not transfer and register-only would have
  published the memos; the Atlas bridge exposes only pure `quantlab` modules
  (the `quantlab.data` path reaches Alpaca keys transitively) and the tripwire
  gained the crypto-venue order tokens with a path-scoped file set; the stage
  flow gained a validation report at ENGINEER with `rejected` as a terminal
  (the quant law decides what shadow-runs); the protocol summary gained
  prior-art-across-everything, survivorship, INADMISSIBLE, ≤2 params,
  `max_cycles_per_card`, the pre-seal fence, provenance manifests and the
  windows; graduation names a target vertical with per-target routes and
  crypto advisory forever; FAMILIES status moves are owner-bounded; pm-edge's
  "0 in 76 days" is recorded as UNMEASURED (a liveness failure); stat-arb
  inherits the F-04 contamination line; Rule 1 adopts the family clause and
  phrase assertions; Telegram-originated runs end with `TASK_COMPLETE:` and
  the manual CEO trigger is a `next_run_at` nudge; per-target timeouts,
  per-job timer files, `python3.12` + per-job venv, `post_review` mapping
  form, `SERVER_ROOT="$PWD"` gate step, provisioning reordered (push → deploy
  → prod clone), an apply path for approved `[system]` items, `shared/adapters`
  with the public-path guard, and D5 retired as already decided.
- **2026-10-21 (build round, same day).** Nineteen builders and two
  integration fixers built both repos from the plan; the deviations folded in
  above: Stooq's keyless CSV turned out to be behind a JavaScript challenge
  from this host, so `shared/adapters/yahoo.py` (Yahoo chart v8, probed
  working) became the benchmark source and the Stooq live probe is xfail;
  the structural ceiling is 23 jobs/week (the first draft summed to 22);
  read-only sessions skip the venv/timer step and the behind-origin check;
  the CLI gained `cycle validate|block|unblock`, `families assert`, `shadow
  trade` and repeatable `--artifact`/`--close` flags; `trials.append` takes
  `sublane`; the company ledger has its own kind set; the engineer's attempt
  cap is counted from IMPL ledger entries' `Attempt: n/2` lines
  (`cycle.json.stage_attempts` is seeded but not yet moved by any CLI — a
  follow-up); the dry-run demo artifacts were removed rather than kept in
  `history/`; the kraken-feed figures in §3.2 were corrected from the atlas
  scorecard. The quant desk's "28/28 REJECT" count is as of 2026-10-20 and
  moves with its weekly sweep.
