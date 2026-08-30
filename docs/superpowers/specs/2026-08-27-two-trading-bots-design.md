# Two Autonomous Trading Bots — Design & Implementation Plan

**Date:** 2026-08-27 · **v2: 2026-08-30** · **Status:** ACCEPTED-DIRECTION — owner decisions of 2026-08-30 incorporated; build starts at P0/P1. Nothing implemented yet.
**Owner request:** (1) a short-term aggressive stock/options trading account driven by technicals and recurring patterns, high risk tolerance, no trade >50% of account value, mandatory stops/safeguards, every trade tracked and audited; (2) a medium/long-term account using earnings and financial fundamentals to buy good companies at low valuations — via short puts, outright longs, or long holds. Plus workflows, agents, and a dashboard, and a broker recommendation.

**Owner decisions 2026-08-30 (supersede parts of v1):**
1. **Two different brokerages.** Bot 1 → **Tradier** (live, Pro). Bot 2 → **tastytrade** (live, margin). Robinhood evaluated at owner request and excluded for now (§3 postscript). Alpaca fell out of the execution role when decision 3 landed (it cannot do margin-secured puts at any level) — it remains a data source only.
2. **Real money from day 1** at reduced size — the paper-first constitution is replaced by: **~2-week sandbox shakedown (plumbing only, mechanical exit criteria) → owner funds small → canary scale ladder gated by audit/governor evidence.** Evidence bars now gate *size*, not *live-at-all*.
3. **No cash-secured puts.** Bot 2 sells **margin-secured short puts** (owner's term: "shares-secured" — the portfolio's margin capacity backs the puts instead of idle cash; brokers classify these as naked/uncovered). The kernel keeps them economically covered: caps are computed on **assignment obligation** (strike notional), never on the smaller margin requirement, plus an assignment-stress rule (§7.2).

**Evidence base:** 9-agent research sweep 2026-08-27 + 3-critic adversarial review (33 findings incorporated) + 3-agent Robinhood/second-broker re-verify 2026-08-30 + 2-agent margin-secured-put verification 2026-08-30 (all reports in the session archive; key claims source-linked in the research files).

---

## 0. Summary

Build two new **atlas verticals** — `swing/` (Bot 1) and `value/` (Bot 2) — cloned from the architecture the shipped `trader/` vertical proved: deterministic model-free Python executes and enforces risk; Claude agents supervise, decide within hard rule bounds, research, and grade; everything lands in append-only Postgres + ledger audit trails.

**Live-money posture:** both bots trade real money at owner-set reduced size after the shakedown. What protects the money from day 1 is everything the design already had: the risk kernel, daily-loss/drawdown breakers, out-of-band watchdog, kill switch with a layer-zero broker-side path, and the append-only audit trail — which now grades **real fills** (better evidence than optimistic paper fills). What the owner's "prove it to me" gate controls is the **scale ladder**: every size step-up requires governor evidence in writing; demotions on drawdown are automatic.

**Brokers:** Bot 1 → **Tradier** (broker-resident OCO/OTOCO on options — exits rest at the broker between cron runs; never-expiring tokens; $0 option contracts on Pro). Bot 2 → **tastytrade** (margin-secured short puts at the Basic level; per-order margin dry-run endpoint; $1-open/$0-close premium-selling fees; free real-time DXLink greeks; non-expiring OAuth refresh tokens). **Dashboard:** new pages inside the existing atlas Next.js app behind Cloudflare Access.

The doctrinal line from v1 stands: the LLM is allowed inside the decision loop but only between a deterministic screener (candidates with machine-readable per-field bounds) and a deterministic risk kernel that rejects any intent looser than its candidate's bounds. **"LLM proposes, kernel disposes"** — with a detective control for the non-cooperative case (§8).

---

## 1. Decisions — resolved and open

**Resolved (owner, 2026-08-30):** O-1 constitutional divergence **approved** (Bot 1 runs as a separate aggressive vertical with the §10 honesty contract). O-2 superseded — separate live accounts at separate brokers; the v1 cross-account reconciler problem disappears by construction; trader v1's Alpaca paper account untouched. Live posture: **real money day 1** post-shakedown, ladder-gated. Put mechanism: **margin-secured, not cash-secured**. O-5 stdlib+pyyaml stands (both brokers are raw-REST-friendly; tastytrade's archived official Python SDK is irrelevant to us).

**Open — the P0 owner actions:**

| # | Action | Notes |
|---|---|---|
| P0-A | **Tradier** (Bot 1): open brokerage account + **Pro** ($10/mo) + margin + options approval **Level 3** (verticals/credit spreads); generate API token (never expires) + sandbox token | Real-time stock+options data with ORATS greeks free with the account. Level 4 (naked puts, $10k min) NOT needed for Bot 1 |
| P0-B | **tastytrade** (Bot 2): open **margin** account (≥$2k Reg-T; realistically the P0-C amount) + **Basic** trading level with uncovered-put permission (suitability questionnaire; Basic suffices — "The Works" only adds naked calls/futures/PM); create OAuth2 personal grant (scopes `read`,`trade`) → client id/secret + **refresh token** (never expires) into atlas `.env` | Orders exceeding the account's level are rejected by tastytrade's own preflight — a second net under our kernel |
| P0-C | **Funding amounts** (wired only after shakedown exit criteria pass). Floors: swing works from ~$10k (better $25k+ for concurrency under heat caps). Value: the 8% name cap applies to **assignment obligation**, so ~$25k+ still recommended for a diversified put book — margin-securing doesn't raise how much obligation fits, it frees the cash to sit in the long book instead of idle | Owner also hand-sets each bot's initial `max_live_equity_usd` at funding |
| P0-D | **Tax params** (real taxable events day 1): marginal ordinary rate + NIIT flag + LTCG rate into `config/settings.yaml`; confirm §475(f) NOT elected | |
| P0-E | Optional: one-time ~$29 (one month Polygon/Massive Options Starter) to backfill IV history and skip the ~60-session IV-rank warm-up | Cheaper urgency than v1: both brokers now stream usable IV (Tradier ORATS, tastytrade DXLink), so the warm-up only gates the IV-*rank* percentile, not IV itself |

---

## 2. Approaches considered

(1) Extend `trader/` — rejected: its constitution excludes short-horizon trading and its risk-officer auto-denies aggressive wiring. (2) **Two new atlas verticals cloned from the trader/ pattern — chosen.** (3) New standalone project — rejected: pure overhead.

LLM-role spectrum: fully deterministic (trader v1) → **LLM-proposes-kernel-disposes (chosen)** → LLM free-form trading (rejected; live-benchmark literature + momentum-lab ADR-004 / Profit Mirage evidence stand).

Live-posture spectrum: months-of-paper-then-live (v1) → **shakedown-then-live-small-with-evidence-gated-scaling (chosen, owner decision)** → fund-with-no-shakedown (rejected: a plumbing bug's first victim would be real money; two weeks of free sandbox validation is the cheapest insurance in the plan).

Short-put collateral spectrum: cash-secured (v1 — owner rejected: idle-cash drag) → **margin-secured with obligation-based caps + assignment-stress rule (chosen)** → margin-secured with requirement-based caps (rejected: that is how put sellers blow up — sizing to the 20% margin instead of the 100% obligation is 5× hidden leverage).

---

## 3. Brokers: Tradier (Bot 1) + tastytrade (Bot 2)

Nine brokers evaluated 08-27; re-verified 08-30 under the two-brokerage constraint and again under the margin-secured-put requirement.

- **Tradier — Bot 1's home.** Decisive: **broker-resident OCO/OTO/OTOCO on stocks AND options** — entry + take-profit + stop-loss rest at the broker in one payload, so positions stay protected between cron runs. Personal API tokens **never expire**; full REST incl. multileg (≤4 legs) with a **preview endpoint** (`preview=true` returns `margin_change`, order cost, warnings — a pre-trade guard hook). **Pro $10/mo = $0 stock and $0 equity-option contracts**; real-time NBBO-quality data with ORATS greeks/IV free with the account. Weaknesses: sandbox is 15-min delayed with simplistic fills (fine — shakedown is plumbing-only); Tradier runs a **risk-based expiry auto-close** (may force-flat short options near expiration if buying power can't cover assignment; wants customers flat by 3:30 PM ET on expiry day) — our R12 morning enforcement already gets there first, but the policy is coded around explicitly.
- **tastytrade — Bot 2's home.** The margin-secured-put verification (2026-08-30) scored it PASS on every load-bearing item: naked/margin-secured short equity puts at **Basic** level in a margin account (Reg-T greater-of(20%·underlying − OTM + premium, 10%·strike + premium) — e.g. ~$990 against a $50 strike vs $5,000 cash-secured); **per-order margin dry-run** (`POST /accounts/{n}/orders/dry-run` → buying-power effect; `POST /margin/accounts/{n}/dry-run` → deep impact) so the kernel gates on broker-computed numbers, not our approximation; OAuth2 personal grants whose **refresh tokens never expire** (15-min access tokens, headless-friendly); GTC buyback orders + OCO/OTOCO complex orders; **$1/contract open, $0 close, $10/leg cap**, ~$0.15/contract pass-throughs, $5 assignment fee, no data fees — the best premium-selling economics surveyed; free real-time **DXLink** quotes + greeks streaming for funded customers; ToS whose Permitted Purpose **explicitly includes "algorithmic trading systems."** Weaknesses, designed around in §7/§11: **no assignment push event** (poll `Receive Deliver` transactions + positions pre-market and post-market — an R20 doctrine variant); cert sandbox has fake fills ($1 market fills; limits >$3 never fill) so it validates auth/order-lifecycle/streamer/reconciliation only; margin loan 8–11% if assignment creates a debit (the assignment-stress rule bounds this); broker may raise per-symbol margin discretionarily (dry-run before every submit, never cache requirements).
- **Alternatives if either is rejected:** all-Tradier (Bot 2 in a second Tradier account at **Level 4**, $10k min — one login/token for both bots, per-account API scoping but no credential isolation; contradicts the owner's two-brokerage preference); TradeStation (Level 4 naked puts + SIM env, heavier onboarding); IBKR (Standard permissions + best margin engine, but gateway babysitting disqualifies unattended cron). **Alpaca cannot host Bot 2 at any level** — it hard-blocks uncovered short options (`"account not eligible to trade uncovered option contracts"`); short puts there are always fully cash-collateralized, which is exactly what the owner declined. Alpaca stays in the stack as a data source (free IEX bars/history for benchmarks and swing signals) and as trader v1's untouched paper venue.

**Two-broker operational deltas (accepted knowingly):** two adapters behind one interface with a capability matrix (Tradier: form-encoded REST, OTOCO, preview; tastytrade: JSON REST, dry-run, complex orders, DXLink streamer); two reconciliation domains, two credential sets, two 1099s; cross-bot symbol-lock and wash-sale guards are app-level via the shared DB (no broker backstop — unchanged from v1's design); fee normalization ($10/mo Pro vs per-contract) in P&L ledgers.

### Postscript: Robinhood (evaluated at owner request, 2026-08-30)

The owner's belief was **correct**: Robinhood launched official **Agentic Trading** on 2026-05-27 — a first-party MCP server through which AI agents trade a dedicated, ring-fenced, separately-funded "agentic account." Fees are excellent ($0/$0, ~$0.04/contract pass-throughs). Excluded because the blockers are functional, not financial: **agent orders are long-only** (no short legs → no short puts, no credit spreads — both bots' option mechanics excluded); options are an eligibility-gated beta with no documented resting stop/OCO types; there is **no REST path** — the LLM session *is* the only sanctioned order path (collides with the LLM-never-places-orders rule) with undocumented headless token life; no simulated mode; only one margin account per customer; nothing published supports multiple agentic bot accounts. **Future option, separate decision:** a small long-only stock sleeve in an agentic account — genuinely the best blast-radius container in retail brokerage. Caution: `cortex-robinhood.com` is an unaffiliated impersonation domain; Robinhood Cortex is an in-app assistant with no API.

---

## 4. Data: $0 recurring stack (with declared warm-ups)

| Need | Primary ($0) | Fallback ($0) | Paid path |
|---|---|---|---|
| Bot 1 quotes/bars/chains/greeks | **Tradier account data** (real-time NBBO-quality; ORATS greeks/IV on chains — refresh coarse, recompute locally at decision time) | Alpaca IEX feed (provisioned) | — |
| Bot 2 quotes/chains/greeks | **tastytrade DXLink streamer** (real-time Quote/Trade/Greeks/Candle events, free for funded customers, 24h quote tokens) | Tradier chains | — |
| Benchmarks + daily history (both) | Alpaca REST (2016+, free; SPY/BIL closes frozen into equity curves) | yfinance (research only, never in the decision path) | — |
| **IV rank** (gates S4/S5 + all short puts) | **Self-accumulated:** daily `iv_snapshots` collector (Tradier chains for swing universe, DXLink for value universe) from P1 deploy; IVR computed once ≥60 sessions exist; until then the declared proxy (IV/HV20, widened thresholds), decisions tagged `ivr_proxy` | — | P0-E ($29 one-time) ends the warm-up |
| VIX (regime gates) | FRED `VIXCLS` (EOD) | Cboe delayed CSV | — |
| Fundamentals (Bot 2) | SEC EDGAR companyfacts + frames (extend the existing atlas_dash ingestion — do not duplicate) | FMP free, Finnhub basics | Finviz Elite $299.50/yr |
| Earnings calendar (blocking dependency) | Finnhub `/calendar/earnings` | Alpha Vantage CSV; FMP | — |
| Estimate-revision signal (Bot 2 overlay) | Self-built consensus-delta (weekly snapshots diffed over 4 wks); ABSENT during warm-up; **overlay tag, never a hard reject** | — | I/B/E/S-class data if warranted |
| Candidate universe & screening | Static versioned universe (S&P 500 + top-ADV optionable ETFs, monthly config commit); screens computed from broker bars + EDGAR in stdlib | `tradingview-screener` / `finvizfinance` — research-only | Finviz Elite |

Hard data rules unchanged from v1: limit orders only; every decision logs the quote snapshot it acted on; scraper-class sources behind circuit breakers; rate budgets per broker (Tradier ~60–120 req/min per category; tastytrade throttles per ToS — budget conservatively and back off on 429; Alpaca 200 req/min); ERROR / ABSENT / UNMEASURABLE distinct on every path; stale regime data fails closed for new risk-adding entries but never blocks lifecycle management. DXLink/streamer connections are conveniences, not dependencies — every decision path must complete on REST polling alone (cron sessions can't hold sockets between runs).

---

## 5. Architecture

### 5.1 Repo layout (atlas repo, mirroring `trader/`)

```
atlas/
  tradingcore/            # NEW shared lib (stdlib+pyyaml), used by swing/ and value/ ONLY
    tradingcore/          #   broker.py (adapter interface + capability matrix),
                          #   tradier.py (form-encoded REST: OTOCO, multileg, preview=true),
                          #   tasty.py (JSON REST: OAuth2 refresh flow, orders + dry-run,
                          #     complex orders, transactions/Receive-Deliver polling),
                          #   alpaca_data.py (bars/history only — no order surface),
                          #   http retry, NYSE calendar (incl. early-close days), black_scholes,
                          #   synthetic_oco (backstop), guards (DR primitives), per-broker rate
                          #   budgets, iv_snapshots collector, universe builder
    tests/
  swing/                  # Bot 1 vertical (Tradier): CLAUDE.md (rule 1: live cap), LADDER.md,
                          #   config/ (owner-owned limits.yaml incl. max_live_equity_usd,
                          #   versioned strategies/), swing/ (signals S1–S5, screener, risk.py,
                          #   executor, ledgerlink), evaluation/, tests/ (live-guard tripwires)
  value/                  # Bot 2 vertical (tastytrade), same shape (screen.py, puts.py
                          #   margin-secured lifecycle, wheel, risk.py, executor, ledgerlink)
  db/migrations/          # 0043_trading_shared · 0044_swing · 0045_value
  web/app/trading/        # dashboard pages (§9)
```

`trader/` v1 is **not modified** (one GOTCHAS cross-note only). `tradingcore` changes trigger both bots' suites in the atlas-redeploy path-conditional gate.

**Universe partition (kept from v1):** trader v1's allowlist symbols (SPY, VTI, EFA, AGG, SGOV, BIL) and their options stay excluded from both new bots (future-proofs a trader go-live; swing's index workhorses are QQQ/IWM). Benchmark *reads* of SPY/BIL are unaffected.

### 5.2 Agent topology (8 new ai-server skills — unchanged shape from v1)

Skills authored in atlas `integrations/ai-server/skills/`, staged byte-identical, seeded by `seed-schedules.sh`. Payload + workspace isolation for operational/research skills; the two evaluate skills follow the trader-evaluate posture (no payload, shared dev clone, stop on dirty tree). **DST handling:** dual month-gated UTC rows per ET-anchored slot + executor `off_window` guard from the broker clock; fills record minutes-to-close; early-close days shift all lifecycle enforcement to the morning run.

| Skill | Cadence (intended ET) | Model | Role |
|---|---|---|---|
| `atlas-swing-supervise` | weekdays ~09:40 | sonnet / med | Deterministic lifecycle: verify OTOCO groups resting at Tradier survived overnight/corporate actions, gap checks, synthetic-OCO backstop sweep, **expiry-day disposals (R12 enforcer)**, breaker state, buying-power check. Never places entries, never fixes code |
| `atlas-swing-trade` | weekdays ~15:45 | opus / med | Decision run: `--screen` emits candidates with per-field bounds → LLM selects/vetoes → `--submit` kernel-validates and places (preview-before-submit, OTOCO groups) → verify, report |
| `atlas-swing-research` | Fri 13:00 UTC (verified free; Mon 13:00 is taken) | opus / high | One governed hypothesis cycle; deny list incl. limits.yaml, risk.py, executor, `tradingcore/*`, live-guard tests — enforced by grep tripwires + code review |
| `atlas-swing-evaluate` | Sun 16:00 UTC | opus / high | Frozen governor: grades from DB rows vs frozen SPY+BIL, liveness sweep, deterministic demotions from governor-computed inputs, **ladder step-up evidence memos** (§11) |
| `atlas-value-manage` | weekdays 18:10 UTC | sonnet / med | Deterministic lifecycle: **assignment poll (Receive-Deliver transactions + positions — tastytrade has no push event)**, profit-target fills, 21-DTE checks, earnings re-verification per short put, obligation/stress-cap scan, breaker state |
| `atlas-value-decide` | Mon ~10:30 | opus / high | Weekly deep run: deterministic screen → watchlist → LLM applies §7.3 tree → kernel submit (dry-run-gated) |
| `atlas-value-research` | Tue 13:00 UTC | opus / high | Governed hypothesis cycle on the screen/params |
| `atlas-value-evaluate` | Sun 17:00 UTC | opus / high | Frozen governor; grades monthly, regime-annotated; ladder memos |

### 5.3 The three-layer decision path (unchanged)

```
[deterministic]  screener → candidates JSON (the ONLY things the LLM may act on),
                 each carrying canonical values AND per-field bounds
[LLM, bounded]   select / veto / rank → OrderIntent; kernel rejects any field looser
                 than its candidate's bound (per-field monotonicity, property-tested)
[deterministic]  kernel: bounds + limits.yaml + account state + broker preview/dry-run
                 + shared guards (wash registry, symbol locks, caps, breakers) → place → audit
```

Kernel re-validates against live quotes at submit (reject >1% deviation or stale >5 min). Ledger write and order submission are one transaction: **no ledger row, no order.**

---

## 6. Bot 1 — `swing/` on Tradier: short-term aggressive stock & options

Unchanged from v2's earlier cut. Mandate: 1–10 day swing holds, cron cadence, aggressive-but-defined-risk. Regulatory framing: PDT rule eliminated 2026-06-04; intraday-margin awareness; margin is plumbing, gross ≤1.0× equity. **Setups S1–S5 as specified in v1** (S1 Dip Snap mean reversion, S2 Drift Rider post-earnings, S3 High Ground breakout, S4 Cheap Shot debit spread, S5 Paid to Agree credit spread on QQQ/IWM/mega-caps) with the v1 honesty notes (published RSI-2 win rates are stop-less historical profiles, not forecasts; binding-constraint arithmetic makes realized risk ≈1.25% on low-vol names; governor baselines use realized numbers).

**Tradier upgrades:** stock and single-leg option entries go in as **broker-resident OTOCO groups** (entry + take-profit + stop in one payload) — exits survive loop death, no morning stop re-placement. Multileg spreads: defined-risk by construction; whether OTOCO can wrap a multileg order is **verified at P1** (else spreads keep synthetic exits via the backstop engine). The preview endpoint runs before every submit; its warnings land in the decision row. R12 (expiry-day morning enforcement with the escalation ladder) also pre-empts Tradier's own risk-desk auto-close policy.

**Risk rules R1–R21 stand as specified in v1** (50%-of-equity per-trade ceiling with spread accounting at structural max loss; 1–3% risk-per-trade; 6% heat; 10% premium-at-risk; 5/2 concurrency; −3% daily-loss and −8%/−12% drawdown breakers with owner-only reset; cooldowns; earnings blackout; liquidity floors; limit-only; price sanity; no same-day round trips; full audit incl. no-trades; out-of-band watchdog; early-assignment doctrine R20; corporate-actions/halts doctrine R21), plus:

- **R22 — Live equity cap:** `max_live_equity_usd` in owner-owned limits.yaml. The kernel refuses any order taking deployed capital (positions at cost + open-order commitments + option obligations) above the cap, regardless of account balance. Raising it is an owner hand-edit (a ladder step, §11); agents and research can never touch it. Grep-enforced tripwire test.

---

## 7. Bot 2 — `value/` on tastytrade: value longs + margin-secured short puts

**Mandate:** own good companies at fair prices; get paid to wait via short puts backed by the portfolio's margin capacity (no idle-cash collateral drag); hold winners long (LTCG-aware). Weekly decisions, monthly full re-rank, positions touched only on triggers.

### 7.1 Screening pipeline — unchanged from v1

Deterministic; every number fetched + logged, never from model memory. Stage 1 hard rejects (F-score ≤6; net debt/EBITDA >3; interest coverage <3; accruals with the NI≤0 scaled branch; unavoidable earnings inside the put window with no long case; OI/spread fails) → Stage 2 composite rank (FCF yield + EV/EBIT + ROIC, cheapest decile dropped) → Stage 3 overlay tags (consensus-delta, IVR/proxy, distance-to-support, days-to-earnings, GARP). Output: ranked ~25-name watchlist persisted as the week's auditable decision file.

### 7.2 Margin-secured short-put mechanics (code-enforced)

Selection parameters unchanged from v1: 30–45 DTE; delta 0.20–0.30 (default 0.25); strike ≤ min(delta-band strike, support, happy-to-own price); IV gate IVR≥30 (prefer ≥40) or tagged proxy; GTC buyback at 50% of premium placed at open; close/roll at 21 DTE; rolls net-credit-only with thesis intact, max 2, then accept assignment; **hard earnings veto** (expiry precedes next report); OI ≥500, spread ≤10% of mid.

**Collateral doctrine (the delta from v1 — what "shares-secured" means in code):**
- **Sizing and caps run on assignment obligation** (strike × 100 × contracts) — NEVER on the ~20% margin requirement. Sizing to the margin requirement is 5× hidden leverage and is the classic put-seller blow-up; the kernel makes it structurally impossible. Single name (stock value + put obligation) ≤8% of equity at open, hard 10%; sector ≤25%; **aggregate short-put obligation ≤40% of equity**; total book exposure (long stock at market + put obligations) ≤ **1.0× equity** — premium efficiency, not leverage.
- **Assignment-stress rule (kernel, pre-trade):** simulate ALL open short puts assigned at strike simultaneously; the resulting margin loan must be ≤ `max_assignment_borrow_pct` of equity (owner-owned limits.yaml, default 25%). Assignment may transiently use margin borrow (tastytrade 8–11%); `--manage` normalizes within `borrow_normalize_sessions` (default 10) by the §7.4 exit rules, and borrow-interest accrual is logged into after-tax P&L.
- **Broker-computed margin is ground truth:** every submit is preceded by tastytrade's **order dry-run** (buying-power effect) and the deep margin dry-run when the book changes shape; requirements are never cached (the broker raises per-symbol margin discretionarily in volatile tape). A dry-run rejection or a `is-in-margin-call` trading-status flag is a P0 control signal.
- **Assignment detection is poll-based (R20 variant):** tastytrade has no assignment push event — `--manage` polls `Receive Deliver` transactions + positions pre-market and post-market; an assignment is an expected lifecycle event (effective basis = strike − cumulative premium, auditable per-name ledger), never a reconcile-break. $5 assignment fee logged.
- **Approval fallback:** if the uncovered-put permission is not granted at account opening, the bot runs **wide put credit spreads** (defined-risk, Level-3-class) as a stopgap and the governor files a DECISION-REQUEST — it never silently reverts to cash-secured treatment (owner's explicit preference).

### 7.3 Decision tree — unchanged in shape (the LLM operates only inside it)

```
held?                             → lifecycle rules only
breaker (SPY<200dma AND VIX>30)?  → no new short puts; longs only in ≤2% slugs
earnings inside window?           → strong long case → half-slug LONG, else PASS
IV rich (IVR≥40/proxy), price 0–10% above target, stress-rule headroom → SELL PUT (§7.2)
IV thin (IVR<20/proxy), or top-decile rank + strong positive consensus-delta → BUY LONG (5% slug)
price at/below target, IV middling → BUY LONG
else → PASS
```

### 7.4 Portfolio rules — unchanged plus stress caps

12–18 positions at ~5% slugs; cash buffer ≥10% **of unencumbered buying power** (the v1 cash floor re-based for a margin-backed book); wheel (covered calls ≥ basis+5%, ≤0.30Δ, same DTE/profit/earnings rules) only while Stage-1 still passes; exits on rank-decay/thesis-break/drift-trim; LTCG-aware discretionary exits; R20/R21 doctrines; R22 live equity cap identical to swing. The owner's 50%-per-trade ceiling is inherited (obligation-accounted); the tighter caps above dominate in practice.

---

## 8. Shared compliance & guard layer (updated)

All v1 DR rules stand; deltas for live money and the two-broker topology: **DR-0** order-path exclusivity + detective control now runs in both reconciliation domains (any broker order without a matching ledgered decision row → kill switch + owner P0); **DR-12** wash-sale registry is live and real from day 1, spans both brokers (same taxpayer; neither broker sees the other's lots), default config B (tag + weekly report), owner may flip hard-block for year-end; **DR-14/16** after-tax reporting incl. margin-borrow interest, two 1099-B export domains; **DR-17** symbol lock app-level via shared DB in both adapters; **DR-20** kill switch paths per broker (Telegram → psql halts row → **layer zero: broker dashboards / token revocation, works with the server dead** — for tastytrade, deleting the OAuth grant kills all access instantly).

Schemas as v1 (`swing.*`, `value.*`, `trading_shared.*` incl. `iv_snapshots`, wash registry, symbol locks) with `strategy_state` stages `candidate|validated|live_capped` — the schema encodes the cap-ladder posture; any live stage requires a matching `max_live_equity_usd` audit row. `value.*` adds `put_lifecycle` (open→50%-take/expire/roll/assign chains, per-name premium ledger, obligation + stress numbers frozen per decision) and `screen_snapshots`.

---

## 9. Dashboard — unchanged plus obligation panel

`/trading` (all-verticals overview: equity vs SPY/BIL, breaker/halt states, worker liveness, pending DECISION-REQUESTs, warm-up status) · `/trading/swing` (positions with resting OTOCO exits + DTE clocks, blotter with slippage + minutes-to-close, governor-computed setup performance, decision journal incl. no-trades, risk panel) · `/trading/value` (watchlist + rank moves, **short-put board: obligation vs the 40% cap, assignment-stress headroom, borrow balance + interest drag**, assignment/effective-basis ledger, wheel status, sector caps, regime-annotated performance, after-tax P&L) · **ladder panel** (current `max_live_equity_usd` per bot, deployed vs cap, evidence progress to next step, demotion history). All numbers from DB rows/ledger artifacts only.

---

## 10. Evaluation & expectation contracts (live evidence)

Strategy evidence comes from **live fills**; sandbox/cert output is plumbing evidence only and is never graded as performance (Tradier sandbox fills are simplistic; tastytrade cert fills are fake by design).

**Swing:** unchanged from v2 — success at current ladder size = zero kernel breaches, complete audit, positive realized expectancy; ≥6 months / ≥100 live trades for the full-size verdict; setup kill rule on governor-computed realized edge; "no valid setup → no trade" is a logged success.

**Value:** process compliance dominates (pass/fail: no earnings-straddling shorts, no cap or stress-rule breaches, no debit rolls, every trade thesis-logged). Returns regime-annotated (short-put sleeve expected to lag melt-ups ~8–10pp, worst documented ~18pp; must win flat/down tapes). Put metrics once the funded size permits: win ≥75%, premium retention ≥50%, assignment-recovery ≥60% above basis within 90 days, **borrow episodes normalized within the rule window 100% of the time**. Governors: DB rows only, frozen SPY+BIL pair, deterministic demotions, ladder memos, owner DECISION-REQUESTs for kernel/limit changes; trials.jsonl + DSR discipline; LLM-signal candidates' historical backtests inadmissible.

---

## 11. Shakedown → funding → scale ladder (runbook: `LADDER.md` per bot)

**Phase S — sandbox shakedown (~2 weeks, unfunded).** Bot 1 on Tradier sandbox (full API surface, delayed data). Bot 2 on tastytrade cert (validates OAuth refresh flow, order lifecycle, complex orders, streamer, transaction polling; fills are fake and assignment cannot be simulated → those paths are exercised against **stub-broker fixtures** with recorded response shapes). Mechanical exit criteria per bot: ≥10 clean sessions; zero kernel breaches; zero unexplained reconcile breaks; assignment (fixture), expiry-ladder, halt, and cancel/replace paths exercised; watchdog observed firing on an induced silent-worker drill; kill switch exercised end-to-end (incl. the layer-zero path against the cert/sandbox credentials). Governor writes a SHAKEDOWN-PASS memo citing each criterion.

**Funding gate (owner).** On SHAKEDOWN-PASS: owner wires P0-C amounts and hand-sets each bot's initial `max_live_equity_usd` (recommended meaningfully below the wired amount). CLAUDE.md rule 1 per bot: *"Live trading is capped at `max_live_equity_usd`. Agents, research loops, and governors may propose but can never raise any cap; every raise is an owner hand-edit with a reviewed diff."*

**Scale ladder.** Steps are owner hand-edits, each requiring a governor evidence memo: step N→N+1 (roughly doubling) after **≥40 live trades (swing) / ≥8 completed position lifecycles (value)** at the current step with positive realized expectancy, 4 consecutive weekly PASS grades, zero kernel breaches, no open risk-surface DECISION-REQUESTs. **Automatic demotions (code, not judgment):** drawdown >1.5× the worst seen at any prior step → down one step; two daily-breaker trips in 10 sessions → down one step + owner page; −12% HWM breaker → deployed capital frozen (lifecycle-only mode) until owner reset. First live sessions run extra-small for Bot 2 specifically because cert-env fill evidence is weak (the first real fills are themselves shakedown data).

---

## 12. Implementation plan

Standard gates every phase (unchanged): atlas pytest path-conditional, ai-server pytest + lint_docs, code-review LGTM (INV-13), secrets grep, registries/CHANGELOG, seed-schedules sole writer, byte-identical staging, deploy via push → `/task deploy server` + `/task redeploy atlas`.

| Phase | Contents | Est. |
|---|---|---|
| **P0 — Owner** | P0-A…P0-E (§1): accounts + approvals (Tradier L3 margin; tastytrade Basic w/ uncovered puts), OAuth grant + tokens into atlas `.env`, funding amounts decided (not wired), tax params, IV-backfill call | owner |
| **P1 — Shared layer** | `tradingcore`: adapter interface + capability matrix; **tradier.py** (OTOCO, multileg + preview, form-encoding; verify multileg-OTOCO — decision point for spread exits); **tasty.py** (OAuth2 refresh, orders + dry-run + margin dry-run, complex orders, Receive-Deliver polling); **alpaca_data.py** (bars/history only); black_scholes; synthetic-OCO backstop; NYSE calendar w/ early closes; per-broker rate budgets; guards; iv_snapshots collector (warm-up clock starts at deploy); universe builder; migration 0043; property tests for every guard | 1–2 sessions |
| **P2 — Swing vertical** | Kernel R1–R22 with property tests incl. candidate-bounds monotonicity + live-cap; signals S1–S5; screener with bounds emission; executor (preview-before-submit, OTOCO); migration 0044; CLAUDE.md/LADDER.md/PROTOCOL seeds; live-guard tripwires (host allowlist, cap presence, deny-list greps); 4 skills + dual-row DST schedules; out-of-band watchdog | 2–3 sessions |
| **P3 — Value vertical** | Screen pipeline extending atlas_dash EDGAR ingestion; F-score/accruals (NI≤0 branch); consensus-delta snapshotter; **margin-secured put lifecycle: obligation accounting, assignment-stress rule, dry-run gating, Receive-Deliver assignment polling, borrow-normalization, wheel**; kernel; executor; migration 0045; 4 skills + schedules | 2–3 sessions |
| **P4 — Dashboard** | `/trading` pages + query libs + ladder & obligation panels; npm build gate | 1–2 sessions |
| **Phase S — Shakedown** | ~2 weeks on Tradier sandbox + tastytrade cert, concurrent with P4/P5; mechanical exit criteria (§11); induced-failure drills | 2 weeks wall-clock |
| **P5 — Learning loops** | Research skills' first governed cycles; governors live; decoys armed; evals registered; env-scoping hardening conversation | 1 session + steady |
| **F — Funding gate** | Owner wires funds + sets initial caps on SHAKEDOWN-PASS; first live sessions at canary size (Bot 2 extra-small first week) | owner |

**Testing strategy** as v2 plus: tasty.py OAuth-refresh failure paths (401-at-refresh alert — grant deletion/secret regeneration kills the bot loudly, never silently), dry-run parsing goldens, Receive-Deliver assignment fixtures (short put assigned; partial assignment), borrow-normalization property tests, obligation-vs-requirement cap tests (a margin-requirement-sized intent must be rejected), Tradier form-encoding goldens, preview parsing, OTOCO reconciliation, live-cap breach attempts, both brokers' order-state machines diffed against recorded sandbox/cert transcripts.

## 13. Top risks

1. **Live-day-1 plumbing risk** — shakedown + live-guard tripwires + R22 caps; first ladder step is pre-decided tuition money.
2. **Cert/sandbox fidelity** — tastytrade cert can't simulate fills or assignment; mitigated by fixture drills + extra-small first live week for Bot 2 (§11); Tradier sandbox delayed data scoped to plumbing.
3. **Margin-secured puts done wrong = leverage** — structurally prevented: obligation-based caps, 1.0× total-exposure ceiling, assignment-stress rule with bounded borrow, broker dry-run as ground truth. The efficiency is cash staying invested, never bigger obligations.
4. **Two-broker complexity** — two adapters, two reconciliation domains, app-level-only cross-broker guards; priced into P1–P3.
5. **Options exit latency (residual)** — Tradier OTOCO covers stocks/single-legs; spreads may stay synthetic (P1 verification); defined-risk caps the damage. Bot 2's GTC buybacks rest at tastytrade.
6. **Broker discretion** — tastytrade can raise per-symbol margin or reject orders in volatile tape (never cache requirements; dry-run every submit); Tradier's expiry auto-close (R12 pre-empts).
7. **Silent worker death with live positions** — out-of-band watchdog is a funding-gate precondition; Tradier-resident exits + tastytrade GTC buybacks protect positions through loop death; assignment polling gap is bounded by the twice-daily manage cadence.

## 14. Out of scope

Robinhood (revisit per §3 postscript as a separate decision); cash-secured puts (owner-declined); shorting stock (involuntary R20 shorts auto-cured); naked calls; futures/crypto; intraday/ORB; §475(f) automation; portfolio margin (revisit only if the book approaches tastytrade's $125k PM threshold and the owner asks); changes to `trader/` v1 beyond the GOTCHAS note; recurring paid data without an owner decision; protected paths (MISSION §M).
