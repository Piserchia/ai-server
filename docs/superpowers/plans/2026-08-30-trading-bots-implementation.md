# Trading Bots (swing + value advisor) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the accepted v3 spec — an aggressive swing auto-trader on Tradier (sandbox-first, live-capped) and a value advisor producing shadow-ledger-graded theses — across the atlas repo (code, DB, dashboard) and ai-server (skills, schedules, registries).

**Architecture:** Clone the shipped `trader/` vertical's doctrine: deterministic Python computes/enforces/records; scheduled Claude skills supervise, decide within kernel-enforced bounds, research, and grade. New shared lib `tradingcore` carries the Tradier client, options math, calendar, and cross-vertical guards. The advisor has **no order path at all** (grep-tripwired).

**Tech Stack:** Python 3.12 stdlib + pyyaml only (owner ceiling); Postgres via `psql` bound variables (no driver); dbmate migrations; Next.js 15 server components for dashboard; ai-server SKILL.md skills + `seed-schedules.sh`.

**Spec:** `docs/superpowers/specs/2026-08-27-two-trading-bots-design.md` (v3) — all numeric parameters (R-rule table §6, thesis rules §7, cadences §5.2) live THERE; this plan cites them rather than re-stating, and the spec travels with the plan.

## Global Constraints

- Dependency ceiling: **stdlib + pyyaml** in all new atlas Python (spec O-5). No pandas/numpy/SDKs. Postgres via `psql` subprocess with `-v` bound vars + stdin SQL (never `-c`) — copy `trader/trader/ledgerlink.py` technique verbatim.
- **Sandbox-first pin:** `swing/config/settings.yaml` ships `mode: "sandbox"`; flipping to `live` + setting `max_live_equity_usd` is an owner hand-edit (spec §11). `tests/test_live_guard.py` greps enforce.
- **Advisor never trades:** `value/` contains no broker-order code and no Tradier token access — `tests/test_no_order_path.py` greps enforce.
- Migrations: **0044_trading_shared, 0045_swing, 0046_value** (0043 is taken); additive/idempotent statements, `-- migrate:up/down`, mirror `0042_trader.sql` style.
- Universe partition: SPY/VTI/EFA/AGG/SGOV/BIL and their options excluded from swing's tradeable set (spec §5.1).
- Every credential is owner-provisioned via atlas root `.env` (env-first resolution, copy `trader/trader/alpaca.py:load_root_env`); missing credential ⇒ report provisioning gap, never create.
- Skills authored in atlas `integrations/ai-server/skills/<name>/SKILL.md`, staged **byte-identical** into ai-server `skills/`; `seed-schedules.sh` is the sole schedule writer; every workspace skill payload carries `{"project_slug":"atlas"}`.
- Commit gates: atlas — vertical pytest green before every push, rebase before push; ai-server — pytest + `scripts/lint_docs.py` green, code-review pass, fetch+merge before push, CHANGELOG entries.

## File map (locks decomposition)

```
atlas/tradingcore/pyproject.toml, tradingcore/{__init__,http,env,calendar_nyse,
  black_scholes,tradier,alpaca_data,ratebudget,ivstore,guards,ledgerbase,universe}.py,
  tests/test_{http,calendar,black_scholes,tradier,ratebudget,ivstore,guards}.py
atlas/db/migrations/{0044_trading_shared,0045_swing,0046_value}.sql
atlas/swing/{CLAUDE.md,LADDER.md,pyproject.toml},
  config/{settings.yaml,limits.yaml,universe.yaml,strategies/setups_v1.yaml},
  swing/{__init__,signals,screener,earnings,risk,executor,ledgerlink}.py,
  evaluation/{PROTOCOL.md,LEDGER.md,trials.jsonl}, research/,
  tests/{conftest,test_signals,test_screener,test_risk_kernel,test_executor,
         test_live_guard,test_adoption_gate}.py
atlas/value/{CLAUDE.md,pyproject.toml},
  config/{settings.yaml,screen.yaml,universe.yaml},
  value/{__init__,fundamentals,consensus,screen,theses,shadow,reports,ledgerlink,
         monitor,weekly}.py,
  evaluation/{PROTOCOL.md,LEDGER.md,trials.jsonl},
  tests/{conftest,test_screen,test_theses_gates,test_shadow,test_no_order_path}.py
atlas/web/lib/atlas/{swing-queries,value-queries}.ts,
  web/app/trading/{page.tsx,swing/page.tsx,value/page.tsx}
atlas/integrations/ai-server/skills/atlas-{swing-supervise,swing-trade,swing-research,
  swing-evaluate,value-theses,value-monitor,value-research,value-evaluate}/SKILL.md
atlas/manifest.yml (gates += tradingcore/, swing/, value/ pytest when_paths)
ai-server: skills/<8 copies>, scripts/seed-schedules.sh (+11 rows),
  .context/SKILLS_REGISTRY.md, .context/org/divisions/atlas/CHARTER.md,
  .context/INDEX.md, CHANGELOG entries
```

## Interfaces locked up front

- `tradingcore.http.request(method,url,headers,body=None,params=None,...) -> (status, json|None)` — copy of trader's; plus `form_request(method,url,headers,form:dict,params=None,...)` (urlencoded body, `Accept: application/json`).
- `tradingcore.tradier.TradierBroker(token,account_id,sandbox:bool)` — hosts hardcoded module consts `LIVE_HOST="https://api.tradier.com"`, `SANDBOX_HOST="https://sandbox.tradier.com"`. Methods (all return parsed dicts; orders tagged): `get_clock()`, `get_calendar(year,month)`, `get_quotes(symbols:list)->dict`, `get_history_daily(symbol,start,end)->list`, `get_expirations(symbol)->list`, `get_chain(symbol,expiration,greeks=True)->list`, `get_balances()`, `get_positions()->list`, `get_open_orders()->list`, `find_orders_by_tag(tag_prefix,days)->list`, `preview(form)->dict`, `place(form)->dict` (single generic place with `preview=true|false`), `cancel(order_id)`. OTOCO/OCO built by helper `equity_otoco_form(symbol,qty,entry_limit,target,stop,tag,duration)`; single-leg option forms via `option_order_form(...)`; multileg via `multileg_form(legs,...)`.
- `tradingcore.alpaca_data.DataClient()` — DATA host only (`get_daily_bars(symbols,start,end,feed='iex')`, `get_latest_trades(symbols)`); **no trading host anywhere** in tradingcore.
- `tradingcore.black_scholes`: `bs_price(S,K,T,r,sigma,cp)`, `bs_delta(...)`, `implied_vol(price,S,K,T,r,cp) -> float|None` (bisection 1e-4, ≤100 iters).
- `tradingcore.calendar_nyse`: `is_trading_day(d:date)->bool`, `early_close(d)->str|None` ("13:00"), `HOLIDAYS`, `EARLY_CLOSES` tables 2024–2027.
- `tradingcore.ivstore.IvStore(url)`: `record(day,symbol,atm_iv,hv20,source)`, `iv_rank(symbol,current_iv)->(float|None,int)` (None until ≥60 sessions), `proxy(current_iv,hv20)->float|None`.
- `tradingcore.guards.SharedGuards(url)`: `record_realized_loss(bot,symbol,day,amount)`, `recent_loss_days(symbol)->int|None` (≤31), `set_lock(bot,symbol,side)` / `clear_locks(bot)` / `opposing_lock(bot,symbol,side)->str|None`, `overlaps(symbols)->dict` (vs swing lots + trader positions).
- `swing.risk.validate(limits, state:KernelState, intents:list[SwingIntent], candidates:dict[str,Candidate], mode) -> Verdict` — same Verdict shape as trader; SwingIntent adds `candidate_id,setup,structure,stop,target,dte`; every intent must reference an emitted candidate and be **tighter-or-equal** on qty/limit/stop/dte (per-field monotonicity, R-bounds).
- `swing.executor` CLI: `python3 -m swing.executor --manage` | `--screen [--out F]` | `--submit F`; JSON report on stdout, exit 0 for handled outcomes; statuses = trader's set + `off_window`.
- `value.weekly` CLI: `python3 -m value.weekly [--dry-run]` → screen → watchlist file `research/watchlists/YYYY-MM-DD.json` → gated theses → shadow booking → report JSON (incl. telegram_text). `value.monitor` CLI: lifecycle sweep, exit 0, report JSON with `alerts:[...]`.
- Shadow booking prices: long = quote mid; put thesis premium = `mid - spread/2` (pessimistic), documented in shadow.py docstring.

---

### Task 1: Plan + tracking scaffold ✅on commit
Commit this plan; `TaskCreate` per phase. Commit: `docs(plans): trading-bots implementation plan`.

### Task 2: tradingcore skeleton + http/env/calendar/BS (TDD)
Write failing tests first (`pytest tradingcore/tests -x`): `test_http.py` (form encoding, 429 retry via injected `_sleep`, 404-GET-None), `test_calendar.py` (2026-07-03 early close, 2026-11-26 holiday-adjacent Friday 13:00, weekends false, MLK 2027-01-18 holiday), `test_black_scholes.py` (put @ S=100,K=100,T=0.25,r=0.05,σ=0.2 ≈ 3.53 ±0.05; delta≈-0.44 ±0.02; implied_vol round-trips σ=0.2 ±1e-3). Implement `http.py` (copy trader + `form_request`), `env.py`, `calendar_nyse.py` (tables 2024–2027), `black_scholes.py`. `pyproject.toml` deps `["pyyaml"]`, py3.12. Commit per green module.

### Task 3: tradier client + alpaca_data + ratebudget (stub-transport TDD)
`test_tradier.py` with injected fake `form_request/request` capturing calls: quotes parse (`quotes.quote` single-vs-list quirk), history parse, chain-with-greeks parse, `equity_otoco_form` produces Tradier's documented indexed params (`type[0]=limit`, `side[1]=sell`, `class=otoco`, `duration[1]=gtc`…), preview flag, tag round-trip, `find_orders_by_tag` filters. `test_ratebudget.py`: bucket sleeps via injected clock. `alpaca_data.py` = data-host subset of `trader/trader/alpaca.py` (no trading host — assert in test). Commit.

### Task 4: migration 0044 + ivstore + guards
Write `0044_trading_shared.sql`: schema `trading_shared`; tables `iv_snapshots(day date, symbol text, atm_iv numeric, hv20 numeric, source text, primary key(day,symbol))`, `wash_registry(id uuid pk default, bot text, symbol text, day date, amount numeric)`, `symbol_locks(bot text, symbol text, side text, ts timestamptz default now(), active bool default true)` + indexes; idempotent; down drops schema. `ivstore.py`/`guards.py` via `ledgerbase.Psql` (extracted `_psql` runner). Tests use a stub Psql capturing SQL+vars (no DB dependency); one integration test marked `@pytest.mark.pg` (skipped without DATABASE_URL) mirroring `test_ledgerlink_pg.py`. Run `dbmate up` against local atlas DB; verify `\dn trading_shared`. Commit + push atlas (rebase first).

### Task 5: swing config + signals (TDD)
`config/universe.yaml`: version, asof, `index_etfs: [QQQ, IWM]`, `equities:` S&P-100 list minus trader allowlist overlap, `options_whitelist:` (QQQ, IWM + ~20 mega-caps). `config/limits.yaml`: every R-rule number from spec §6.2 verbatim + `max_live_equity_usd: 0`. `config/settings.yaml`: `mode: "sandbox"`, hosts pinned declaratively, windows `supervise_window_et: ["09:35","11:30"]`, `trade_window_et: ["15:10","15:55"]`, `benchmark_symbols: [SPY, BIL]`, feeds. `config/strategies/setups_v1.yaml`: S1–S5 parameters from spec §6.1 verbatim, each with `enabled`, `risk_pct`, entry/exit/stop params. `test_signals.py`: rsi2 on a hand-computed 10-bar series; atr14; donchian_high; adx trending>25 vs flat<20 series; rvol; hv20. Implement `signals.py` pure functions over `list[dict]` bars (`{"t","o","h","l","c","v"}`). Commit.

### Task 6: swing screener + earnings (TDD)
`earnings.py`: Finnhub calendar fetch (token via env `FINNHUB_TOKEN`, absent ⇒ `{"status":"ABSENT"}`), `next_earnings(symbol)->date|None`, cached per-run. `screener.py`: `Candidate` dataclass `{id,setup,symbol,structure("stock"|"debit_spread"|"credit_spread"),side,qty_max,limit_bounds,stop_max_distance,target,dte_range,legs|None,expected_metrics:None,gates:dict}`; `screen(bars,quotes,chains,ivctx,positions,limits,setups,now) -> list[Candidate]` implementing S1–S5 entry conditions + liquidity floors (R13) + earnings blackout (R11) + IV gate (rank or proxy, tag `ivr_proxy`) + universe partition. Tests: synthetic bar fixtures triggering exactly S1 (RSI2<10 above 200SMA) and S3 (Donchian break + RVOL); assert bounds emitted (qty_max from R2 ATR sizing clipped by R1/R19); assert SPY never emitted; assert earnings-within-5d suppresses. Commit.

### Task 7: swing kernel (property-style TDD — every R-rule rejects)
`test_risk_kernel.py`: one test per rule R1–R22 proving a violating intent is rejected with the rule named in the reason, plus: intent-looser-than-candidate (qty above qty_max / limit outside bounds / stop wider than stop_max_distance / dte outside range) rejected (`bounds:` prefix); tighten-only accepted; heat accumulation across accepted intents; daily-loss/drawdown breakers emit halts; cooldowns; `max_live_equity_usd=0` in live mode rejects everything (sandbox mode exempt); flatten-mode semantics. Implement `risk.py` (`KernelState` extends trader's with `buying_power, open_risk_usd, premium_at_risk, positions_lots, day_trades_blocked, mode_live:bool`). Commit.

### Task 8: swing ledgerlink + migration 0045
`0045_swing.sql`: schema `swing`; `runs` (trader-style + `off_window` in comment), `orders` (+`tag`, `occ_symbol`, `structure`, `group_id` for OTOCO legs), `positions_lots(id,symbol,structure,qty,entry_price,stop,target,opened_run,closed_run,occ_symbol,expiry,state)`, `decisions(id,run_id,ts,candidate_id,setup,action,rationale,guard_evals jsonb,quote_snapshot jsonb,minutes_to_close int)`, `equity_curve(day,equity,cash,spy_close,bil_close)`, `strategy_state(stage check in ('candidate','validated','live_capped'))`, `halts`, `cooldowns view` (from orders realized losses). `ledgerlink.py` mirrors trader's incl. `record_decision`, `open_lots`, `heat()`, `orders_today`, halts API. Stub-Psql tests + `@pytest.mark.pg` round-trip. `dbmate up`. Commit + push.

### Task 9: swing executor (fixture-driven TDD)
`test_executor.py` with `StubTradier` (canned clock/quotes/chains/balances/positions/orders; scriptable failures): scenarios — market closed; `off_window`; clean supervise re-arms missing stop after simulated split-cancellation (R21); expiry-day force-close ladder escalates limit→walk→marketable and records; short-leg assignment appears as position delta ⇒ classified R20 lifecycle event + auto-cure order + P0 flag in report (never reconcile_break); unexplained foreign order ⇒ reconcile halt; margin rejection ⇒ logged control signal, no retry loop; submit path: candidate→intent→kernel→preview→OTOCO place with tag `aswg-<setup>-<sym>-<yyyymmdd>-<n>`, idempotent re-run via `find_orders_by_tag`; decision rows incl. no-trade; equity snapshot with SPY/BIL closes (via alpaca_data stub). Implement `executor.py` (`--manage/--screen/--submit`, window guard from Tradier clock + `calendar_nyse.early_close`). Commit.

### Task 10: swing docs + tripwires + LADDER
`CLAUDE.md` (rule 1: sandbox-pinned; live = owner hand-edit of settings.mode + max_live_equity_usd with reviewed diff; rules 2–3 mirror trader), `LADDER.md` (spec §11 verbatim mechanics incl. layer-zero kill switch), `evaluation/PROTOCOL.md` (adapted from trader's: cards, trials.jsonl, DSR, validator, decoys; §10 grading contract), seed `LEDGER.md` with D-0001 DECISION (vertical founded, spec pointer). `test_live_guard.py`: greps — settings `mode: "sandbox"`; only tradier hosts in tradingcore/tradier.py referenced; no `paper-api.alpaca` trading usage in swing; `max_live_equity_usd` key exists in limits; deny-edits list files exist. `test_adoption_gate.py`: setups file additions require LEDGER card ids (parse `card:` field per setup, assert present in LEDGER). Run full swing suite. Commit + push.

### Task 11: backtests B-0001..B-0003 (bounded, honest)
`research/B-0001-rsi2/run.py` (stdlib): Alpaca daily bars 2016→now for QQQ/IWM + 40-name liquid subset; S1 rules with 2.5×ATR stop AND stop-less variant; costs 3bps/side; walk-forward split 2016-21/2022-25; outputs JSON + LEDGER `B-0001 RESULT` entry (framing: baseline evidence, stop drag quantified, NOT a forecast). `B-0002-donchian/run.py` same harness for S3 (2×ATR, Chandelier exit approximation at close). `B-0003-pead-probe/run.py`: Finnhub historical earnings for 20 mega-caps 2023-25 → if endpoint refuses history on free tier, write `UNMEASURABLE` entry (error≠absence). Register all three in `trials.jsonl`. Commit.

### Task 12: value config + fundamentals + screen (TDD)
First inspect `dashboard/atlas_dash` EDGAR/earnings tables (read-only reuse if fields suffice; else self-contained fetcher with `.cache/` + 10 req/s throttle + UA header). `fundamentals.py`: `facts(symbol)->dict` (EBIT, EV inputs, FCF, ROIC inputs, F-score components, NI, CFO, assets, debt, interest), source-tagged. `consensus.py`: weekly snapshot writer + 4-wk delta (ABSENT during warm-up). `screen.py`: Stage1 rejects (incl. NI≤0 scaled-accruals branch) → composite rank → drop cheapest decile → top-40 → overlay tags; returns watchlist rows with full provenance. Tests: synthetic facts exercising every reject branch; NI≤0 branch; decile drop; deterministic ordering. Commit.

### Task 13: value theses + shadow + migration 0046 (TDD)
`0046_value.sql`: schema `value`; `screen_snapshots`, `theses(id,week,symbol,kind check in ('long','msp','exit','pass'),params jsonb,rationale,invalidation,gates jsonb,quote jsonb,state)`, `shadow_ledger(id,thesis_id,event,ts,price,note)`, `shadow_curve(day,equity,spy_close)`, `grades`. `theses.py`: compose per spec §7.2/§7.3 (LLM fills rationale/choices at skill layer; this module provides `build_candidates(watchlist,chains,ivctx,holdings,portfolio_value)` and `gate(thesis)->(ok,evals)` — earnings veto, liquidity, obligation cap 40%, per-name 8%, stress note, regime breaker, overlap/wash warnings via SharedGuards). `shadow.py`: `book(thesis,quote)` pessimistic; `sweep(quotes,chains,now)` lifecycle (invalidation/50%-target/21-DTE/expiry-assignment at effective basis); append-only (UPDATE forbidden — state transitions via new events). Tests: a gate-failing thesis is unbookable; booking prices pessimistic; lifecycle transitions; append-only enforced. Commit + `dbmate up` + push.

### Task 14: value monitor/weekly CLIs + reports + docs + tripwire
`weekly.py`/`monitor.py` per locked CLI; `reports.py` (markdown card + telegram TL;DR ≤1200 chars). `CLAUDE.md` rule 1: "This vertical NEVER places orders; it holds no broker credentials." `PROTOCOL.md`/`LEDGER.md` seeds. `test_no_order_path.py`: greps — no `tradier` import outside test files, no `TRADIER_TOKEN`, no `place(`/`preview(`/`otoco` strings in `value/`; monitor/weekly exit-0 dry runs against stub data. Full value suite green. Commit + push.

### Task 15: dashboard pages
Read `web/app/momentum/page.tsx` + one queries lib for house style. Add `swing-queries.ts` (`getSwingOverview`, `getOpenLots`, `getBlotter(50)`, `getSetupPerf`, `getDecisions(30)`, `getLadder`), `value-queries.ts` (`getTheses(week?)`, `getShadowScoreboard`, `getWatchlist`, `getOpenTheses`). Three server-component pages (`dynamic = "force-dynamic"`) matching atlas-tokens styling; ladder panel; shadow scoreboard; graceful empty-DB states ("vertical armed, awaiting first run"). `cd web && npm run build` green. Commit + push.

### Task 16: skills ×8 (atlas-authored, byte-identical staging)
Author in `integrations/ai-server/skills/`; frontmatter mirrors trader trio (models/effort/turns/isolation per spec §5.2; supervise/monitor: sonnet-4-6, no Write/Edit; trade/theses/research: opus-5 + workspace + payload; evaluates: no isolation field). Bodies encode the spec roles + trader-skill conventions (halts are successful outcomes; missing tokens ⇒ provisioning-gap report; escalation language). Copy to ai-server `skills/` with `cp -r` + `diff -r` proof. Commit atlas.

### Task 17: ai-server wiring
`seed-schedules.sh` +11 rows (dual-row DST scheme: `atlas-swing-supervise-edt '40 13 * 3-11 1-5'` / `-est '40 14 * 1-3,11,12 1-5'`; `atlas-swing-trade-edt '45 19 * 3-11 1-5'` / `-est '45 20 * 1-3,11,12 1-5'`; `atlas-value-theses-edt '30 14 * 3-11 1'` / `-est '30 15 * 1-3,11,12 1'`; singles: swing-research Fri 13:00, swing-evaluate Sun 16:00, value-monitor `10 18 * * 1-5`, value-research Tue 13:00, value-evaluate Sun 17:00) with slot-map comment block; SKILLS_REGISTRY +8 rows; atlas CHARTER roster +8; INDEX.md additions row; `manifest.yml` gates += tradingcore/swing/value `when_paths` blocks (atlas commit). Run `pipenv run pytest -q` + `lint_docs`. Code-review pass on the ai-server diff. Commit + push both repos.

### Task 18: final verification + handoff
Full test matrix both repos; `git log` clean; write CHANGELOG entries (atlas + ai-server runner-module none — skills only); update memory + artifact; summary with P0 checklist + deploy commands (`/task deploy server`, `/task redeploy atlas`).

## Self-review
Spec coverage: §3 broker (T3), §4 data incl. warm-ups (T3,T4,T6), §5.1 layout (T2–T14), §5.2 skills/schedules (T16–17), §5.3 bounds (T6,T7), §6 setups+R-rules (T5–T10), §7 advisor (T12–14), §8 guards/schemas (T4,T8,T13), §9 dashboard (T15), §10 contracts (T10,T13 PROTOCOLs), §11 ladder docs (T10), §12 gates (T17,T18), backtests (T11). Types/interfaces consistent per "Interfaces locked" block. No placeholders: parameter values live in the spec §6/§7 tables by explicit reference; code contracts are stated exactly.
