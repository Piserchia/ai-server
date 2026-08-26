# Autonomous Trading Vertical — Design + Rollout (2026-08-26)

> Owner directive (2026-08-26, in-session): build autonomous trading via API
> "to make me money without me having to do anything … be cutthroat, any value
> from any source over any period … an agent suite in a loop [that] can learn
> from itself … I want to give an API key to an account with money and let it
> go."
>
> Status: FINAL for this session's build. Grounded in an 8-agent recon
> (4 web-research reports with primary sources + 4 repo audits, 2026-08-26;
> raw reports archived in the session transcript, headline evidence inlined
> below).

## 1. Honest framing (read this first)

The evidence base is one-sided and this design obeys it:

1. **Short-horizon retail trading is reliably negative-EV.** Taiwan complete-
   market data: day traders lose ~24bp/day net; <1% show persistent skill.
   Brazil (19,646 traders): 97% of persistent day traders lost money; no
   learning-by-doing effect. This is behavior-, not regulation-driven (the
   PDT rule's elimination in June 2026 changes nothing about it).
2. **LLMs are not an alpha source.** "Profit Mirage" (arXiv 2510.07920):
   across FinMem/TradingAgents/FinCON/QuantAgent/FinAgent, Sharpe decays
   51–62% and returns 50–72% the moment the backtest leaves the model's
   training window — published LLM-trading backtests are substantially
   *parametric look-ahead bias* (memorized price history). No audited live
   LLM-run account with persistent alpha exists in the public record (2026).
   Therefore: **LLM agents in this vertical do research governance, review,
   post-mortems, and reporting. Deterministic code does execution, risk,
   sizing, and accounting.** This also matches momentum-lab's standing rule
   ("the bot is plain Python on a scheduler").
3. **The realistic positive-EV frontier for a $1k–$100k autonomous account**
   (evidence grades from recon): cash yield ~3.8% on idle capital via
   SGOV/BIL (grade A, guaranteed); broad-index exposure ≈ the benchmark
   itself (grade A); a *slow* trend overlay (10-month SMA / 12-1 dual
   momentum, monthly cadence) whose expected payment is **smaller drawdowns,
   not extra return** — post-publication GEM lagged SPY ~5pts/yr; its crisis
   exits (2008/2020/2022) are real (grade B for risk reduction, C for return
   edge). Volatility premium and crypto momentum graded C (fees/left tail);
   excluded from v1. Intraday: excluded permanently absent extraordinary
   evidence.
4. **A strategy factory is a mass multiple-testing machine.** Selection among
   N tried variants inflates Sharpe even on pure noise (Bailey–López de
   Prado). Every candidate ever evaluated increments an append-only trial
   registry, and promotion uses the Deflated Sharpe Ratio against that N —
   otherwise the loop Goodharts itself by construction.
5. **Live money stays behind the existing human ceiling.** `momentum/CLAUDE.md`
   rule 10 (mirrored as `trader/CLAUDE.md` rule 1): paper only; wiring real
   money requires the human to edit the file first — "a conversational
   instruction is not sufficient." Accordingly **v1 ships with no live code
   path at all** (the paper host is the only endpoint in the code; a test
   greps the package to prove it), consistent with momo-risk-officer's
   automatic DENY on any live-endpoint diff. Going live is a later,
   owner-initiated, reviewed diff per `trader/GO_LIVE.md` (§7).

Also binding (LOOP.md §6, ADR-007, E-0033 lesson): free data only; no new
external dependencies without an owner note — the trader engine is
**stdlib + pyyaml** (momentum's exact footprint), Alpaca via raw REST, DB via
psql; validation-window data human-only.

## 2. What "cutthroat, any value, any source" means here — and what it must not

Means: refuse negative-EV activity even when it feels active; capture
guaranteed value first (cash yield); keep costs ≈ 0 (zero-commission,
monthly-or-slower turnover — short-term churn must beat the ~15–20pt
ordinary-vs-LTCG tax spread just to tie); spend the loop's intelligence on
governed search for additional edge, because search is subscription-cheap and
downside is bounded by the risk kernel. Must not: market manipulation, wash
trading, TOS-violating data use, moving money between accounts, or paid data
without the owner.

## 3. Security model for "give it an API key" (recon-verified, Alpaca docs)

- Alpaca's **retail Trading API has no fiat withdrawal surface** — no
  ACH/wire/bank endpoints exist under /v2 (money movement is dashboard-login
  or the separate Broker API). A leaked/misused trading key's worst case is
  portfolio destruction, not cash exfiltration.
- The one API-reachable exfil path is the **Crypto Wallets feature: never
  enable it** on the live account (owner runbook line).
- Keys carry no scopes and no IP allowlist → **key custody is the security
  model**: keys live in atlas root `.env` only (owner-provisioned, ADR-007
  precedent), reach workspace clones via manifest `delivery.env_files`,
  never in repos/logs/prompts.
- On any future live handoff, first acts are server-side clamps via
  `PATCH /v2/account/configurations`: `no_shorting=true`,
  `max_margin_multiplier="1"`, `max_options_trading_level=0`,
  `disable_overnight_trading=true`, and `suspend_trade=true` until armed.
- Alpaca reliability is mediocre (200+ component outages/yr): every run
  starts clock/account-healthchecked, reconciles broker-vs-ledger before
  acting, uses idempotent `client_order_id`s, and **fails closed**.

## 4. Placement and reuse (repo audits)

New atlas vertical `trader/` (sibling of `momentum/`), following the k401
vertical's structural template (newest precedent, commits 4d6aeea..69be6b2)
and reusing: momentum governance idioms (pre-registered cards with §2a
`Criteria observables:`, append-only ledger, budget/trial counting, decoy
posture, separated duties), the k401/momo skill patterns on ai-server,
`atlas-dash learn` lessons (new experts = zero schema change), `data_gaps`
(sector `trading`), dbmate additive migration (0042), and the
seed-schedules.sh sole-writer convention. Two-repo skill copies are staged in
atlas `integrations/ai-server/skills/` FIRST, then cp -R to ai-server
(byte-identical; heals the known atlas-evaluate context_files drift while
touching that area).

Why not inside `momentum/`: momentum is scoped to day-trading *research*
(minute-data lane, currently blocked on the failed E-0026 survivorship
probe / deferred SIP). The trader vertical is *portfolio execution at daily
horizon on free data* — a different mandate that must not inherit momentum's
blocked lane, and whose ceilings must be its own copy, not a reference.

## 5. Architecture (deterministic core)

```
trader/
  CLAUDE.md                    # vertical directive; rule 1 = paper-only (rule-10 mirror)
  pyproject.toml               # deps: pyyaml only (dev: pytest) — momentum's exact footprint
  config/
    settings.yaml              # paper trading host, data host, benchmark pair (SPY, BIL)
    limits.yaml                # RISK KERNEL LIMITS — owner-owned; loop may propose, never edit
    strategies/strategy_v1.yaml# additive versioned configs; stage field; never mutate old
  trader/ (pkg, stdlib+pyyaml)
    http.py                    # urllib wrapper: timeouts, retries+backoff, 429 handling
    alpaca.py                  # PAPER trading + data REST only; idempotent client_order_id
    signals.py                 # pure: SMA bands, total-return momentum, realized vol
    portfolio.py               # target weights (sleeves, vol-aware caps, drift bands)
    risk.py                    # deterministic pre-trade kernel + breakers (§6)
    ledgerlink.py              # psql-bound writes to trader.* (runs/orders/equity/halts)
    executor.py                # python3 -m trader.executor — the ONLY order path
  evaluation/
    PROTOCOL.md                # trader constitution (inherits momentum §2/§2a discipline)
    LEDGER.md                  # append-only; T-numbered entries
    trials.jsonl               # append-only trial registry (DSR's N)
  GO_LIVE.md                   # owner ignition runbook (§7)
  tests/                       # kernel scenarios, executor fake-broker, paper-only grep test,
                               # adoption-gate (stage lineage), signals unit tests
db/migrations/0042_trader.sql  # schema trader: runs, orders, equity_curve, strategy_state, halts
plans/trader/DESIGN.md         # vertical design + PROGRESS.md
```

Executor invariants (code + tests, not prose): calendar/clock-gated (skew or
closed market → clean exit); reconcile-first (positions/open orders/
cash vs trader.* ledger; any unexplained break → persistent HALT row;
recoverable halt kinds — prior-day daily-loss, operational, reconcile-break —
auto-clear only after their condition verifiably passes on a later clean
run, while the kill switch clears only by owner action); idempotent orders
(deterministic `client_order_id` `atlv1-<strat>-<sym>-<side>-<date>-<chunk>`;
on timeout query-by-id before any retry); limit-day orders only, collared ±2% of last
trade; every run writes a `trader.runs` row (config hash, git SHA, inputs
digest) — determinism discipline; stale quotes (>10 min) → no new orders;
**paper host is the only base URL in the package** (`test_paper_only` greps).

## 6. Risk kernel (deterministic; limits.yaml v1 values)

Instrument allowlist, deny-by-default, each entry with its own weight cap:
SPY 0.95 / VTI 0.95 (wash-sale substitute) / EFA 0.40 / AGG 0.60 /
SGOV 1.00 / BIL 1.00. Long-only; cash account semantics (no margin, no
shorting, no options, no crypto). Gross exposure ≤ 100%. Per-order notional
≤ 10% of equity (multi-order rebalances split). Orders ≤ 10/run, ≤ 20/day.
Daily-loss breaker: portfolio down >3% intraday vs yesterday's close → no
further orders today (long-only ETF book: a −3% day is malfunction-or-crash;
halting new orders is cheap). Max-drawdown kill: −25% from equity high-water
→ flatten to SGOV, halt all strategies, owner-only reset (this is a
malfunction bound, deliberately BELOW the market's own worst case so the
trend gate — which historically exits around −10/−15% — fires first; if the
kill ever fires, something is broken). Wash-sale guard: 31-day re-entry
block per symbol after a realized loss, satisfied by the allowlisted
substitute (SPY↔VTI) so the book is never forced out of the market.
Breaker/halt state persists in `trader.halts` (survives process death).
The kernel validates typed order intents and returns accept/reject with
reasons; **nothing in the kernel is LLM-decidable** (SEC 15c3-5 pattern).

## 7. Strategy book v1 + promotion ladder

`strategy_v1.yaml` (stage: paper): **trend-gated core + cash floor** —
core sleeve 90%: SPY when SPY > 10-month SMA at month-end (±1% hysteresis
band), else SGOV; floor sleeve 10% + all idle cash: SGOV. Monthly rebalance
(first trading day) plus drift-band repair (>5pt absolute drift). Expected
honest outcome: ≈ market returns on the sleeve, ~3.8% on cash, crash
drawdowns historically truncated; expected return edge vs SPY ≈ 0 or
slightly negative. Its ledger card says exactly that — the v1 book's job is
plumbing-proof + insurance, not alpha claims.

Ladder (encoded as data in strategy_state, gates deterministic):
`candidate → validated` — walk-forward + purged CV on free daily data,
costs modeled, DSR > 0.95 against the lifetime trial count N (append-only
`trials.jsonl`; rejects count), ≥30 trades/OOS slice for trade-level
strategies; policy-class strategies (like v1) validate mechanics + tracking,
not alpha. `validated → paper` — governor proposal + ledger card.
`paper → live_canary` — **owner-only** (§8): ≥60 trading days AND ≥30
closed trades (or 3 clean monthly rebalance cycles for slow policies), paper
Sharpe ≥ 0.5× backtest, maxDD ≤ 1.5× backtest, slippage ≤ 2× modeled, order
error rate <1%, zero unresolved reconciliation breaks. Live: canary 1–2% of
capital → 10% → 25% hard per-strategy ceiling, each step ≥20/40 trading
days and owner-edited. Demotion is automatic and code-side: DD > 1.5×
backtest maxDD → down one stage; DD > 2× or two daily-breaker trips in 10
sessions → back to paper; rolling 60-day Sharpe < 0 → down one stage.
MinTRL honesty: live statistical significance is unreachable on our
timescale (SR≈1 needs ~15 years of monthly obs) — the ladder bounds loss
during irreducible uncertainty; it does not prove alpha.

## 8. Live-money ignition (owner-only; ships as trader/GO_LIVE.md)

No live code exists in v1. Going live = the owner, by hand: (1) edits
`trader/CLAUDE.md` rule 1 (and momentum/CLAUDE.md rule 10 stays untouched —
separate verticals); (2) approves the reviewed diff that adds the live
endpoint + `live_enabled`/capital-ceiling config; (3) creates live keys,
puts them in root `.env`, immediately applies the §3 account-configuration
clamps, never enables Crypto Wallets; (4) sets the canary ceiling in
limits.yaml. The GO_LIVE runbook also lists the §7 evidence preconditions
the governor must show first, and the standing advice that the honest
expected value is market-beta + cash yield + crash insurance — if that is
unattractive, the correct move is not-going-live, and the paper loop keeps
searching at zero capital risk.

## 9. The agent suite (the loop) and how it learns from itself

Three skills, staged atlas-side then byte-identical on ai-server
(k401/momo frontmatter patterns):

| Skill | Cron (UTC) | Model | Isolation | Duty |
|---|---|---|---|---|
| `atlas-trader-paper` | `30 17 * * 1-5` | sonnet-4-6 / medium | workspace + `{"project_slug":"atlas"}` | run `python3 -m trader.executor`, verify run row + clean reconciliation, one-paragraph daily report; anomaly → file finding. NEVER edits strategy/limits/code; supervisor only. |
| `atlas-trader-research` | `0 13 * * 3` | opus-5 / high | workspace + payload, 3600s timeout | one governed research cycle under trader PROTOCOL: analyst card (pre-registered, Criteria observables) → deterministic backtest harness → adversarial validator → risk-officer if risk surface → documentarian seals ledger + trials.jsonl; may produce a new additive strategy_vN.yaml candidate; subagents [code-review]; push gates. |
| `atlas-trader-evaluate` | `0 15 * * 0` | opus-5 / high (→xhigh escalation) | none (shared dev clone, like atlas-evaluate) | GOVERNOR: grades the week from DB evidence only (runs fired? reconciliation clean? equity vs frozen SPY/BIL benchmark pair? tracking error vs expectation? breaker events?), appends ledger GRADE entry, files lessons (`atlas-dash learn trader_strategist ...`), executes gated stage flips (never paper→live), schedule-liveness check on all three trader schedules, proposes system changes per LOOP.md §7 front door. |

Learning channels — explicit, and nothing else (recon: Library Drift,
PACE, Voyager/ExpeL evidence):

1. **Episodic, append-only** (never rewritten): `trader.runs`/`orders`/
   `equity_curve` rows, `evaluation/LEDGER.md` T-entries,
   `trials.jsonl`. Raw evidence is the substrate; no LLM re-consolidation
   pass exists (documented compounding-error failure mode).
2. **Semantic, capped + curated**: lessons via `atlas-dash learn` under new
   experts `trader_strategist` / `trader_adversary` (existing bounds:
   60/expert, dedupe). Lessons carry provenance (ledger IDs) and enter as
   candidates; the governor cites which lessons a graded week engaged, so
   contribution is trackable and retirement is evidence-rich, not vibes
   (Library Drift: LLM-authored lessons contribute ~0 unless outcome-gated;
   under-evidenced pruning is itself harmful).
3. **Procedural, versioned + gated**: strategy YAMLs are additive; stage
   flips are governor commits with ledger evidence; the backtest harness,
   risk kernel, limits.yaml, and gate thresholds are OUTSIDE every agent's
   write mandate (owner/[system]-lane only) — the evaluator the learner
   cannot edit is the load-bearing anti-Goodhart control (FunSearch/
   AlphaEvolve, Gödel-machine co-evolution warning).
4. **Ops lessons**: per-skill GOTCHAS.md via context_files from day 1
   (avoiding the known inert-GOTCHAS trap), mechanical appends exempt from
   the [system] ceiling per LOOP.md §7.

Anti-Goodhart controls: frozen benchmark pair (SPY total return + BIL) in
every weekly grade; trial registry + DSR; validator/generator/governor role
separation across different scheduled sessions; criteria scored-as-written
(§2a); periodic decoy candidate rounds (armed in PROTOCOL, exercised at
governor's cadence); quarterly no-lessons baseline cycle to measure whether
accumulated memory still helps (Library Drift's honest test).

## 10. Rollout (this session) + verification

1. Spec (this doc) + atlas `plans/trader/DESIGN.md`.
2. Atlas: `trader/` vertical + migration 0042 + tests green
   (`cd trader && .venv/bin/python -m pytest -q`), momentum/dashboard/pmedge
   suites stay green, ledger seeded (T-0001 infra card, T-0002 v1 policy
   card with honest expectations), trials.jsonl seeded.
3. Atlas: manifest.yml trader test gate + skills/atlas-redeploy gate block
   (both repo copies — the 2026-08-07 lesson: manifest gates must also land
   in the redeploy skill), staging skills + heal atlas-evaluate staging
   drift.
4. ai-server: 3 skills + GOTCHAS + seed-schedules rows + SKILLS_REGISTRY +
   atlas division CHARTER roster + INDEX/CHANGELOG; `python
   scripts/lint_docs.py` green; pytest green.
5. Gates: secrets grep, in-session code-review LGTM (INV-13) on both diffs,
   fetch/merge, push atlas master + ai-server main; deploy through the
   established chain (autopilot / deploy-director dispatch); schedules seed
   on deploy; owner notified with diff summary (this session's report).
6. First fires: paper run next weekday 17:30 UTC; research Wed 13:00;
   governor Sun 15:00.

Out of scope this session: any live code path (ceiling), paid data
(ceiling), options/shorting/margin/crypto (risk posture), /trader web page
(filed as a `data_gaps` row, sector `trading`, for the build loop),
reopening the momentum SIP decision (owner's call, unchanged).
