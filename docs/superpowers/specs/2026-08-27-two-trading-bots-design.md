# Two Trading Bots — Design & Implementation Plan

**Date:** 2026-08-27 · **v3: 2026-08-30** · **Status:** ACCEPTED-DIRECTION — build starts at P0/P1. Nothing implemented yet.
**Owner request (as evolved):** (1) a short-term aggressive stock/options trading account driven by technicals and recurring patterns, high risk tolerance, no trade >50% of account value, mandatory stops/safeguards, every trade tracked and audited — **auto-trading**; (2) a medium/long-term value engine using earnings and financial fundamentals — **v3 change: no automated trading; it generates theses/suggestions for the owner's own portfolio** (long entries, margin-secured put ideas, exits), with every suggestion tracked and graded.

**Owner decision log:**
- 2026-08-30 (v2): two different brokerages; **real money day 1** at reduced size for the auto-trader (shakedown → funded canary → evidence-gated scale ladder); **margin-secured ("shares-secured") puts, never cash-secured** (idle-cash drag rejected).
- 2026-08-30 (v3): **Bot 2 does not trade.** It becomes an advisory vertical producing theses for the owner's normal portfolio. Consequences: tastytrade account no longer needed; **Tradier is the only brokerage account in the plan** (Bot 1 execution + market/options data for both bots); Bot 2 has no funding, no ladder, no order path — its accountability mechanism is a **shadow ledger** that tracks every suggestion as-if-executed and grades it.

**Evidence base:** 9-agent research sweep 2026-08-27 + 3-critic adversarial review (33 findings incorporated) + Robinhood/second-broker re-verify + margin-secured-put verification (both 2026-08-30). Upstream patterns: atlas `trader/` vertical (execution + governance), atlas k401 weekly review (owner-portfolio advice), atlas advisors vertical 0043 (shadow-scoreboard grading of picks).

---

## 0. Summary

Two new **atlas verticals**, sharing one architecture doctrine: deterministic model-free Python computes, enforces, and records; Claude agents supervise, decide within hard rule bounds, research, and grade; everything lands in append-only Postgres + ledger audit trails.

- **`swing/` (Bot 1, auto-trading, Tradier):** 1–10 day aggressive swing trades in liquid stocks + defined-risk options. LLM picks only among deterministic screener candidates carrying per-field bounds; a risk kernel (22 rules incl. the owner's 50%-per-trade cap, mandatory broker-resident exits, breakers, live equity cap) validates and places. Real money at reduced size after a ~2-week sandbox shakedown; every scale-up gated by governor evidence; demotions automatic.
- **`value/` (Bot 2, advisory, no broker account):** weekly deep run screens the market on fundamentals (F-score gate, FCF/EV-EBIT/ROIC composite, value-trap filters), then produces **specific, sized, invalidation-tagged theses** — buy X at ≤$Y (5% slug), sell the X $40 put 35 DTE ~0.25Δ for ~$Z (obligation math included), exit/trim W — delivered by Telegram + dashboard. A daily monitor watches open theses (earnings approaching, invalidation hit, target hit) and alerts. **Every thesis is booked into a shadow ledger at quoted prices and graded weekly by a frozen governor against SPY** — the owner sees whether the advice is good before acting on any of it.

Doctrine unchanged: **"LLM proposes, kernel disposes"** for the trader; for the advisor, the same guard math runs as **quality gates on suggestions** (a thesis violating earnings vetoes, liquidity floors, or sizing rules is never emitted).

---

## 1. Decisions — resolved and open

**Resolved:** O-1 aggressive constitution approved · live-small-day-1 + ladder (Bot 1) · margin-secured put *mechanics* retained in Bot 2's suggestions (cash-secured explicitly rejected) · Bot 2 advisory-only (v3) · stdlib+pyyaml ceiling · Alpaca out of execution (hard-blocks uncovered puts; stays as free data fallback) · Robinhood excluded (§3 postscript).

**Open — P0 owner actions:**

| # | Action | Notes |
|---|---|---|
| P0-A | **Tradier**: open account + **Pro** ($10/mo) + margin + options **Level 3**; API token (never expires) + sandbox token into atlas `.env` | The single brokerage account in the plan: Bot 1 execution + real-time stock/options data with ORATS greeks for BOTH bots' universes |
| P0-B | **Swing funding amount** (wired only after shakedown passes) + initial `max_live_equity_usd` | Floor ~$10k; better $25k+ for concurrency under the heat caps |
| P0-C | **Portfolio context for the advisor** — pick one: (i) maintain holdings in atlas's existing portfolio store (already feeds `/portfolio`), (ii) k401-style CSV upload cadence, (iii) start portfolio-blind (theses still work, lose position-aware exits/overlap warnings) | Recommendation: (i) — the store exists and the k401 vertical proves the owner-upload pattern. Advisor reads it if present, degrades gracefully if stale (staleness shown on the report) |
| P0-D | **Tax params** for swing's after-tax reporting (marginal rate + NIIT flag); confirm §475(f) not elected | The advisor's shadow ledger is tax-free by construction but its suggestions display holding-period/LTCG notes for the owner |
| P0-E | Optional one-time ~$29 options-history backfill to skip the ~60-session IV-rank warm-up | Both bots' IV gates start on the declared IV/HV20 proxy otherwise |

---

## 2. Approaches considered

- **Vertical shape:** extend `trader/` (rejected — constitution conflict) → **two new verticals on its pattern (chosen)** → standalone project (rejected — overhead).
- **LLM role (swing):** fully deterministic → **LLM-proposes-kernel-disposes (chosen)** → free-form LLM trading (rejected; long-window decay evidence).
- **Live posture (swing):** months of paper → **shakedown-then-live-small, evidence-gated scaling (chosen, owner)** → no shakedown (rejected — plumbing bugs would debut on real money).
- **Bot 2 accountability (v3):** ungraded suggestions (rejected — advice without a scoreboard is noise) → **shadow ledger, as-if-executed, frozen-governor-graded vs SPY (chosen; proven pattern in atlas advisors 0043)** → auto-trading (owner withdrew it).
- **Put collateral in suggestions:** cash-secured (owner rejected) → **margin-secured with obligation-based sizing math shown per thesis (chosen)** — the suggestion states obligation (strike×100), estimated ~20%-rule margin, premium, and the assignment-stress impact on the owner's stated portfolio, so the owner sees the real exposure, not the margin illusion.

---

## 3. Broker & venue: Tradier only

- **Tradier — Bot 1's execution home + the plan's data backbone.** Broker-resident **OCO/OTO/OTOCO on stocks AND options** (entry+target+stop rest at the broker between cron runs); never-expiring personal tokens; multileg ≤4 legs with a **preview endpoint** (margin change + warnings pre-commit, a natural guard hook); **Pro $10/mo = $0 stock/$0 option contracts**; real-time NBBO-quality quotes + chains with ORATS greeks/IV free with the account — serving both the swing universe and the value advisor's screens. Sandbox (15-min delayed, crude fills) hosts the shakedown. Coded-around: Tradier's risk desk may auto-close short options near expiry (our morning enforcement pre-empts).
- **Alpaca** — free data fallback (IEX bars, history, benchmarks; SPY/BIL closes frozen into curves); no execution role (hard-blocks uncovered short options — moot now for Bot 2, still disqualifying for any future put-selling automation). Trader v1's paper account untouched.
- **tastytrade** — no longer needed (v3). Recorded for the future: if the owner ever re-automates the value strategy, tastytrade Basic-level margin-secured puts + per-order margin dry-run was the verified home (2026-08-30 report in session archive).
- **Robinhood postscript (owner asked; verified 2026-08-30):** official **Agentic Trading** MCP exists (launched 2026-05-27; ring-fenced agentic account; $0/$0 fees) but is excluded: agent orders are **long-only** (no short legs), options rollout is eligibility-gated with no documented resting stop/OCO types, and the LLM session is the only sanctioned order path (collides with LLM-never-places-orders) with undocumented headless auth; no simulated mode. Future option: a small long-only sleeve as a separate decision. Caution: `cortex-robinhood.com` is an unaffiliated impersonation domain. **v3 note:** the owner's "normal portfolio" may well live at Robinhood — the advisor's theses are broker-agnostic instructions the owner executes wherever they hold assets; nothing in this plan touches that account.

---

## 4. Data: $0 recurring stack (with declared warm-ups)

| Need | Primary ($0) | Fallback ($0) |
|---|---|---|
| Quotes/bars/chains/greeks (both bots) | **Tradier account data** (real-time; ORATS greeks — recomputed locally at decision time) | Alpaca IEX; yfinance (research only) |
| Benchmarks + daily history | Alpaca REST (SPY/BIL closes frozen into equity + shadow curves) | yfinance |
| **IV rank** (swing option setups; advisor put theses) | Self-accumulated daily `iv_snapshots` from P1 deploy; IVR live at ≥60 sessions; until then declared IV/HV20 proxy, tagged `ivr_proxy` | P0-E backfill ends the warm-up |
| VIX (regime gates) | FRED `VIXCLS` (EOD) | Cboe delayed CSV |
| Fundamentals (advisor) | SEC EDGAR companyfacts + frames — **extend the existing atlas_dash ingestion, do not duplicate** | FMP free, Finnhub basics |
| Earnings calendar (blocking dependency for both) | Finnhub | Alpha Vantage CSV; FMP |
| Estimate-revision signal (advisor overlay) | Self-built consensus-delta (weekly snapshots, 4-wk diffs; ABSENT during warm-up; **overlay tag, never a hard reject**) | — |
| Universe & screening | Static versioned universe (S&P 500 + top-ADV optionable ETFs, monthly config commit); stdlib screens | Screener packages research-only |
| Owner holdings (advisor, optional) | Atlas portfolio store per P0-C | k401-style CSV |

Hard rules unchanged: limit-order pricing assumptions only; every decision/thesis logs its quote snapshot; ERROR/ABSENT/UNMEASURABLE distinct with declared fail directions (stale regime data blocks new risk-adding entries/theses, never lifecycle management); per-broker rate budgets; streamers are conveniences — every path completes on REST polling.

---

## 5. Architecture

### 5.1 Repo layout (atlas repo)

```
atlas/
  tradingcore/            # shared lib (stdlib+pyyaml): tradier.py (OTOCO, multileg,
                          #   preview), alpaca_data.py (bars only), black_scholes,
                          #   synthetic_oco backstop, guards, NYSE calendar w/ early
                          #   closes, rate budgets, iv_snapshots collector, universe
  swing/                  # Bot 1 (auto-trader): CLAUDE.md (rule 1: live cap), LADDER.md,
                          #   owner-owned limits.yaml incl. max_live_equity_usd,
                          #   signals S1–S5, screener, risk.py, executor, ledgerlink,
                          #   evaluation/, tests/ (live-guard tripwires)
  value/                  # Bot 2 (advisor): CLAUDE.md (rule 1: NEVER places orders —
                          #   no broker credentials in this vertical), screen.py,
                          #   theses.py (suggestion builder + quality gates),
                          #   shadow.py (as-if-executed ledger), reports.py,
                          #   evaluation/, tests/ (no-order-path grep tripwire)
  db/migrations/          # next three available numbers (≥0044 — 0043 taken by the
                          #   advisors vertical; verify at implementation):
                          #   trading_shared · swing · value_advisor
  web/app/trading/        # dashboard pages (§9)
```

`trader/` v1 untouched (one GOTCHAS cross-note). **Universe partition:** trader's allowlist symbols (SPY/VTI/EFA/AGG/SGOV/BIL) and their options stay excluded from swing's tradeable set (QQQ/IWM are its index workhorses). The advisor may *analyze* anything, but its reports flag overlaps with swing's open positions and with trader's holdings (double-exposure + wash-sale warnings for the owner, who is one taxpayer).

### 5.2 Agent topology (8 scheduled skills)

Staged byte-identical from atlas `integrations/ai-server/skills/`; seeded by `seed-schedules.sh`; payload + workspace isolation for operational/research skills; evaluate skills follow the trader-evaluate posture (no payload, shared dev clone). DST: dual month-gated UTC rows + executor `off_window` guard; early-close days shift enforcement to the morning run; fills/theses record minutes-to-close.

| Skill | Cadence (ET) | Model | Role |
|---|---|---|---|
| `atlas-swing-supervise` | weekdays ~09:40 | sonnet / med | Deterministic lifecycle: verify resting OTOCO exits survived overnight/corporate actions, gap checks, **expiry-day disposals (R12 enforcer)**, breaker + buying-power state. Never places entries, never fixes code |
| `atlas-swing-trade` | weekdays ~15:45 | opus / med | Decision run: `--screen` (candidates with per-field bounds) → LLM selects/vetoes → `--submit` (kernel + preview-before-submit → OTOCO) → verify, report |
| `atlas-swing-research` | Fri 13:00 UTC | opus / high | One governed hypothesis cycle; deny list (limits, risk.py, executor, `tradingcore/*`, live-guard tests) enforced by grep tripwires + code review |
| `atlas-swing-evaluate` | Sun 16:00 UTC | opus / high | Frozen governor: DB-rows-only grades vs frozen SPY+BIL, liveness sweep, deterministic demotions, ladder step-up memos |
| `atlas-value-theses` | Mon ~10:30 | opus / high | Weekly deep run: deterministic screen → ranked watchlist → LLM composes theses **inside the §7.3 rules** → suggestion quality gates → shadow-ledger booking → Telegram report + dashboard |
| `atlas-value-monitor` | weekdays 18:10 UTC | sonnet / med | Deterministic daily sweep of OPEN theses: invalidation triggers, targets hit, earnings entering a suggested put's window, 21-DTE/50%-premium checkpoints on suggested puts, staleness of owner holdings snapshot → owner alert only when something changed |
| `atlas-value-research` | Tue 13:00 UTC | opus / high | Governed hypothesis cycle on screen/params |
| `atlas-value-evaluate` | Sun 17:00 UTC | opus / high | Frozen governor: grades the **shadow ledger** vs SPY (regime-annotated), thesis hit-rate/expectancy, process compliance; optional comparative line vs the advisors-vertical persona scoreboard |

### 5.3 Decision paths

```
SWING (execution):
[deterministic] screener → candidates JSON with per-field bounds
[LLM, bounded]  select/veto → OrderIntent; kernel rejects any field looser than bounds
[deterministic] kernel: bounds + limits + account state + broker preview → place → audit
                (ledger write and order submission are one transaction)

VALUE (advisory):
[deterministic] screen pipeline → ranked tagged watchlist (auditable weekly file)
[LLM, bounded]  compose theses inside the decision-rule set (§7.3) — entry, size-for-
                the-owner's-stated-portfolio, invalidation, horizon, rationale
[deterministic] suggestion quality gates (earnings veto, liquidity floors, obligation
                math, sizing sanity) — a failing thesis is never emitted →
                shadow-ledger booking at quoted prices → report
```

---

## 6. Bot 1 — `swing/` on Tradier (auto-trading; unchanged from v2)

1–10 day swing holds; cron cadence with no intraday pretense; PDT rule eliminated June 2026 (intraday-margin awareness instead; margin is plumbing, gross ≤1.0× equity). **Setups S1–S5** (Dip Snap mean reversion; Drift Rider post-earnings; High Ground breakout; Cheap Shot debit spread; Paid to Agree credit spread on QQQ/IWM/mega-caps) with the standing honesty notes (published RSI-2 win rates are stop-less historical profiles, not forecasts; caps clip realized risk to ~1.25% on low-vol names; governor baselines use realized numbers).

**Risk rules R1–R22** as specified in v1/v2: owner's **50%-per-trade ceiling** (spreads at structural max loss), 1–3% risk-per-trade sized off ATR stops then clipped, 6% heat, 10% premium-at-risk, 5/2 concurrency, −3% daily-loss breaker, −8%/−12% drawdown breakers (owner-only reset), stop-out + losing-streak cooldowns, earnings blackout, liquidity floors, limit-only orders with price sanity, no same-day round trips, full audit incl. logged no-trades, out-of-band watchdog, R20 early-assignment doctrine, R21 corporate-actions/halts doctrine, **R22 `max_live_equity_usd`** (kernel refuses orders above the cap; owner hand-edit only; grep-tripwired). Tradier specifics: entries rest as **OTOCO groups** (exits survive loop death); preview-before-submit with warnings logged; multileg-OTOCO support verified at P1 (else spreads keep synthetic exits — defined-risk either way); R12 morning expiry enforcement pre-empts Tradier's auto-close desk.

---

## 7. Bot 2 — `value/` advisor: theses for the owner's portfolio

**Mandate:** find good companies at fair prices and tell the owner exactly what it would do — buy, sell a margin-secured put, exit, or pass — with sizes scaled to the owner's stated portfolio, invalidation conditions attached, and a shadow ledger keeping score. The owner executes (or ignores) suggestions in their own account; **this vertical holds no broker credentials and has no order path** (grep-tripwire-enforced, like `test_paper_only.py` in trader v1).

### 7.1 Screening pipeline (deterministic; every number fetched + logged, never model memory)

Unchanged from v2: universe = static versioned list, mkt cap ≥$1B, optionable, ex-financials/REITs/utilities. Stage 1 hard rejects (Piotroski F-score ≤6; net debt/EBITDA >3; interest coverage <3; accruals — CFO<0.8×NI when NI>0, scaled accruals when NI≤0; OI/spread fails). Stage 2 composite rank (FCF yield + EV/EBIT + ROIC; **cheapest decile dropped** — value-trap zone). Stage 3 overlay tags (consensus-delta, IVR/proxy, distance-to-support, days-to-earnings, GARP). Output: ranked ~25-name watchlist persisted as the week's auditable file.

### 7.2 Thesis composition rules

Each emitted thesis is one of:
- **LONG** — buy ≤ $limit, slug sized at ~5% of the owner's stated portfolio value (P0-C), thesis horizon, invalidation (Stage-1 reject fires, support break, rank decay), LTCG note when relevant.
- **MARGIN-SECURED PUT** — sell the X $K put, 30–45 DTE, 0.20–0.30Δ (default 0.25), strike ≤ min(delta band, support, happy-to-own), only when IV gate rich (IVR≥30–40 or tagged proxy), expiry **before next earnings (hard veto)**, OI ≥500 / spread ≤10% of mid. The card shows the honest numbers: premium, **assignment obligation (strike×100)**, estimated ~20%-rule margin, annualized yield on obligation, and the standing management plan (50% profit buyback, 21-DTE close/roll rule, net-credit rolls only, then take assignment). Aggregate suggested-put obligation across open theses ≤40% of stated portfolio; assignment-stress note (all suggested puts assigned at once → cash/margin impact on the owner's stated portfolio).
- **EXIT/TRIM** — only when P0-C holdings data exists: position no longer passes Stage 1 (thesis broke — exit regardless of P&L), rank decayed below ~top-60%, or concentration drift; days-to-LTCG surfaced on discretionary exits.
- **PASS** — a name that looks tempting but fails a gate, with the failing gate named (educational value + audit honesty).

**Suggestion quality gates (deterministic, run before anything is emitted):** earnings veto, liquidity floors, sizing arithmetic vs stated portfolio, obligation caps, regime breaker (SPY<200dma AND VIX>30 → no new put theses; long theses tagged half-size), overlap warnings (swing open positions, trader holdings, recent realized losses in the shared wash-sale registry — the owner is one taxpayer). A thesis failing any gate is not emitted; the gate result is logged.

### 7.3 Shadow ledger (the accountability mechanism)

Every emitted thesis is **booked as-if-executed** at the logged quote snapshot (longs at limit-or-quote, puts at mid-with-haircut — half the spread, pessimistic by construction). The daily monitor marks lifecycle events (invalidation hit → shadow-closed at quote; 50% premium target → shadow buyback; 21 DTE → shadow roll/close per the stated plan; assignment at expiry if ITM → shadow stock at effective basis). Nothing is ever edited retroactively; the ledger is append-only with the same discipline as `trials.jsonl`. Weekly, the frozen governor grades: shadow P&L vs SPY (regime-annotated — the put sleeve is *expected* to lag melt-ups, up to ~18pp in the worst documented year, and must win flat/down tapes), thesis hit-rate, put-suggestion win rate (≥75% target once N permits), invalidation discipline (were exits called before the damage), and process compliance (zero gate violations — pass/fail). Optional benchmark line: the advisors-vertical persona scoreboard (0043), so the owner can see whether the in-house engine out-advises the YouTubers.

### 7.4 Delivery

Weekly theses report: Telegram DM (TL;DR paragraph + top actions) + full card view on `/trading/value`. Daily monitor DMs only on state changes (invalidation, target, earnings encroaching, holdings snapshot stale >2 weeks). Every card carries its provenance: screen snapshot reference, quote timestamps, gate evaluations, rationale — the FINRA-derived "reasonable basis, recorded" standard from v1 applies to advice exactly as it did to orders.

---

## 8. Shared compliance & guard layer

- **DR-0 order-path exclusivity (narrowed to swing):** the swing executor is the system's only order path; no broker MCP tools or direct API calls in any trading skill; detective control — any Tradier order without a matching ledgered decision row → kill switch + owner P0. The value vertical's tripwire is stronger: **no broker-credential access and no order-capable code at all** (grep-enforced).
- **DR-12 wash-sale registry:** live from day 1 for swing's real trades; the advisor **reads** it to warn on suggestions that would wash against swing's recent realized losses (and vice versa on the report). IRA/401k cross-account caveat rides every weekly report.
- **DR-14/16 tax honesty:** swing's P&L shown pre-tax and after-tax-estimate; 1099-B export per its account. Advisor cards show holding-period/LTCG notes; the shadow ledger itself is tax-free.
- **DR-17 conduct:** swing-only now (single execution account) — cancel/replace ≤5 per order, no close-manipulating orders.
- **DR-19/20/21:** decision provenance on every order AND every thesis; kill switch (Telegram → psql halts row → **layer zero: Tradier dashboard / token revocation, works with the server dead**); atomic ledger-write-then-order for swing; out-of-band watchdog (independent launchd timer + external heartbeat) as a funding-gate precondition.
- **Schemas** (next available dbmate numbers ≥0044): `trading_shared` (iv_snapshots, wash registry, symbol/overlap registry), `swing.*` (runs, orders w/ `aswg-` prefix + options fields, positions_lots, decisions, equity_curve w/ frozen SPY/BIL, strategy_state `candidate|validated|live_capped`, halts), `value.*` (screen_snapshots, theses, shadow_ledger, shadow_curve w/ frozen SPY, grades).

---

## 9. Dashboard (atlas web, behind Cloudflare Access)

- **`/trading`** — overview: swing equity vs SPY/BIL, advisor shadow curve vs SPY, breaker/halt states, worker liveness, pending DECISION-REQUESTs, warm-up status.
- **`/trading/swing`** — positions with resting OTOCO exits + DTE clocks; blotter with slippage + minutes-to-close; governor-computed setup performance; decision journal incl. no-trades; risk panel; **ladder panel** (cap, deployed vs cap, evidence progress to next step, demotion history).
- **`/trading/value`** — current theses as cards (entry/size/invalidation/rationale/gate provenance); open-thesis board with lifecycle state; **shadow scoreboard** (P&L vs SPY regime-annotated, hit-rate, put win rate, invalidation discipline); watchlist with rank moves; overlap/wash warnings; holdings-snapshot freshness.

All numbers from DB rows/ledger artifacts only; Telegram remains the push channel.

---

## 10. Evaluation & expectation contracts

**Swing:** live fills are the strategy evidence (sandbox output is plumbing evidence only). Success at current ladder size = zero kernel breaches, complete audit, positive realized expectancy; full-size verdict needs ≥6 months / ≥100 live trades; setup kill rule runs on governor-computed realized edge (no researcher-declared numbers in demotion math); "no valid setup → no trade" is a logged success.

**Value advisor:** the shadow ledger is the evidence. Process compliance is pass/fail and dominates (zero emitted-gate violations; no retroactive edits; every card fully provenanced). Performance judged regime-annotated vs SPY at 6–12 months (value strategies need time; a melt-up lag on the put sleeve is expected behavior, not failure); put-suggestion win rate ≥75% once N≥20; invalidation discipline (loss beyond stated invalidation without an exit call = a named failure class). The governor may recommend the owner *stop reading* the advisor (the honest kill switch for an advice product) — that recommendation is deterministic on thresholds, not vibes.

Both governors: DB rows only, frozen benchmarks, deterministic demotions/verdicts, owner DECISION-REQUESTs for any rule change; `trials.jsonl` + DSR discipline in both research loops; LLM-signal candidates' historical backtests inadmissible.

---

## 11. Swing shakedown → funding → scale ladder (`swing/LADDER.md`)

**Phase S (~2 weeks, unfunded):** full schedules against Tradier sandbox; mechanical exit criteria — ≥10 clean sessions, zero kernel breaches, zero unexplained reconcile breaks, assignment/expiry/halt/cancel-replace paths exercised (sandbox + stub fixtures), watchdog fired on an induced silent-worker drill, kill switch exercised end-to-end. Governor writes SHAKEDOWN-PASS citing each criterion. The advisor needs no funding gate: its "shakedown" is 2 dry weekly runs reviewed by the owner before the first real DM'd report.

**Funding gate (owner):** wire P0-B; hand-set initial `max_live_equity_usd` below the wired amount. CLAUDE.md rule 1: *agents, research loops, and governors may propose but can never raise any cap; every raise is an owner hand-edit with a reviewed diff.*

**Scale ladder:** each step (~doubling) needs a governor memo: ≥40 live trades at current step, positive realized expectancy, 4 consecutive weekly PASS, zero kernel breaches. Automatic demotions in code: drawdown >1.5× worst prior-step drawdown → down one step; two daily-breaker trips in 10 sessions → down one step + owner page; −12% HWM → frozen lifecycle-only until owner reset.

---

## 12. Implementation plan

Standard gates every phase: atlas pytest path-conditional (new blocks for `tradingcore/`, `swing/`, `value/`), ai-server pytest + lint_docs, code-review LGTM (INV-13), secrets grep, registries/CHANGELOG/CHARTER/INDEX updates, seed-schedules sole writer, byte-identical staging, deploy via push → `/task deploy server` + `/task redeploy atlas`.

| Phase | Contents | Est. |
|---|---|---|
| **P0 owner** | P0-A…P0-E: Tradier account/approvals/tokens, swing funding amount decided, portfolio-context choice, tax params, IV-backfill call | owner |
| **P1 shared** | `tradingcore`: tradier.py (OTOCO, multileg, preview; verify multileg-OTOCO), alpaca_data.py, black_scholes, synthetic-OCO backstop, calendar w/ early closes, rate budgets, guards, iv_snapshots collector (warm-up clock starts), universe builder; `trading_shared` migration; property tests for every guard | 1–2 sessions |
| **P2 swing** | Kernel R1–R22 (property tests incl. candidate-bounds monotonicity + live-cap), signals S1–S5, screener with bounds emission, executor, swing migration, CLAUDE.md/LADDER.md/PROTOCOL seeds, live-guard tripwires, 4 skills + dual-row DST schedules, out-of-band watchdog | 2–3 sessions |
| **P3 value advisor** | Screen pipeline extending atlas_dash EDGAR ingestion (F-score/accruals w/ NI≤0 branch, consensus-delta snapshotter), theses.py + quality gates, shadow.py ledger + lifecycle, reports.py, holdings reader per P0-C, value migration, no-order-path tripwire, 4 skills + schedules; 2 dry runs for owner review | 2 sessions (lighter than v2 — no broker adapter, no assignment automation) |
| **P4 dashboard** | `/trading` pages: swing panels + ladder, advisor cards + shadow scoreboard; npm build gate | 1–2 sessions |
| **Phase S** | Swing shakedown ~2 weeks (concurrent with P4/P5); induced-failure drills | 2 wks wall-clock |
| **P5 loops** | Research cycles live, governors live, decoys armed, evals registered | 1 session + steady |
| **F funding** | Owner wires swing funds + sets cap on SHAKEDOWN-PASS; advisor goes live on owner nod after dry runs | owner |

**Testing:** every R/DR rule has a kernel-rejection test; Tradier form-encoding + preview goldens; OTOCO reconciliation + cancel/replace race; assignment/expiry/halt/split fixtures; live-cap breach attempts; ERROR/ABSENT/UNMEASURABLE branches; advisor: gate-violation theses must be provably un-emittable, shadow-ledger lifecycle property tests (no retroactive mutation), pessimistic-fill booking tests.

## 13. Top risks

1. **Live-day-1 plumbing (swing)** — shakedown + tripwires + R22; first ladder step is pre-decided tuition.
2. **Advisor credibility** — an advice product can be confidently wrong; mitigated by the shadow scoreboard (graded before trusted), pessimistic booking, process-compliance grading, and the governor's deterministic "stop reading this" verdict.
3. **Sandbox fidelity** — Tradier sandbox delayed/crude; scoped to plumbing evidence only.
4. **Options exit latency (swing residual)** — OTOCO covers stocks/single-legs; spreads may stay synthetic (P1 verification); defined-risk caps damage.
5. **Owner-context staleness (advisor)** — position-aware advice on stale holdings is worse than portfolio-blind advice; staleness is surfaced on every report and monitor alert.
6. **Silent worker death** — out-of-band watchdog (funding-gate precondition); Tradier-resident exits protect swing positions through loop death; the advisor fails safe (no report ≠ no money at risk, but liveness still governor-checked).

## 14. Out of scope

Automated trading for the value strategy (owner withdrew it; tastytrade findings archived for a future re-decision); Robinhood (postscript §3; the owner's own account is untouched by this system); cash-secured put suggestions (owner-declined — margin-secured math only); shorting; naked calls; futures/crypto; intraday/ORB; §475(f); changes to `trader/` v1 beyond a GOTCHAS note; recurring paid data without an owner decision; protected paths (MISSION §M).
