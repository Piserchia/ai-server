# Quant Stack — validation-desk vertical (design)

Date: 2026-09-16
Status: APPROVED (owner prompt 2026-09-16 delegated the full pipeline:
research → spec → plan → implement → deploy → adversarial post-analysis;
see Amendments)

## 1. Source blueprint

Owner pointed at @x_insider4's 2026-08-30 "$200K quant stack" tweet
(status 2094086302849179706) + its linked article "The $200,000 Quant Stack
You Can Now Build in an Evening", and asked for a system mimicking that setup
for **making money through reports and automation**, with a turn-on switch,
thorough tests on the existing atlas Alpaca infrastructure, optionally its own
page, deployed, then adversarially reviewed.

The tweet's stack, component by component:

1. **Backtest engine** — vectorized, `position = signal.shift(1)` (look-ahead
   guard), fees + slippage on turnover (5 bps + 3 bps defaults), equity curve,
   leverage cap.
2. **Metrics** — annualized Sharpe, vol, max drawdown, longest-underwater
   days, Calmar.
3. **The critic** — "eight ways your backtest is lying": look-ahead,
   survivorship, repainting, missing costs, fill assumptions, parameter
   fitting, regime sampling, data alignment.
4. **Multiple-testing correction** — Deflated Sharpe Ratio
   (Bailey–López de Prado 2014); PASS iff DSR > 0.95; honest lifetime trial
   count N.
5. **Walk-forward validation** — rolling 180d-train/60d-test folds; judge on
   the **worst** fold.
6. **Position sizing** — fixed-fractional risk-per-trade (1% default, 20%
   notional cap), "size for the path, not the destination".
7. **Production health check** — live-vs-backtest Sharpe decay
   (halt if live < 0.5 × backtest on a 30-bar window), DD exceedance,
   kill condition pre-committed.
8. **Five AI roles** — Hypothesis / Code / Critic / Statistician / Risk as
   prompt architecture.

Core thesis, verbatim: **"Generation is free now. Validation is the job."**

## 2. Why this fits atlas (the money logic)

MISSION §M / INV-22: no order path, ever, autonomously. So "making money"
here is the honest version of the tweet's own claim — the money is in
**not deploying noise**, and in reports that sharpen real decisions:

- Atlas mission priority 1 is "Make money — every feature must sharpen an
  investment decision (buy/sell/hold/size/hedge)". Validation reports do
  exactly that for every strategy the org considers.
- The research protocols ALREADY mandate this stack and lack the code:
  alpha-lab PROTOCOL §3 — *"A GO that does not state lifetime N (from
  trials.jsonl) and the Deflated Sharpe Ratio against it is invalid on its
  face"* — has **zero executable backing** (trials.jsonl is 0 bytes; grep
  finds no Sharpe implementation anywhere in atlas; max drawdown is
  hand-rolled 4× with two sign conventions; walk-forward exists once,
  hard-wired inside trader T-0003's 909-line harness).
- The trader adversary charter states "An undeflated Sharpe is a defect" —
  with no way to compute a deflated one.

The vertical therefore ships the stack as a reusable library + an automated
weekly report loop, and its reports become the rigor floor the other
verticals' protocols already point at.

## 3. Binding constraints (inventory)

| Constraint | Source | Consequence |
|---|---|---|
| No order path; reports/advisory only | MISSION §M, INV-22 | `quant/` has no order surface; grep tripwire test; imports only `tradingcore.alpaca_data` (data host) |
| Brokerage creds only in atlas `.env` | INV-22 | data adapter resolves creds via `tradingcore.env.resolve`; ai-server env untouched |
| stdlib + pyyaml only (research verticals) | owner ceiling, momentum E-0033; LOOP.md §6 "new external deps = owner" | pure-python engine, no numpy/pandas |
| Free/keyless data only | atlas CLAUDE.md (owner 2026-08-03) | Alpaca IEX free feed daily bars; caveats stated, never a paid workaround |
| Verticals self-contained; shared code graduates to engine/ on 2nd use | atlas CLAUDE.md | new `quant/` package; no tradingcore edits (owner-owned); alpha-lab wiring is a follow-up owner decision |
| `lint_docs.py` UNISOLATED_WRITER_ALLOWLIST is frozen (protected path) | INV-4, SYSTEM.md | both new skills are `isolation: workspace` |
| Skills staged in atlas `integrations/ai-server/`, copied byte-identical | two-repo contract | author there first, `cp -R` to ai-server dev |
| Schedule writer is `seed-schedules.sh` only; paused survives re-seed | house pattern | switch = schedule row + config flag |
| Glossary entry per user-visible term; verify-frontend 8 steps | atlas CLAUDE.md | terms.json seed + db migration + `<Term>` usage |
| No publishing to public social accounts / email | MISSION §M | reports delivered via Telegram summary + private `/quant` page only |
| LLM-signal backtests INADMISSIBLE | alpha-lab PROTOCOL §3 | reference strategies are deterministic rule-based signals only |

## 4. Design decisions

- **D1 — Home**: new self-contained atlas vertical `quant/` (package
  `quantlab`), own `.venv` + pyproject + tests + manifest gate
  (`when_paths: ["quant/"]`). Not tradingcore (owner-owned), not alpha-lab
  (its ceiling and self-containment lock the code away from other verticals).
- **D2 — Pure stdlib engine**: no new dependencies; matches all four existing
  harnesses and the noise_baseline.py house style (deterministic, seeded,
  fail-closed).
- **D3 — Data**: daily bars via `tradingcore.alpaca_data.DataClient`
  (Alpaca IEX free, split-adjusted), fetch-once JSON cache under
  `quant/.cache/bars/` (gitignored) with a sha256 `manifest.json`
  (provenance per PROTOCOL §3). Universe = committed YAML with an explicit
  survivorship caveat — the critic's survivorship check FLAGS it honestly.
- **D4 — Page**: `/quant` on atlas web (Next.js server component, CF-Access
  private). Reads filesystem artifacts (`quant/reports/`, house `/momentum`
  pattern): runs table (strategy, window, Sharpe, DSR, worst fold, verdict
  badge), critic checklist, latest memo. Nav entry + glossary terms.
- **D5 — Turn-on switch (three layers, all owner-flippable)**:
  1. `quant/config/settings.yaml: enabled: true|false` — CLI preflight
     exits 0 with a DISARMED line when false (cheap no-op; the preflight the
     value vertical wished it had).
  2. Schedule rows in `seed-schedules.sh` — pause/resume via Telegram
     `/schedule` or psql; seeder never un-pauses.
  3. Rule 1 in `quant/CLAUDE.md` + `tests/test_reports_only.py` grep
     tripwire in the deploy gate — the authority ceiling.
  Ships with `enabled: true` and rows armed (reports-only vertical; safety
  ceiling is the tripwire, not the schedule).
- **D6 — Verdicts are memos**: a PASS is a report to the owner. No
  auto-promotion into any trading vertical (mirrors "a GO is a decision memo
  to the owner only").
- **D7 — Five AI roles**: realized as the two skills' prompt structure
  (worker = Code+Statistician+Risk; governor = Critic; Hypothesis = the
  committed strategy roster), not five separate agents. YAGNI.

## 5. Architecture

```
atlas/quant/
  pyproject.toml            # [project] quantlab, requires-python >=3.12, dev = pytest+ruff
  CLAUDE.md                 # Rule 1 (reports only) + owner-owned files + bootstrap
  config/
    settings.yaml           # enabled, cost defaults, dsr_threshold, wf windows, health thresholds
    roster.yaml             # strategies × universe × params to validate weekly
    universe.yaml           # committed symbol list, version+asof, survivorship caveat
  quantlab/
    __init__.py
    engine.py               # run_backtest(bars, signal_fn, cfg) -> BacktestResult
    metrics.py              # sharpe, vol, max_drawdown, underwater, calmar, cagr, turnover
    dsr.py                  # psr(), expected_max_sr(), deflated_sharpe(); fail-closed on N<=0
    walkforward.py          # rolling folds + purge/embargo; worst-fold verdict
    leakage.py              # the 8-check critic -> CriticReport
    sizing.py               # fixed-fractional + vol-target math, streak table
    health.py               # live-vs-backtest decay checks -> check rows
    trials.py               # trials.jsonl append/read/count (lifetime N)
    report.py               # render R-#### report.md + metrics.json
    data.py                 # Alpaca daily bars via tradingcore.DataClient + cache + manifest
    strategies.py           # sma_gate, rsi2_meanrev, donchian_breakout, buy_hold
    cli.py                  # python -m quantlab.cli preflight|fetch|validate|sweep|health
  tests/                    # see §8
  reports/                  # R-####/ artifacts (committed)
  evaluation/
    PROTOCOL.md             # binding constitution (child of momentum's)
    LEDGER.md               # append-only
    trials.jsonl            # append-only, one line per variant ever run
  .cache/                   # gitignored bar cache
```

Data flow: `roster.yaml` → `cli sweep` → per-strategy: fetch/cached bars →
signal (lagged) → engine (costs) → metrics → walk-forward → critic → DSR
(N from trials.jsonl, appended first) → report.md + metrics.json under
`reports/R-####/` → LEDGER entry → commit/push → Telegram TL;DR → `/quant`
page renders artifacts.

## 6. Component contracts (the stack, made precise)

- **engine.run_backtest**: inputs = list of bars per symbol
  (`{"t","o","h","l","c","v"}`), a signal function producing target weights
  per symbol per day from **data up to and including t**, config
  (fee_bps=5, slip_bps=3 per side on turnover, max_leverage=1.0,
  capital=100_000). The engine applies `w_effective[t] = w_signal[t-1]`
  (the shift(1) rule) — a signal can never affect the return of its own bar.
  Daily returns from close-to-close; `cost[t] = turnover[t] ×
  (fee_bps+slip_bps)/1e4`; net curve compounds. Output: equity curve, daily
  returns, turnover, cost drag, per-symbol weights.
- **metrics**: native-frequency Sharpe (mean/std, ddof=1) + annualized
  (×√252, display only); vol; MDD as `min(E/peak − 1)` (canonical sign:
  negative; report `|MDD|`); longest-underwater in trading days with
  right-censoring ("ongoing ≥ X" if unrecovered); CAGR; Calmar =
  CAGR/|MDD| (full-sample variant, stated); annual turnover.
- **dsr** (verified against the primary papers):
  - `psr(sr_hat, sr_star, T, skew, kurt)` =
    `Φ((sr_hat − sr_star)·√(T−1) / √(1 − skew·sr_hat + ((kurt−1)/4)·sr_hat²))`
    — native frequency, raw kurtosis (Normal = 3, not excess).
  - `expected_max_sr(n_trials, var_trial_sr)` =
    `√V · ((1−γ)·Φ⁻¹(1−1/N) + γ·Φ⁻¹(1−1/(N·e)))`, γ = 0.5772156649.
  - `deflated_sharpe(returns, n_trials, var_trial_sr)` = PSR(SR0). PASS iff
    > 0.95. **Raises** on N ≤ 0 (noise_baseline house rule: a silently
    permissive correction is the worst failure mode); warns (report caveat)
    for N < 10 (approximation under-corrects).
  - Golden test: the 2014 paper's worked example → DSR ≈ 0.90.
- **walkforward**: rolling folds, default train=180, test=60 trading days,
  stride=test; purge = signal lookback horizon before each test block;
  embargo = 1% of sample after it. Reports per-fold Sharpe/return/MDD,
  `positive_folds/total`, worst fold, and the concatenated-OOS curve.
  Verdict input = **worst fold**, per the blueprint and momentum PROTOCOL.
- **leakage (critic)** — programmatic where possible, each check returns
  PASS/FLAG/FAIL + evidence:
  1. look-ahead: future-perturbation test — truncate data after t, recompute
     signal at t, must be identical (run at 3 sampled dates).
  2. survivorship: universe.yaml metadata must declare point-in-time-ness;
     current-constituent universes FLAG with the momentum E-0026 citation.
  3. repainting: recompute signal streaming (bar-by-bar) vs batch; assert equal.
  4. costs: fee+slip > 0 enforced; report run at 0×/1×/2× costs.
  5. fills: engine trades at next close after signal (never same-bar);
     assert every mark within its bar's [l,h].
  6. parameter fitting: params-per-strategy counted vs data length; >5
     params or in-sample-tuned params FLAG.
  7. regime sampling: SPY 200d-MA bull/bear/chop labeling; test window must
     contain ≥2 regimes or FLAG; per-regime metrics reported.
  8. alignment: timestamps monotonic, unique, UTC, same calendar across
     symbols; missing-bar count reported.
- **sizing**: `units = f·equity / stop_distance` (f=1% default), notional
  cap 20%; the streak table (1%→−11.4% at 12 losses, 5%→−46%) rendered in
  every report's risk section. Vol-target alternative:
  `L = σ_target/σ̂ (EWMA)`, leverage-capped. Backtest-internal only.
- **health**: for strategies with a prior PASS report: trailing 30-bar and
  60-bar live-window Sharpe vs backtest Sharpe → `HALT` row if
  live < 0.5 × backtest; trailing DD vs backtest MDD → `HALT` if exceeded.
  Kill conditions are printed in the PASS report **at validation time**
  (pre-committed while objective). Output shape mirrors firm/risk.py check
  rows. Paper-metrics only — "live" means the most recent data window, not
  live capital.
- **trials**: append-only JSONL, schema
  `{"ts","idea","name","family","params_hash","verdict","note"}` (alpha-lab
  compatible). Every variant/grid cell ever run gets a line BEFORE the
  verdict is computed. Lifetime N for the DSR = **all** lines ever
  (cross-family — the honest "I have tested N variations" count);
  per-family N is also reported for context.
- **report**: `reports/R-####/report.md` (prose memo: verdict, the single
  strongest reason, N + DSR + worst fold, critic table, kill conditions,
  caveats) + `metrics.json` (every number the page renders) +
  `manifest.json` (data provenance: source, symbols, window, sha256s,
  adjustment note). Memo format follows the five-roles structure.

## 7. Automation loop (skills + schedules + switch)

Two skills, staged in `atlas/integrations/ai-server/skills/`, copied
byte-identical to ai-server `skills/`:

- **`atlas-quant-validate`** (worker; weekly Sun 14:10 UTC;
  `claude-opus-5`/high; `isolation: workspace`; `permission_mode:
  bypassPermissions`; `subagents: [code-review]`; `post_review: always`;
  `privilege_class: guarded-writer`; payload
  `{"project_slug":"atlas","session_timeout_seconds":3600}`).
  Procedure: preflight (enabled flag, creds, cache) → `cli sweep` (roster) →
  health pass on prior PASSes → verify artifacts (pytest green) → ONE commit
  (reports + trials + LEDGER) → rebase → push → Telegram TL;DR (verdicts +
  DSR + worst folds + any HALT).
- **`atlas-quant-governor`** (critic/auditor; weekly Tue 10:20 UTC; same
  model tier; `isolation: workspace`; `privilege_class: guarded-writer` —
  writes only LEDGER audit entries).
  Duties: schedule liveness (validate row fired within cadence+25h);
  trials-before-verdict ordering; every report's DSR recomputed from
  metrics.json inputs (independent arithmetic); critic FLAGs acknowledged in
  memo prose; `enabled: false` ⇒ confirm last run no-op'd; findings →
  AUDIT LEDGER entry + Telegram. Never edits reports, config, or code.

Switch operation (documented in CLAUDE.md + the page):
- OFF without deploy: `/schedule pause atlas-quant-validate` (+ governor), or
  set `enabled: false` in `quant/config/settings.yaml` (commit+redeploy).
- ON: resume rows / set true. Seeder never un-pauses a paused row.

## 8. Testing strategy

`quant/tests/` (pytest, `.venv`, stdlib): engine goldens (hand-computed
2-symbol case; shift(1) proven by a peeking signal that gains nothing;
cost arithmetic exact; leverage cap); metrics goldens (known curves →
exact Sharpe/MDD/underwater/Calmar incl. right-censored spell); DSR paper
worked example ≈ 0.90 + fail-closed N≤0 + kurtosis-convention test;
walk-forward fold construction + purge/embargo boundaries + worst-fold;
critic: each of the 8 checks catches a seeded violation AND passes a clean
control (decoy-library spirit); sizing exactness + streak table; health
halt triggers; trials append/read/N; report renders with every required
section; `test_reports_only.py` grep tripwire (no `submit_order`,
`place_order`, `api.alpaca.markets`, `broker-api`, `tradingcore.tradier`,
executor imports); switch behavior both states; data adapter offline via
injected `_request` fake + cache round-trip + manifest sha256; live Alpaca
smoke test behind a `pytest.mark.alpaca` marker (skips without creds) —
the "thorough tests using existing alpaca infrastructure" requirement, run
for real during acceptance.

## 9. Paperwork + deploy map

Atlas: manifest gate row; `scripts/install-venv-sitecustomize.sh` +=
`quant/.venv`; `atlas/CLAUDE.md` verticals row; `evaluation/LOOP.md` §1 stage
rows + §2 single-writer rows + §6 ceilings line (owner-authority edits, made
under the owner's standing instruction, flagged in the final report);
glossary terms.json + db migration (`00NN_glossary_quant.sql`); web page +
Nav; `integrations/ai-server/README.md` rows. ai-server: 2 skills;
`SKILLS_REGISTRY.md`; atlas `CHARTER.md` roster; `seed-schedules.sh`
upserts; `INDEX.md` block; this spec + the plan; `docs/README.md` if needed.
Deploys: atlas push → `atlas-redeploy` job; ai-server push → `server-deploy`
job (arms schedules after green gates). Verify: schedule rows present,
`curl localhost:8791/quant` 200 + markup, skills resolvable, pytest green
in prod paths, lint_docs PASS.

## 10. Non-goals / follow-ups (owner decisions, not ours)

- No wiring into alpha-lab/swing/value harnesses (their skills are frozen;
  adopting quantlab is a LOOP.md §7 front-door change).
- No intraday engine, no numpy port, no paid data, no public page, no
  selling of reports anywhere — the reports' customer is the owner.
- No order path of any kind, ever (INV-22 restated).
- Decoy injection into the governor's audit (decoy_library pattern) —
  worthwhile v2, excluded from v1 like alpha-lab did.

## Amendments

- 2026-09-16: Approved-by-delegation. The owner's prompt explicitly ordered
  research → documented plan → implementation (turn-on switch, thorough
  Alpaca-infra tests, optional page) → deploy → adversarial execution review,
  autonomously. Design decisions D1–D7 taken under that delegation; the
  LOOP.md/CLAUDE.md `[system]` edits it requires are recorded as
  owner-authority actions in the final report.
- 2026-09-17 (post-adversarial-audit corrections): governor cadence shipped
  as Tue **12:20** UTC (not 10:20 as §7 first read) to clear the Tue 10:00
  atlas-build slot. The desk shipped ARMED at birth under the delegation
  above; steady-state switch flips are owner-only (LOOP.md §6). The
  validate skill gained a post-push gated redeploy dispatch so /quant
  surfaces each sweep (the page reads the runtime clone). The critic's
  `fills` check now audits real OHLC containment when bars are supplied.
  Findings register: `docs/QUANT_STACK_ADVERSARIAL_2026-09-16.md`.
