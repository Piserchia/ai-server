# Two Autonomous Trading Bots — Design & Implementation Plan

**Date:** 2026-08-27 · **Status:** PROPOSED — awaiting owner review (nothing implemented)
**Owner request:** (1) a short-term aggressive stock/options trading account driven by technicals and recurring patterns, high risk tolerance, no trade >50% of account value, mandatory stops/safeguards, every trade tracked and audited; (2) a medium/long-term account using earnings and financial fundamentals to buy good companies at low valuations — via cash-secured puts, outright longs, or long holds. Plus workflows, agents, and a dashboard, and a broker recommendation.

**Evidence base:** 9-agent research sweep 2026-08-27 (4 codebase readers over ai-server + atlas trading infra; 5 web researchers over brokers, market data, both strategy domains, and 2025–26 regulation), followed by a 3-critic adversarial review (infrastructure fit, risk/safety, strategy realism — 33 findings, all incorporated below or explicitly owner-flagged). Key upstream docs: `docs/superpowers/plans/2026-08-26-autonomous-trading.md`, atlas `plans/trader/DESIGN.md`, `trader/CLAUDE.md`, `trader/GO_LIVE.md`, momentum-lab `evaluation/PROTOCOL.md` + LEDGER lessons.

---

## 0. Summary

Build two new **atlas verticals** — `swing/` (Bot 1) and `value/` (Bot 2) — cloned from the architecture the shipped `trader/` vertical proved on 2026-08-26: deterministic model-free Python executes and enforces risk; Claude agents supervise, decide within hard rule bounds, research, and grade; everything lands in append-only Postgres + ledger audit trails; live money has no code path until the owner hand-opens one per the GO_LIVE pattern.

**Broker: keep Alpaca for both bots** (rationale §3). **Data: $0 stack at launch, with two honestly-declared warm-up gaps** (IV-rank and estimate-revision signals need self-accumulated history; §4). **Dashboard: new pages inside the existing atlas Next.js app** behind the existing Cloudflare Access gate (§9).

The one deliberate doctrinal change vs `trader/` v1: the LLM is allowed **inside the decision loop** — but only between a deterministic screener (which produces the only candidates it may act on, each carrying machine-readable parameter bounds) and a deterministic risk kernel (which rejects any intent looser than its candidate's bounds). "LLM proposes, kernel disposes" — and §8 adds the detective control for the non-cooperative case.

Both bots run **paper-only** with owner-gated live ignition, exactly like `trader/` v1.

---

## 1. Owner decisions required before build (O-1 … O-6)

| # | Decision | Recommendation |
|---|---|---|
| **O-1** | **Constitutional divergence.** The trader/ vertical's founding evidence review concluded "short-horizon retail trading: negative EV, excluded absent extraordinary evidence," and its risk-officer auto-denies aggressive wiring. Bot 1 contradicts that stance. Approve running Bot 1 as a **separate vertical under its own aggressive constitution**, with the honest expectation contract in §10 (year-1 success = survival + complete audit + Sharpe > 0; beating SPY is a stretch goal, not the base case). | Approve — the point of paper trading is to buy evidence cheaply; the expectation contract keeps it honest. |
| **O-2** | **Account topology.** Trader v1's reconciler halts on ANY foreign open order in its account (hardcoded `CID_PREFIX` check) — bots sharing an account will halt each other. **(a) Preferred, treated as a build precondition:** owner creates two additional Alpaca paper accounts (separate key pairs). **(b) Fallback, only if Alpaca won't grant more accounts:** shared account, which REQUIRES three things this spec otherwise avoids: a scoped owner-approved amendment to trader's reconciler (accept sibling `aswg-`/`aval-` prefixes — the one `trader/` code change, explicitly enumerated), per-bot **virtual capital partitions** in migration 0043 (own equity ledger, own HWM, own breaker inputs — otherwise every equity-denominated rule reads combined equity and one bot's drawdown trips the other's breakers), and a per-key-pair rate budget with static headroom reserved for trader's profile. | (a). Owner also sets each paper account's starting equity to realistic intended live scale. **Sizing arithmetic to decide with open eyes:** value's 8%-per-name cap includes CSP collateral, so at $50k one contract (strike×100) caps tradeable strikes at $40 and most watchlist names route to stock-buys instead; at $100k the CSP mechanism works as designed but sizing evidence is scaled. Recommendation: swing $30k, value $100k, with the §11 value precondition scaled to what the funded universe can actually produce. |
| **O-3** | **Data spend.** Launch is $0. Two candidate upgrades, decided separately: (i) **one-time** ~$29 (single month of Polygon/Massive Options Starter) to backfill options-IV history and shorten the §4 IV-rank warm-up from ~3 months to immediate; (ii) **recurring** Alpaca Algo Trader Plus $99/mo (full SIP + real OPRA + 10k req/min) — improves Bot 1's fill/quote fidelity. Standing policy (momentum-lab E-0027) is that paid data is owner-gated. | Defer (ii) until 60 paper sessions of slippage-ledger evidence. (i) is cheap and removes a real launch degradation — owner's call at P0. |
| **O-4** | **Options approval ceilings.** Bot 2 needs Level 1 (CSP/covered calls); Bot 1 needs Level 2 (long options), Level 3 if spreads ship. | Clamp `max_options_trading_level` to exactly what each bot needs **on paper accounts too** (so paper evidence and blast radius match live constraints), and again at live ignition. |
| **O-5** | **Dependency ceiling.** trader/ v1 is stdlib+pyyaml by owner ceiling. All required math (RSI/ATR/SMA/Donchian, Black-Scholes recompute, F-score components) is stdlib-feasible. Third-party screener packages (`tradingview-screener`, `finvizfinance`) are demoted to research-only convenience — the decision path uses a static versioned universe + Alpaca bars only (§4). | Keep stdlib+pyyaml for both new verticals. |
| **O-6** | **Tax parameters.** After-tax P&L reporting (§8) needs the owner's marginal bracket + NIIT applicability as config. §475(f) mark-to-market is a CPA decision, never assumed. | Owner supplies two numbers in `config/settings.yaml` (est. ordinary rate, est. LTCG rate); defaults 32%/15% until then. |

---

## 2. Approaches considered

1. **Extend `trader/` with new strategies** — rejected. Its constitution excludes short-horizon trading; its risk-officer charter auto-DENIES aggressive wiring; its expectation contract ("market beta + cash yield + crash insurance, not alpha") is the opposite of Bot 1's mandate. Bolting Bot 1 on would either corrupt the existing vertical's governance or be strangled by it.
2. **Two new atlas verticals cloned from the trader/ pattern** — **recommended.** Reuses proven invariants (deterministic executor, owner-owned kernel+limits, schema-refuses-live, worker-trio skills, GO_LIVE gate), the deploy pipeline, the DB, the dashboard, and Cloudflare Access — while giving each bot its own constitution, risk kernel, ledger, and expectation contract.
3. **New standalone project(s)** — rejected. Costs a port, manifest, Access policy, deploy topology, and a second Postgres story; zero isolation benefit for a single-tenant system whose bots share the owner's broker and data.

LLM-role spectrum: fully deterministic (trader v1) → **LLM-proposes-kernel-disposes (chosen)** → LLM free-form trading (rejected; StockBench/live-benchmark literature shows LLM freelancing decays over long windows, and momentum-lab ADR-004 / Profit Mirage evidence stands). The chosen middle keeps every cap, stop, and veto in code while letting the agent do what the owner asked: use technicals, patterns, and judgment to pick among systematically screened candidates.

---

## 3. Broker: Alpaca (both bots), Tradier as designed-for fallback

Ranked evaluation of 9 brokers (Alpaca, Tradier, tastytrade, IBKR, Schwab, TradeStation, Robinhood, Webull, Public.com) on headless auth, options API depth, paper fidelity, safeguard order types, fees, data, and agent-readiness:

- **#1 Alpaca — keep.** Static API keys (best unattended auth); best-in-class paper fidelity (real-time simulated fills, options on by default, multi-leg `mleg` in paper since Jan 2025); options Levels 1–3 via API; stocks get native **bracket/OCO/trailing-stop**; official first-party MCP server exists (65 tools) — an ecosystem-maturity signal, but **broker MCP tools and direct broker API calls are forbidden in every trading skill** (§8): the executor is the only order path. Zero switching cost (keys + env plumbing + client patterns already live here). Known gaps engineered around in §6: no bracket/OCO on options; options orders are **DAY-TIF only for stop types and GTC only for plain limits** — so options stops must be re-placed each morning and synthesized between runs.
- **#2 Tradier** — adopt only if broker-resident options OCO becomes a hard requirement (its OTOCO does entry+TP+SL on options in one payload) or Alpaca reliability disappoints. Non-expiring personal tokens, official hosted MCP (Dec 2025), $10/mo Pro = $0 options commissions. Weakness: sandbox is 15-min delayed → paper evidence is weaker.
- tastytrade (best CSP economics, weak paper env), IBKR (most capable API, gateway/2FA babysitting disqualifies for unattended launchd loops), Schwab (7-day manual OAuth re-login + no paper = disqualified), Robinhood (no stock/options API; ToS ban risk = disqualified), TradeStation/Webull/Public (no advantage / immature / no paper).

**Architecture hedge:** all broker calls go through a thin adapter interface in `tradingcore` (§5) with Alpaca as the only v1 implementation, shaped so a Tradier adapter is a bounded add.

Fee note: Alpaca options ~$0.65/contract in practice (verify current fee schedule before live); stocks $0. Both immaterial at paper stage; the slippage ledger will price them for the live decision.

---

## 4. Data: $0 launch stack (with declared warm-ups)

| Need | Primary ($0) | Fallback ($0) | Paid upgrade path |
|---|---|---|---|
| Real-time quotes/bars (both) | Alpaca IEX feed (provisioned) | — | Algo Trader Plus $99/mo (O-3ii) |
| Daily/intraday history | Alpaca REST (2016+) | yfinance (research only, never in decision path) | — |
| Options chains + current greeks/IV | Alpaca indicative options feed (chain endpoint returns greeks+IV; recompute greeks locally at decision time) | Tradier w/ free brokerage acct (ORATS greeks) | Polygon/Massive Options Starter (O-3i) |
| **IV rank** (gates S4/S5 and all CSPs) | **Self-accumulated:** a daily `iv_snapshots` collector runs from day 1; IVR computed over the growing window once ≥60 sessions exist. **Until then IVR is UNMEASURABLE and the kernel uses the declared launch proxy: IV/HV20 ratio with widened thresholds**, every such decision tagged `ivr_proxy` in the ledger | — | O-3i backfills history and ends the warm-up immediately |
| VIX (regime gates, §6/§7 breakers) | **FRED `VIXCLS`** (free, EOD) | Cboe delayed CSV | — |
| Fundamentals (Bot 2) | **SEC EDGAR companyfacts + frames** (free, keyless, 10 req/s, nightly bulk ZIP + local cache) — NOTE: atlas `dashboard/` (atlas_dash) already ingests EDGAR financials, earnings, and valuation; **audit and extend that pipeline, do not duplicate it** | FMP free (250/day), Finnhub basic financials | Finviz Elite $299.50/yr |
| Earnings calendar (both — blocking dependency for multiple hard rules) | Finnhub `/calendar/earnings` (60/min) | Alpha Vantage `EARNINGS_CALENDAR` CSV (1 call/day); FMP | — |
| **Estimate-revision signal** (Bot 2 overlay) | **Self-built consensus-delta:** weekly snapshots of consensus EPS/recommendation levels from free endpoints, diffed over trailing 4 weeks. True revision *breadth* (I/B/E/S-class up/down analyst counts) is NOT free — the free signal is consensus direction, it reports ABSENT during its N-week warm-up, and it is an **overlay tag, never a hard reject** (§7.1) | — | I/B/E/S-class data joins the O-3 list if evidence warrants |
| Candidate universe & screening | **Static versioned universe** (S&P 500 constituents + top-ADV optionable ETFs, refreshed monthly by the research loop as a config commit), every §6.1/§7.1 screen computed from Alpaca daily bars + EDGAR in stdlib | `tradingview-screener` / `finvizfinance` — **research-only convenience**, never in the decision path (both are unofficial/revocable endpoints) | Finviz Elite |

Hard data rules: IEX prints are indicative, not NBBO → **limit orders only**, and Bot 1's universe restricted to high-liquidity names until/unless SIP. Every decision logs the quote snapshot it acted on (fills graded against it). Any scraper-class source sits behind circuit breakers — a 429 wave degrades to cached data, never blind-trades, never halts the safety loop. Budget Alpaca's 200 req/min **per key pair** via a token bucket in `tradingcore` (frozen trader/ never consults it; if any bot shares trader's account under O-2(b), statically reserve trader's known request headroom). ERROR / ABSENT / UNMEASURABLE are distinct states on every data path (momentum-lab's 7-incident lesson): an API failure is never recorded as "no signal," auth errors abort the run, and each gate declares its fail direction — **VIX/regime data stale >3 sessions fails closed for new risk-adding entries but never blocks lifecycle management** (a data outage can't silently disable a breaker, and also can't strand open positions).

---

## 5. Architecture

### 5.1 Repo layout (atlas repo, mirroring `trader/`)

```
atlas/
  tradingcore/            # NEW shared lib (stdlib+pyyaml), used by swing/ and value/ ONLY
    tradingcore/          #   http retry/backoff, NYSE calendar (incl. EARLY-CLOSE days), alpaca client v2
                          #   (stocks + options: chains, greeks, mleg, brackets, exercise/DNE),
                          #   black_scholes.py, synthetic_oco.py, guards.py (DR-rule primitives),
                          #   ratebudget.py (per-key token bucket), iv_snapshots collector, universe.py
    tests/
  swing/                  # NEW Bot 1 vertical (self-contained like trader/)
    CLAUDE.md             #   rule 1: PAPER ONLY (verbatim pattern) + swing constitution
    GO_LIVE.md            #   owner-only ignition runbook (§11)
    config/               #   limits.yaml (owner-owned), settings.yaml, strategies/ (versioned setups)
    swing/                #   signals.py (S1–S5), screener.py, risk.py (kernel), executor.py, ledgerlink.py
    evaluation/           #   PROTOCOL.md, LEDGER.md, trials.jsonl
    research/  tests/     #   tests incl. test_paper_only.py, test_adoption_gate.py, kernel property tests
  value/                  # NEW Bot 2 vertical, same shape
    ... (screen.py fundamentals pipeline, csp.py lifecycle, wheel rules, risk.py, executor.py)
  db/migrations/
    0043_trading_shared.sql   # wash-sale registry, cross-bot symbol locks, account registry,
                              # iv_snapshots, (O-2(b) only: virtual capital partitions)
    0044_swing.sql            # swing.* schema
    0045_value.sql            # value.* schema
  web/app/trading/...     # dashboard pages (§9)
```

`trader/` v1 is **not modified**, with two explicitly-enumerated exceptions: its GOTCHAS gains a cross-note that sibling verticals exist, and — **only under O-2(b)** — a scoped owner-approved reconciler amendment to accept sibling order prefixes. `tradingcore` changes trigger both new bots' test suites in the atlas-redeploy path-conditional gate; `trader/` keeps its own gate untouched.

**Universe partition (hard rule):** trader v1's allowlist symbols (SPY, VTI, EFA, AGG, SGOV, BIL) **and their options are excluded from swing's and value's tradeable universes** — this is what makes the cross-vertical wash-sale and self-trade guards sound, because frozen trader/ cannot consult them (§8). Swing's index workhorses are QQQ/IWM instead of SPY. Benchmark *reads* of SPY/BIL closes are unaffected (data, not trading).

### 5.2 Process/agent topology per bot

Each bot ships 4 ai-server skills (authored in atlas `integrations/ai-server/skills/`, staged byte-identical, seeded by `seed-schedules.sh` — the sole schedule writer). Payload + `isolation: workspace` apply to the operational and research skills only; **the two evaluate skills follow the shipped trader-evaluate posture: no payload, no workspace — shared dev clone, stop on dirty tree.**

**DST handling (applies to every ET-anchored slot):** cron is UTC and cannot track DST, so each ET-anchored schedule gets **two month-gated rows** (EDT ≈ Mar–Nov, EST ≈ Dec–Feb, imprecise at edges by design) and the executor enforces the truth: it computes minutes-to-open/close from the broker clock and **no-ops with status `off_window` outside its intended ET window**; every fill's ledger row records minutes-to-close so seasonal evidence is never silently pooled. The NYSE calendar module knows **early-close days** (day-after-Thanksgiving, Jul 3, Christmas Eve): on those days the morning supervise/manage run performs ALL lifecycle enforcement (expiries, forced closes) because afternoon runs will land after the 13:00 ET close.

| Skill | Cadence (intended ET; seeded as dual UTC rows) | Model/effort | Role |
|---|---|---|---|
| `atlas-swing-supervise` | weekdays ~09:40 ET (13:40 UTC EDT / 14:40 UTC EST) | sonnet-4-6 / medium | Deterministic lifecycle run: `python3 -m swing.executor --manage` — re-place DAY-TIF option stops (§6.2 R6), verify every stock position's resting stop survived overnight/corporate actions, gap-through-stop checks, synthetic-OCO sweep, **expiry-day disposals (R12 — this run is the enforcer)**, early-close-day full enforcement, breaker state; report; never places new entries, never fixes code |
| `atlas-swing-trade` | weekdays ~15:45 ET (19:45 UTC EDT / 20:45 UTC EST) | opus-5 / medium, max_turns 40 | Decision run near the close: executor `--manage` (backstop closes only on expiry day), then `--screen` (deterministic candidates JSON for S1–S5 **with per-field parameter bounds**), LLM selects/vetoes and writes structured intents, `--submit intents.json` (kernel validates against candidate bounds + limits + account state, places), verify, report |
| `atlas-swing-research` | Fri 13:00 UTC (verified-free slot; Mon 13:00 is taken by `research-report-weekly`) | opus-5 / high, 3600s, code-review subagent + post_review | ONE governed hypothesis cycle under `swing/evaluation/PROTOCOL.md` (card → engineer → adversarial validator → risk-officer on any risk-surface diff → documentarian). Write surface: new versioned setup YAMLs, evaluation appends, scratch, new tests. Never: limits.yaml, `swing/risk.py`, executor, **`tradingcore/*`**, tripwire tests, GO_LIVE, CLAUDE.md, own skill — enforced by prose + code-review + **mechanical grep tripwire tests** (the test_paper_only pattern applied to the deny list) |
| `atlas-swing-evaluate` | Sun 16:00 UTC | opus-5 / high (xhigh escalation) | Frozen governor: grades the week from DB rows only vs frozen SPY+BIL pair; schedule-liveness sweep of all swing workers; deterministic demotions **using only governor-computed inputs (§10)**; promotions candidate→validated→paper only; DECISION-REQUESTs to owner |
| `atlas-value-manage` | weekdays 18:10 UTC (single row; not close-anchored — executor clock-guards RTH) | sonnet-4-6 / medium | Deterministic lifecycle: profit-target fills, 21-DTE checks, earnings-calendar re-verification for every open short put (blocking data), assignment processing, cap-breach scan, circuit-breaker state |
| `atlas-value-decide` | Mon ~10:30 ET (14:30 UTC EDT / 15:30 UTC EST — never the opening bell) | opus-5 / high, 3600s | Weekly deep run: deterministic screen pipeline → ranked tagged watchlist → LLM applies the §7.3 decision tree per name (rule-bounded choices only) → intents → kernel `--submit` → report |
| `atlas-value-research` | Tue 13:00 UTC | opus-5 / high, 3600s | Governed hypothesis cycle on the screen/params (same PROTOCOL machinery) |
| `atlas-value-evaluate` | Sun 17:00 UTC | opus-5 / high | Frozen governor; grades monthly (weekly liveness), regime-annotated per §10 |

Slot deconfliction verified against `seed-schedules.sh` (06:00 managers, 10/11:00 atlas loops, 12:00 brief, **Mon 13:00 research-report-weekly**, Wed/Thu/Sat 13:00 research, Sun 15:00 trader governor, Sun 18:00 report sweep); final slot table lands in the seeder's comments at implementation time.

Failure semantics inherited from trader v1: halted/breaker/`off_window` statuses are SUCCESSFUL supervision outcomes; only crashes fail the job; missing keys = report the provisioning gap, never create credentials; escalation is report-only with owner-attention-now language for kill-switch/reconcile-break/assignment events.

### 5.3 The three-layer decision path (both bots)

```
[deterministic]  screener/signals → candidates JSON — the ONLY things the LLM may act on.
                 Each candidate carries canonical values AND per-field bounds:
                 qty_max, limit_bounds, stop_max_distance, DTE band, structure spec.
[LLM, bounded]   select / veto / rank; structured OrderIntent{candidate_id, side, qty, limit,
                 stop, rationale}. "Tighten-only" is NOT a prompt promise: the kernel
                 rejects any intent field looser than its candidate's bound (per-field
                 monotonicity defined in code, property-tested).
[deterministic]  risk kernel: validate every intent against candidate bounds + limits.yaml +
                 account state + shared guards (wash registry, symbol locks, caps,
                 breakers) → place → audit
```

The kernel re-validates price/size/side against live quotes at submit (reject >1% deviation or stale >5min quote). Ledger write and order submission are one transaction: **no ledger row, no order** (DR-21).

---

## 6. Bot 1 — `swing/`: short-term aggressive stock/options

**Mandate:** 1–10 day swing holds on liquid US equities/ETFs + defined-risk options. Cron cadence cannot do low-latency intraday and will not pretend to (ORB-style strategies explicitly rejected — replication shows break-even at ~2.2¢/share slippage). High risk tolerance = top of the sizing band and aggressive setup selection — never undefined risk.

**Regulatory framing (2026):** PDT rule **eliminated 2026-06-04** (FINRA RN 26-10; Alpaca implemented day one — `pattern_day_trader`/`daytrade_count` API fields REMOVED 2026-07-06; use `buying_power`/`equity`/`maintenance_margin` only). No day-trade counting needed; instead: intraday-margin-deficit awareness — a margin-rejected order is a normal control signal (log, downsize/skip, never retry-loop); any margin call is P0 (auto-cure at the next scheduled run, and the R18 watchdog exists precisely because "same day" is only as good as the loop's liveness). Margin account is plumbing, not appetite: gross exposure ≤1.0× equity by policy.

### 6.1 Setups (v1 sealed strategy library — research loop proposes changes as new versions)

| ID | Setup | Entry | Stop | Exit | Size |
|---|---|---|---|---|---|
| S1 "Dip Snap" | Large-cap/ETF mean reversion (RSI-2 style) | RSI(2)<10 (A+ <5), price>200SMA, no earnings ≤5d, regime risk-on; long near close | 2.5×ATR(14), resting at broker | close>5dSMA or RSI(2)>65; time stop 7d | R=2% (3% A+) |
| S2 "Drift Rider" | Post-earnings-announcement drift | 1–2 days AFTER report: surprise>+5%, gap≥+3% that held, RVOL≥2, >200SMA; stock or bull call debit spread 30–45 DTE (spread preferred — IV just crushed) | below report-day low / structural max loss | Chandelier 3×ATR trail or 50% spread profit; time stop 15–20d | R=2%; debit ≤2% eq |
| S3 "High Ground" | 52w-high breakout continuation (George–Hwang anchor) | close > 20d Donchian high, RVOL≥1.5, ADX>20, top-quartile 6mo RS in top-half sector, within 15% of 52w high | 2×ATR | Chandelier trail; ⅓ off at +2R | R=1.5% |
| S4 "Cheap Shot" | Defined-risk momentum option | S1/S3 signal on options-whitelist name AND IV gate (IVR<40, or launch proxy per §4) → bull call debit spread 30–45 DTE, long 0.55–0.65Δ / short ~0.30Δ, debit ≤40% of width | structural (debit) + synthetic stop on underlying | 50–60% of max value; force-close 10 DTE; never through earnings | debit ≤1.5% eq |
| S5 "Paid to Agree" | Put credit spread on strength (small income sleeve) | S1-quality pullback on **QQQ/IWM/mega-cap** (SPY excluded by the §5.1 partition) AND IV gate (IVR>50 / proxy) → 30–45 DTE, short 0.25Δ, credit ≥25% width | loss = 2× credit | 50% of credit; close/roll 21 DTE; close if short strike ITM | max-loss ≤1.5% eq; max 2 concurrent |

Universe note: S1's index leg and all setups draw from the §4 static universe **minus trader's allowlist** (QQQ/IWM replace SPY as index workhorses). Regime gates still *read* SPY data. Win-rate expectations: the published RSI-2 literature's 70–80% win rates are **stop-less, largely pre-2015 numbers — they are NOT S1's forecast** (the same literature documents that hard stops degrade mean-reversion performance; we keep the stop anyway because an autonomous bot without one is not acceptable). S1's expected metrics are declared unknown ex-ante and set from paper evidence only.

**Honest sizing arithmetic (binding-constraint reality):** for a large-cap with ATR ≈ 1% of price, R2's 2% risk at a 2.5×ATR stop implies ~0.8× equity notional — R1 clips it to 0.5×, capping realized risk near ~1.25%, and R19's 1.0× gross cap limits low-vol concurrency to ~2 such positions, not R5's five. The kernel emits the realized (post-clip) risk per trade; expectation-contract math and governor baselines use **realized** numbers, never the nominal R2 band. "Aggressive" lives in setup selection and the top of the *achievable* band.

**Explicitly forbidden:** intraday ORB, pre-earnings long premium (IV crush), naked short options, 0DTE, sub-$5 stocks, <0.40Δ lottery calls, market orders on options (one exception: the R12 escalation ladder's final step), LLM-improvised trades outside the sealed setup library, trader-allowlist symbols.

**Indicator library (all stdlib-computable from daily bars + one snapshot):** SMA50/200, EMA8/21, ADX(14), VIX level+Δ5d (FRED), RSI(2), %-from-5dSMA, consecutive down closes, ATR(14), HV20/60, IV rank (or launch proxy), %-from-52w-high, 3/6-mo RS, sector RS, RVOL vs 20d same-time average, 20d Donchian, prior swing levels, earnings-gap anchored VWAP, earnings calendar.

### 6.2 Risk rules (kernel-enforced; LLM cannot override any row)

| # | Rule | Value |
|---|---|---|
| R1 | Max notional per trade (owner's cap) | **50% of account equity** at order time. Accounting: stocks at notional; long options/debit spreads at max loss; **defined-risk spreads at structural max loss ((width−credit)×100×contracts)** — full strike×100 collateral accounting applies only to value/'s genuinely cash-secured puts |
| R2 | Risk per trade (stop distance × size) | 1–2% std, 3% A+ — where "A+" is a deterministic screener checklist result, **not a YAML field the research loop can set** |
| R3 | Total open risk (heat) | ≤6% equity |
| R4 | Aggregate option premium at risk | ≤10% equity |
| R5 | Concurrent positions / new per day | 5 / 2 (low-vol names bind earlier via R19 — see §6.1 arithmetic) |
| R6 | Stops mandatory | Stock: bracket (entry+stop[+target]) placed atomically; entry whose stop fails to place is immediately closed. Options: defined-risk structure + per-run synthetic OCO + single-leg broker stop **re-placed every morning by supervise (Alpaca option stops are DAY-TIF; the ~9:30–9:40 window before supervise is a known, priced-in stopless gap)**. Invariant: **at most ONE resting broker order per option position** (the stop; profit target is synthetic) — cancel → confirm-no-fill-in-flight → replace sequencing, race-tested |
| R7 | Daily loss breaker | −3% equity → no new entries this session (auto-clears next clean session) |
| R8 | Drawdown breaker | −8% from HWM → half size; −12% → paper-only halt + owner notification (owner-only reset) |
| R9 | Ticker cooldown after stop-out | 5 trading days |
| R10 | Consecutive-loss cooldown | 3 losing days → half size 5 days |
| R11 | Earnings blackout | No new stock swing / long premium ≤5 days pre-report (S2 post-report exempt by design); calendar is a blocking data dependency — stale calendar = no new entries |
| R12 | Option expiry & DTE hygiene | Enter 30–60 DTE; force-close longs ≤10 DTE; shorts ≤21 DTE if ITM-risk; **no swing option position survives the morning supervise run on its expiry date** (supervise is the enforcing run; the afternoon trade run is backstop-close-only since it lands after Alpaca's 15:30 ET opening-order cutoff). Forced closes use an escalation ladder: limit at mid → walk toward far touch → **marketable limit crossing the spread (the sole exemption to "market forbidden"), poll-until-filled**; residual failures use Alpaca's exercise/DNE instruction API and page the owner. Spreads closed as spreads, never legged out; ex-div ITM short calls closed immediately; early-close days: all enforcement in the morning run |
| R13 | Liquidity floor | Stock ADV>1M sh, price>$5; option OI≥500, day volume≥100, spread ≤10% of mid |
| R14 | Order types | Stocks: limit entries, resting stop exits, brackets. Options: limit at mid ± bounded walk (R12 ladder excepted); DAY TIF, RTH only |
| R15 | Price sanity | Reject if limit deviates >1% from live quote or quote stale >5min |
| R16 | Same-day round trips | Forbidden except broker-stop triggers (design rule, independent of PDT repeal) |
| R17 | Full audit | Every decision incl. "no trade" → append-only: setup ID, checklist values, sizing math (nominal AND realized risk), quote snapshot, minutes-to-close, rationale, guard evals, fills vs mid (slippage) |
| R18 | Watchdog | **Out-of-band**: an independent launchd timer (not an ai-server job) checks for a completed run every market day + the external heartbeat worker pattern; no run in 26h → owner alert. Broker-side stock stops make loop-death survivable; options are why the watchdog is not optional |
| R19 | Gross exposure | ≤1.0× equity; margin-call = P0 auto-cure at next run |
| R20 | **Early assignment doctrine** | Assignment on a known short leg (matched via OCC symbol + ledgered structure link) is an **expected lifecycle event, never a reconcile-break**: `--manage` auto-cures same-run (cover involuntary short stock / dispose assigned stock or exercise the paired long / close the orphan leg), P0 owner notification, property-tested for both short-call (involuntary short stock) and short-put cases |
| R21 | **Corporate actions & trading halts** | Detect halted/CA-affected symbols before any order action → mark position `unmanageable` + owner notification instead of retry-burning the ≤5 cancel/replace conduct budget; **re-place stops after detected order-cancellation events (splits cancel open orders)**; split/symbol-change/delisting cases in the reconciler test matrix |

Sizing method: R1 is a **ceiling, not a sizing method** — size from risk-per-trade (`shares = (equity×R)/(k×ATR)`), then clip by R1/R19. Kelly used only as a governor concept (quarter-Kelly ≈ the 1–3%×2–4-position band); no live Kelly formula until the audit log holds ≥100 trades.

---

## 7. Bot 2 — `value/`: medium/long-term value + cash-secured puts

**Mandate:** own good companies at fair prices; get paid to wait via CSPs when premium is rich; hold winners long (LTCG-aware). Weekly decisions, monthly full re-rank, positions touched only on triggers. Weekly *review*, never weekly *churn*.

### 7.1 Screening pipeline (deterministic; every number fetched + logged, never from model memory)

Universe: US common stocks from the §4 static universe, mkt cap ≥$1B, optionable with penny-class liquidity, ex-financials/REITs/utilities (EV/EBIT meaningless there), ex-trader-allowlist → screened weekly.

1. **Hard rejects:** Piotroski F-score ≤6; net debt/EBITDA >3; interest coverage <3; accruals/earnings-quality — **CFO < 0.8× net income applies only when NI>0; for NI≤0 use scaled accruals ((NI−CFO)/total assets above threshold)**; unavoidable earnings inside the CSP window with no long case; OI/spread fails.
2. **Rank:** equal-weighted composite of FCF yield + EV/EBIT earnings yield + ROIC. **Drop the cheapest decile of the composite** (value-trap zone — re-tests show the extreme-cheap ranks underperform). Keep top ~40.
3. **Overlay tags (never hard rejects):** consensus-delta sign (§4 — ABSENT during warm-up), IV rank (or proxy), distance-to-support/52w range position, days-to-earnings, GARP flag (PEG<1.5 & 3yr EPS growth). Output: ranked ~25-name watchlist persisted as the week's auditable decision file.

Data: EDGAR companyfacts/frames via the existing atlas_dash ingestion (extended), Finnhub calendar, Alpaca chains/IV, self-built consensus-delta. Beat-and-raise names get long-entry priority; misses quarantine 2 weeks; strongly negative consensus-delta (once measurable) vetoes new entries.

### 7.2 CSP mechanics (code-enforced parameter table)

30–45 DTE; delta 0.20–0.30 (default 0.25); strike ≤ min(delta-band strike, support, happy-to-own price); **IV gate: IVR ≥30 (prefer ≥40), or the §4 launch proxy with its widened thresholds and `ivr_proxy` ledger tag**; GTC buyback at 50% of premium placed at open (plain option limits may be GTC on Alpaca; stop types may not); close/roll at 21 DTE; rolls only for net credit with thesis intact, max 2, then accept assignment; **never hold a short put through earnings** (expiry must precede the next report — blocking calendar check); OI ≥500, spread ≤10% of mid; collateral reserved = strike×100×contracts, counted against the caps below.

Assignment is a **planned outcome**: effective basis = strike − cumulative premium (per-name premium ledger, auditable). Post-assignment default: hold as long value position. Wheel (covered calls ≥ basis+5%, ≤0.30Δ, same DTE/profit/earnings rules) **only while the name still passes Stage-1 screens** — thesis-break = exit stock, never farm premium on a deteriorating name.

### 7.3 Decision tree (per watchlist name, weekly — the LLM operates only inside this tree)

```
held?                    → lifecycle rules only
breaker (SPY<200dma AND VIX>30)? → no new CSPs; longs only in ≤2% slugs
earnings inside window?  → strong long case (top-10 + positive consensus-delta) → half-slug LONG, else PASS
IV gate rich (IVR≥40 / proxy) and price 0–10% above target entry → SELL CSP (params §7.2)
IV gate thin (IVR<20 / proxy), or top-decile rank + strongly positive consensus-delta → BUY LONG (5% slug)
price at/below target and IV middling → BUY LONG (don't wait for a fill that may never come)
else → PASS (stay on watchlist)
```

### 7.4 Portfolio caps (kernel-enforced; exhaustive — value's own table, self-contained)

The owner's 50%-per-trade ceiling is inherited as a value rule too (CSP collateral counted), though the caps below dominate in practice. Single name (stock value + CSP collateral combined) ≤8% at open, hard 10% after drift; sector ≤25% (value screens pile into distressed sectors — the mandate's top structural risk); total CSP collateral ≤40% of equity; cash buffer ≥10%; **12–18 positions** at ~5% slugs (18×5% + 10% cash is arithmetically satisfiable; 20 was not); skip CSP where one contract's collateral exceeds the name cap (buy stock instead — see O-2's funding arithmetic); no leverage, no shorting, no naked anything. Exits: composite rank falls below ~top-60% (thesis complete), Stage-1 reject fires (thesis broke — exit regardless of P&L), or drift-cap trim. LTCG awareness: discretionary exits at 300–365 days held surface "LTCG in N days" and prefer deferral (stops/thesis-breaks override). Early assignment on any short put is processed by `--manage` under the same R20 doctrine (expected event, auto-book at effective basis, owner notified).

---

## 8. Shared compliance & guard layer (`trading_shared` schema + `tradingcore/guards.py`)

Derived from FINRA's 2026 AI-agent oversight expectations, adopted voluntarily (single-tenant system; owner is liable for every order; "the LLM decided" is not a defense):

- **Order-path exclusivity (DR-0):** the executor is the ONLY order path. **No broker MCP tools, no direct broker API calls, in any trading skill** — written into every skill body and CLAUDE.md. Because the decision agents necessarily hold workspace `.env` broker keys, this is backstopped by a **detective control**: any broker order lacking a matching ledgered decision row (DR-21) → immediate kill switch + owner P0, tested in the reconciler matrix. Server-side per-skill env scoping (denying keys to research/evaluate skills) is a P5 hardening item — it touches `src/runner/` delivery plumbing and is worth an owner conversation.
- **Wash-sale registry (DR-12):** rolling 61-day per-symbol realized-loss registry shared by swing + value (substantially-identical set includes the underlying's options). **Default: config B — tag `wash_sale_risk` on re-entry and surface in weekly reports** (a wash sale defers the loss into basis; it does not destroy it — hard-blocking re-entry for 31 days would fight the swing cadence and the §11 evidence bar for no tax benefit in a paper account). Hard blocking (config A) is reserved for a live-money taxable year-end window, owner-flipped. **Trader-side coverage is detect-and-report only** (frozen trader/ consults nothing) — made sound by the §5.1 universe partition; the weekly report also carries the standing cross-account caveat (owner's IRA/401k invisible to the bots).
- **Cross-bot symbol lock (DR-17):** no two *new* verticals may simultaneously hold working orders on opposite sides of one symbol (self-trade/wash-print prevention); trader/ is outside the lock, made moot by the universe partition. Conduct rules: cancel/replace ≤5 per order (R12's ladder budgeted within it), no orders in the last 10 min intended to affect the close.
- **Kill switch (DR-20):** one action halts both bots and cancels all working orders. Its physical trigger paths, in order of survivability: (1) owner Telegram command → runner job; (2) a `halts` row inserted via psql; (3) **layer zero, works with the entire server dead: Alpaca dashboard `suspend_trade=true` / key revocation — written into both GO_LIVE docs**. Automatic breakers per bot (§6.2 R7/R8; §7.3 breaker); N consecutive kernel rejections → halt (the model is confused); broker error-rate spike → halt. The R18 watchdog is out-of-band (independent launchd timer + external heartbeat), because the 08-17 governor-dark incident proved the scheduler can't watchdog itself.
- **After-tax reporting (DR-14):** P&L shown pre-tax AND after-tax-estimate (swing at ordinary rate, value's >365d lots at LTCG) — otherwise the aggressive bot flatters itself by ~1.27× at a 32% bracket.
- **Ledger invariant (DR-21):** every fill carries lot detail (symbol, side, qty, price, fees, UTC ts, order id, strategy id, decision id) in append-only storage, CSV-exportable for 1099-B reconciliation; ledger write and order submission are atomic.
- **Decision provenance (DR-19):** every trade decision persists inputs-snapshot reference, model + prompt version, stated rationale, per-rule guard evaluations, and order lifecycle.

**Per-bot DB schemas** (`swing.*`, `value.*` — following the momo→k401→trader separate-schema precedent, psql-stdin bound-vars technique): `runs` (status enum incl. halts + `off_window`, git_sha, config_hash, equity, cash, details), `orders` (unique client_order_id with per-bot prefix `aswg-`/`aval-`, options fields: occ_symbol, type, strike, expiry, multiplier, premium), `positions_lots` (open lots with entry, stop, target, structure links — an active book needs first-class lots, not jsonb snapshots), `decisions` (DR-19 provenance incl. "no trade"), `equity_curve` (day PK with frozen `spy_close`, `bil_close`), `strategy_state` (stage CHECK-constrained to candidate|validated|paper — **schema refuses live**), `halts`. Value adds `csp_lifecycle` (open→50%-take/expire/roll/assign chains, per-name premium ledger) and `screen_snapshots`. Shared schema adds `iv_snapshots`, wash registry, symbol locks, account registry (and, under O-2(b), virtual capital partitions).

---

## 9. Dashboard (atlas web, behind existing Cloudflare Access)

New pages in the existing Next.js 15 app (no new port/subdomain/Access policy; pattern: `/momentum/page.tsx`'s ledger-honesty style + `web/lib/atlas/*-queries.ts`):

- **`/trading`** — all-verticals overview: per-bot equity curves vs SPY & BIL (frozen pair), breaker/halt states at a glance, last-run liveness per worker (the governor-dark lesson made visible), pending owner DECISION-REQUESTs, warm-up status of the IVR and consensus-delta signals.
- **`/trading/swing`** — equity + drawdown vs benchmarks; open positions with live stop levels and DTE clocks; trade blotter with per-fill slippage vs quoted mid and minutes-to-close; setup-level performance table (S1–S5: N, win rate, realized expectancy in R, avg slippage — governor-computed, the evidence that feeds demotions and the live-money decision); decision journal (rationale + guard evals, incl. logged no-trades); risk panel (heat, premium-at-risk, cooldowns, wash-risk tags).
- **`/trading/value`** — watchlist with screen tags and week-over-week rank moves; CSP lifecycle board (open shorts w/ DTE, 50%-target distance, earnings-date guard status); assignment history with effective-basis ledger; wheel status; sector-exposure vs 25% cap; regime-annotated performance vs the §10 rubric; after-tax P&L estimate.

All numbers rendered from DB rows/ledger artifacts only (nothing hand-maintained); charts follow the dataviz skill when built. Telegram remains the push channel (per-run summary paragraphs; Friday equity-vs-SPY/BIL; owner-attention-now escalations).

---

## 10. Evaluation & expectation contracts (written into YAML headers, cards, and GO_LIVE §0 — the honesty anchor)

**Swing:** year-1 SUCCESS = survival with complete audit trail, zero kernel breaches, Sharpe > 0 net of costs; STRONG = beat SPY risk-adjusted. Judged on ≥6 months / ≥100 trades, never a hot month (LLM-agent literature: short-window outperformance common, long-window rare). **Paper-fill honesty:** Alpaca paper fills limit orders on touch with no queue or adverse selection, which flatters exactly S1-style limit entries — a paper limit fill counts as valid evidence only if price traded through the limit by ≥1 tick (computable from stored bars); the haircut is stated in GO_LIVE §0. **Setup kill rule:** any setup whose live slippage exceeds 30% of its edge is killed — where "edge" is **governor-computed trailing realized paper expectancy from DB rows** (below an N-minimum the setup is "unproven," not "safe"); **no researcher-declared number ever enters demotion math**. Overtrading is a first-class failure: "no valid setup → no trade" is a logged success.

**Value:** process compliance dominates and is pass/fail (no earnings-straddling shorts, no cap breaches, no debit rolls, every trade has thesis + screen snapshot). Returns judged **regime-annotated**: the CSP sleeve is expected to lag melt-ups — historically by ~8–10pp annualized in typical bull years and **~18pp in the worst documented case (PUT vs SPY, 2019)** — and must win flat/down tapes. The vol test is conditional: **when CSP collateral ≥~25% of the book**, portfolio vol < SPY vol or the mechanics are broken; in low-IV regimes the §7.3 tree legitimately builds a concentrated stock book that may exceed SPY vol with nothing broken. CSP metrics: win rate ≥75%, premium retention ≥50%, assignment-recovery ≥60% above basis within 90 days. 6–12 months evaluates process; outcome verdicts need longer.

Both governors: grade from DB rows only vs the frozen SPY+BIL pair; deterministic demotions (compute, don't deliberate) using only governor-computed inputs; promotions candidate→validated→paper only; kernel/limit changes are owner DECISION-REQUESTs, never governor actions; quarterly integrity cadence (decoy round, no-lessons baseline) copied from trader/momo practice. Every candidate ever evaluated lands in `trials.jsonl` pre-verdict (Deflated-Sharpe denominator); backtests use free daily data with costs modeled and walk-forward/purged CV; **LLM-signal candidates: historical backtests inadmissible** (post-cutoff paper evidence + ticker-anonymization probes only — the model has memorized history).

---

## 11. GO_LIVE (per bot, owner-only — copied pattern, not referenced)

No live code path exists in v1 (grep-enforced per bot: `test_paper_only.py`). Ignition sequence per bot: (0) honest-expectations gate written in the bot's GO_LIVE §0, including the paper-fill haircut and §10 contracts; (1) evidence preconditions the governor must show in writing — swing: ≥60 sessions, **≥100 haircut-valid trades** (matching §10's own evidence standard), positive realized expectancy, 4 consecutive weekly PASS, zero kernel breaches ever; value: ≥90 days, a CSP-lifecycle count scaled at P0 to the funded universe (O-2 arithmetic) incl. ≥1 correctly-handled assignment, 4 consecutive PASS, zero breaches; (2) owner hand-edits the bot's CLAUDE.md rule 1, approves a reviewed diff adding live host + `live_enabled` + `max_live_equity_usd` + live stages + live-guard test suite; (3) live keys under NEW names, `max_options_trading_level` clamps (O-4), `suspend_trade=true` until first reconciled run, Crypto Wallets never enabled; (4) canary ladder: ≤2% of capital (or ≤$2k) → 10% → 25% hard ceiling, each step a fresh owner edit after ≥20/40 clean days; automatic code-side demotions on DD >1.5× paper evidence, two daily-breaker trips in 10 sessions, or rolling 60-day Sharpe <0. Layer-zero controls (broker dashboard suspend, key revocation) are documented in GO_LIVE as working with the entire server dead.

---

## 12. Implementation plan (phased; each phase independently deployable and gated)

Standard gates every phase: atlas pytest green (path-conditional in atlas-redeploy — new blocks for `tradingcore/`, `swing/`, `value/`), ai-server pytest + `lint_docs` green, code-review subagent LGTM (INV-13), secrets grep, CHANGELOG/registry/INDEX updates, byte-identical skill staging, `seed-schedules.sh` as sole schedule writer, deploy via push→`/task deploy server` + `/task redeploy atlas`.

| Phase | Contents | Est. |
|---|---|---|
| **P0 — Owner** | Decisions O-1…O-6 (incl. O-2 funding arithmetic and the O-3i warm-up shortcut); provision paper account keys into atlas `.env` under new names (`ALPACA_SWING_*`, `ALPACA_VALUE_*` — flows automatically via existing `delivery.env_files`); set paper starting equities; clamp paper options levels (O-4) | owner, ~30 min |
| **P1 — Shared layer** | `tradingcore` package: options-capable Alpaca client (chains/greeks/snapshots, single-leg + `mleg` orders, brackets, stop types, exercise/DNE), Black-Scholes recompute, synthetic-OCO engine (single-resting-order invariant + race sequencing), NYSE calendar **with early-close days**, per-key rate budget, guard primitives, **iv_snapshots collector (starts accumulating on deploy — the §4 warm-up clock starts here)**, static universe builder; migration 0043; atlas-redeploy gate blocks; property tests for every guard | 1–2 build sessions |
| **P2 — Swing vertical** | `swing/` package (kernel R1–R21 with property tests incl. candidate-bounds monotonicity, signals S1–S5, screener with per-field bounds emission, executor `--manage/--screen/--submit`, ledgerlink), migration 0044, CLAUDE.md + GO_LIVE.md + PROTOCOL/LEDGER seeds, tripwire tests (paper-only, adoption-gate, deny-list greps), 4 skills + dual-row DST schedules + registries; out-of-band watchdog timer; first supervised paper runs | 2–3 sessions |
| **P3 — Value vertical** | `value/` package (screen pipeline extending atlas_dash EDGAR/earnings ingestion, F-score/accruals/coverage calculators with the NI≤0 branch, consensus-delta snapshotter, CSP lifecycle + R20 assignment processing + wheel, kernel, executor), migration 0045, docs/contracts, 4 skills + schedules; first supervised runs | 2–3 sessions |
| **P4 — Dashboard** | `/trading`, `/trading/swing`, `/trading/value` pages + query libs; npm build gate | 1–2 sessions |
| **P5 — Learning loops + hardening** | Research skills' first governed cycles; governors' first grades; decoy/integrity cadence armed; evals registered in `evals/cases/`; owner conversation on per-skill env scoping (DR-0 hardening) | 1 session + steady state |

Build order rationale: P2 before P3 per owner emphasis; they share only P1, so P3 can proceed in parallel if desired. Every phase ends with observable outcomes (P1: tests green + schema live + IV collector running; P2/P3: first paper run rows in DB + Telegram report received; P4: pages render from real rows; P5: first GRADE ledger entries).

**Testing strategy:** kernel and guards get exhaustive unit/property tests (every R-rule and DR-rule has a test proving the kernel rejects a violating intent, including intents looser than candidate bounds); executor pipeline tested against a stub broker with canned fixtures — assignment (short-call → involuntary short stock; short-put), expiry-day ladder incl. unfilled-close escalation, partial fills of multi-leg spreads, splits/symbol-changes/halts (R21), order-cancellation-on-split, 429s, margin rejections, the synthetic-OCO cancel/replace race; tripwire tests copied per vertical; reconciler tested for the full cross-account/foreign-order matrix per O-2's outcome; failure-path tests for every ERROR/ABSENT/UNMEASURABLE branch (momentum-lab's lesson class), including VIX-stale fail-closed behavior.

## 13. Top risks (beyond the per-bot failure-mode tables)

1. **Cross-vertical interference** — resolved by decision O-2 + the §5.1 universe partition; tested in P1/P2.
2. **Options exit latency** — synthetic stops have cron granularity; DAY-TIF option stops leave a ~10-min morning gap before supervise re-places them, and gaps between runs can jump synthetic levels. Mitigated structurally (defined-risk spreads cap loss at entry), honestly (expectation contract prices it in), and by the R12 ladder. If paper evidence shows it's costly, that evidence justifies an intraday watchdog service (portless atlas `services:` entry) or moving options execution to Tradier's broker-resident OTOCO.
3. **Data-quality on free tier** — IEX-only prints, indicative options quotes, and two warm-up signals (IVR, consensus-delta). Mitigated by liquidity floors, limit-only orders, proxy tagging, slippage grading; the O-3 upgrades are decided on ledger evidence.
4. **LLM decision drift** — bounded by candidates-only input, kernel-enforced per-field bounds, cooldowns, governor process grading, quarterly decoys; backstopped by DR-0's detective control.
5. **Silent worker death** — liveness is a first-class governor check + dashboard panel + out-of-band R18 watchdog (the 08-17 governor-dark incident made this a named class).

## 14. Out of scope (explicit)

Live money (owner-gated per §11); shorting stock (involuntary R20 shorts are auto-cured, never held); naked options; futures/crypto; intraday/ORB strategies; Robinhood/Schwab/Fidelity integrations; §475(f) automation; any change to `trader/` v1 beyond the GOTCHAS cross-note (and, under O-2(b) only, the enumerated reconciler amendment); paid data without an O-3 decision; modifying protected paths (MISSION §M list).
