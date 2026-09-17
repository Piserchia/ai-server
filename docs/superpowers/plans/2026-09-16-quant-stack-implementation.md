# Quant Stack Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the $200K-quant-stack validation-desk vertical: a pure-stdlib
backtest-validation library (`quantlab`) in a new atlas `quant/` vertical,
an automated weekly reports loop (2 skills + schedules + turn-on switch),
a private `/quant` web page, deployed to prod, then adversarially reviewed.

**Architecture:** Self-contained atlas vertical (`quant/` package
`quantlab`), data via `tradingcore.alpaca_data.DataClient` (read-only
import), reports as committed filesystem artifacts rendered by a Next.js
server component; automation as two workspace-isolated ai-server skills
armed by seed-schedules rows.

**Tech Stack:** Python 3.12 stdlib + pyyaml (pytest/ruff dev), Next.js 15 /
React 19 / TS strict, Postgres via dbmate migration (glossary only).

**Spec:** `docs/superpowers/specs/2026-09-16-quant-stack-design.md`

## Global Constraints

- stdlib + pyyaml only in `quant/` runtime code (owner dependency ceiling).
- NO order surface anywhere: forbidden strings `submit_order`, `place_order`,
  `api.alpaca.markets`, `broker-api.alpaca.markets`, `tradingcore.tradier`,
  `trader.executor`, `swing.executor` in any `quant/**/*.py`
  (`data.alpaca.markets` IS allowed). INV-22.
- Free data only (Alpaca IEX daily bars, split-adjusted).
- Deterministic: no `random` without fixed seed; no wall-clock in math paths
  (timestamps injected).
- All Sharpe inference at native (daily) frequency; annualized (√252) for
  display only. Raw kurtosis convention (Normal = 3).
- Atlas conventions: `requires-python >=3.12`, ruff line-length 100,
  `.venv/bin/python -m pytest -q`, dbmate migrations (max+1 numbering,
  re-check at push), conventional commits, CHANGELOG.md append per session,
  glossary entry per user-visible term.
- ai-server conventions: skills staged in atlas `integrations/ai-server/`
  first, byte-identical copy; `python scripts/lint_docs.py` must PASS;
  `isolation: workspace` for both skills (frozen-allowlist trap).
- Repos: atlas dev `~/Documents/repos/atlas` (push GitHub `Piserchia/atlas`
  `master`, rebase before start AND before push); ai-server dev
  `~/Documents/repos/ai-server` (merge `origin/main` before push).

---

### Task 1: Vertical scaffold + turn-on switch + no-order tripwire

**Files:**
- Create: `atlas/quant/pyproject.toml`, `atlas/quant/CLAUDE.md`,
  `atlas/quant/config/{settings.yaml,universe.yaml,roster.yaml}`,
  `atlas/quant/quantlab/__init__.py`, `atlas/quant/quantlab/settings.py`,
  `atlas/quant/evaluation/{PROTOCOL.md,LEDGER.md}`,
  `atlas/quant/evaluation/trials.jsonl` (empty file),
  `atlas/quant/reports/.gitkeep`, `atlas/quant/tests/__init__.py`
- Modify: `atlas/.gitignore` (add `quant/.cache/`),
  `atlas/manifest.yml` (gate row), `atlas/scripts/install-venv-sitecustomize.sh`
  (append `quant/.venv`)
- Test: `atlas/quant/tests/test_reports_only.py`,
  `atlas/quant/tests/test_switch.py`

**Interfaces (Produces):**
- `quantlab.settings.load_settings(path=None) -> dict` (defaults from
  `config/settings.yaml` relative to package root; `path` overrides)
- `quantlab.settings.is_enabled(settings) -> bool`
- `quantlab.QuantError(Exception)` in `quantlab/__init__.py`

Settings file content:

```yaml
enabled: true
costs: {fee_bps: 5.0, slip_bps: 3.0}
dsr_threshold: 0.95
walk_forward: {train_days: 180, test_days: 60, embargo_frac: 0.01}
health: {decay_factor: 0.5, windows: [30, 60]}
sizing: {risk_per_trade: 0.01, max_position_frac: 0.20}
data: {feed: iex, start: "2016-01-04"}
```

`universe.yaml`: `version: 1`, `asof: "2026-09-16"`, `point_in_time: false`,
`survivorship_note` (current-day list, delisted names absent, momentum
E-0026 citation), `benchmark: SPY`,
`groups: {core_etfs: [SPY, QQQ, IWM], megacaps: [AAPL, MSFT, NVDA, AMZN, GOOGL]}`.

`roster.yaml` entries (idea, strategy, symbols, params):
Q-0000 buy_hold [SPY] {}; Q-0001 sma_gate [SPY] {window: 200};
Q-0002 rsi2_meanrev [SPY, QQQ, IWM] {buy_below: 10.0, exit_above: 60.0};
Q-0003 donchian_breakout [AAPL, MSFT, NVDA, AMZN, GOOGL] {entry: 20, exit: 10}.

`CLAUDE.md` Rule 1 (mirrors value/CLAUDE.md): "THIS VERTICAL NEVER PLACES
ORDERS — no order-capable code path; imports only
`tradingcore.alpaca_data`/`tradingcore.env`; `tests/test_reports_only.py`
greps enforce this mechanically. A PASS verdict is a memo to the owner —
nothing auto-promotes into any trading vertical." Plus: owner-owned files
(CLAUDE.md, PROTOCOL.md, settings.yaml thresholds, this rule), write surface
(`quant/**`), bootstrap (`python3.12 -m venv .venv && .venv/bin/pip install
-e '.[dev]'`), test command, switch operation (3 layers).

`evaluation/PROTOCOL.md` (child of `momentum/evaluation/PROTOCOL.md`):
trial accounting (one line per variant BEFORE its report, `verdict:
"logged"`, report R-#### is verdict-of-record), evidence standards
(costs ≥ 3 bps/side + slippage always on, walk-forward worst-fold
judgment, DSR > 0.95 for PASS, N = lifetime line count, V from recorded
`sr_native` values), determinism, learning channels, what stays human
(thresholds, roster additions beyond agents' proposals, any order path —
never).

- [ ] **Step 1: Scaffold dirs/files above; write failing tests**

```python
# tests/test_reports_only.py
import pathlib, re
FORBIDDEN = ["submit_order", "place_order", "api.alpaca.markets",
             "broker-api.alpaca.markets", "tradingcore.tradier",
             "trader.executor", "swing.executor"]
def test_no_order_surface():
    root = pathlib.Path(__file__).resolve().parents[1]
    hits = []
    for p in root.rglob("*.py"):
        if ".venv" in p.parts or ".cache" in p.parts: continue
        text = p.read_text()
        for f in FORBIDDEN:
            if f in text and p.name != "test_reports_only.py":
                hits.append(f"{p}:{f}")
    assert hits == []

# tests/test_switch.py
from quantlab.settings import load_settings, is_enabled
def test_enabled_by_default(): assert is_enabled(load_settings()) is True
def test_disabled(tmp_path):
    p = tmp_path / "s.yaml"; p.write_text("enabled: false\n")
    assert is_enabled(load_settings(p)) is False
def test_missing_key_fails_closed(tmp_path):
    p = tmp_path / "s.yaml"; p.write_text("costs: {}\n")
    assert is_enabled(load_settings(p)) is False
```

- [ ] **Step 2:** `cd atlas/quant && python3.12 -m venv .venv && .venv/bin/pip install -e '.[dev]'` then `.venv/bin/python -m pytest -q` — expect FAIL (no settings module).
- [ ] **Step 3:** Implement `settings.py` (yaml load, merge over defaults dict, `is_enabled` = `settings.get("enabled") is True`).
- [ ] **Step 4:** pytest green; run `bash scripts/install-venv-sitecustomize.sh` after appending `quant/.venv` to its list; verify `sitecustomize.py` exists in the venv.
- [ ] **Step 5:** Commit `feat(quant): scaffold validation-desk vertical — switch, tripwire, protocol`.

### Task 2: metrics.py

**Files:** Create `atlas/quant/quantlab/metrics.py`; Test `atlas/quant/tests/test_metrics.py`

**Interfaces (Produces):**
- `sharpe_native(returns: list[float]) -> float` — mean/stdev ddof=1; raises `QuantError` if len<2 or stdev==0
- `annualize_sharpe(sr_native, periods=252) -> float`
- `max_drawdown(equity: list[float]) -> float` — returns ≤ 0 (canonical `min(E/peak − 1)`)
- `longest_underwater(equity) -> tuple[int, bool]` — (trading days, censored) censored=True if final spell unrecovered
- `cagr(equity, periods=252) -> float`
- `calmar(equity, periods=252) -> float` — cagr/|mdd|; raises `QuantError` if mdd == 0
- `moments(returns) -> tuple[float, float]` — (skew g3, RAW kurtosis g4) via population moments; Normal → g4≈3
- `summary(returns, equity) -> dict` — all of the above keyed
  `{sharpe_native, sharpe_annual, vol_annual, mdd, underwater_days,
  underwater_censored, cagr, calmar, skew, kurt_raw, n_obs}`

- [ ] **Step 1: Failing tests with exact vectors**

```python
def test_sharpe_exact():
    r = [0.01, -0.005, 0.02, 0.0, 0.007]   # mean=0.0064, stdev(ddof=1)=0.009423375...
    import statistics
    assert abs(sharpe_native(r) - statistics.mean(r)/statistics.stdev(r)) < 1e-12
def test_mdd_and_underwater():
    eq = [100, 110, 99, 104.5, 110, 121, 115]
    assert abs(max_drawdown(eq) - (99/110 - 1)) < 1e-12   # -0.1
    days, censored = longest_underwater(eq)
    assert (days, censored) == (2, False)                  # 99, 104.5 below 110-peak
def test_underwater_censored():
    days, censored = longest_underwater([100, 120, 110, 105, 108])
    assert (days, censored) == (3, True)
def test_kurtosis_of_normal_like():
    g3, g4 = moments([1.0, -1.0]*500)                      # symmetric two-point
    assert abs(g3) < 1e-9 and abs(g4 - 1.0) < 1e-9         # two-point dist: kurt=1
```

- [ ] **Step 2:** pytest FAIL → **Step 3:** implement → **Step 4:** green → **Step 5:** Commit `feat(quant): metrics — sharpe/mdd/underwater/calmar/moments`.

### Task 3: dsr.py (Bailey–López de Prado)

**Files:** Create `atlas/quant/quantlab/dsr.py`; Test `atlas/quant/tests/test_dsr.py`

**Interfaces (Produces):**
- `psr(sr_hat, sr_star, n_obs, skew, kurt_raw) -> float`
- `expected_max_sr(n_trials, var_trial_sr) -> float` — raises `QuantError`
  on n_trials < 1 or var < 0; returns 0.0 when n_trials == 1
- `deflated_sharpe(returns, n_trials, var_trial_sr) -> DsrResult` —
  frozen dataclass `{sr_native, sr_annual, sr0, dsr, passed, caveats: tuple}`;
  raises on n_trials <= 0; caveat string appended when n_trials < 10
  ("E[max SR] under-corrects for N<10")

Implementation core (use exactly this math; `NormalDist` from statistics):

```python
from statistics import NormalDist
_N = NormalDist()
EULER_GAMMA = 0.5772156649

def psr(sr_hat, sr_star, n_obs, skew, kurt_raw):
    denom = math.sqrt(1 - skew*sr_hat + ((kurt_raw - 1)/4)*sr_hat**2)
    return _N.cdf((sr_hat - sr_star) * math.sqrt(n_obs - 1) / denom)

def expected_max_sr(n_trials, var_trial_sr):
    if n_trials == 1: return 0.0
    return math.sqrt(var_trial_sr) * (
        (1 - EULER_GAMMA) * _N.inv_cdf(1 - 1/n_trials)
        + EULER_GAMMA * _N.inv_cdf(1 - 1/(n_trials*math.e)))
```

- [ ] **Step 1: Failing tests — the paper's worked example is the golden**

```python
def test_paper_worked_example():
    # Bailey & Lopez de Prado 2014, p.10: N=100, V=1/500 (daily), T=1250,
    # g3=-3, g4=10 (raw), daily SR=2.5/sqrt(250) -> DSR ~= 0.9004
    sr_hat = 2.5 / math.sqrt(250)
    sr0 = expected_max_sr(100, 1/500)
    assert abs(sr0 - 0.1132) < 0.0005
    val = psr(sr_hat, sr0, 1250, -3.0, 10.0)
    assert abs(val - 0.9004) < 0.002
def test_fail_closed_on_zero_trials():
    with pytest.raises(QuantError): expected_max_sr(0, 0.001)
def test_single_trial_is_pure_psr():
    assert expected_max_sr(1, 0.5) == 0.0
def test_small_n_caveat():
    res = deflated_sharpe([0.01, -0.002, 0.004]*50, n_trials=3, var_trial_sr=0.001)
    assert any("under-correct" in c for c in res.caveats)
```

- [ ] **Step 2:** FAIL → **Step 3:** implement (`deflated_sharpe` composes
  `metrics.sharpe_native` + `metrics.moments` + the two functions above,
  `passed = dsr > threshold` left to caller — result carries raw dsr) →
  **Step 4:** green → **Step 5:** Commit `feat(quant): deflated Sharpe (PSR/E[maxSR]/DSR), paper-verified`.

### Task 4: engine.py + strategies.py

**Files:** Create `atlas/quant/quantlab/engine.py`, `atlas/quant/quantlab/strategies.py`;
Test `atlas/quant/tests/test_engine.py`, `atlas/quant/tests/test_strategies.py`

**Interfaces (Produces):**
- `EngineConfig` frozen dataclass: `capital=100_000.0, fee_bps=5.0, slip_bps=3.0, max_leverage=1.0`
- `run_backtest(closes: dict[str, list[float]], dates: list[str], target_weights: dict[str, list[float]], cfg: EngineConfig) -> BacktestResult`
- `BacktestResult` frozen dataclass: `dates, returns (net, len T, returns[0]=0.0), gross_returns, equity (equity[0]=capital), turnover, weights_effective: dict[str, list[float]], cost_drag_annual_bps: float`
- Strategy functions, each `(closes: list[float], **params) -> list[float]`
  (per-bar target weight for ONE symbol, computed from data ≤ t):
  `buy_hold`, `sma_gate(window=200)`, `rsi2_meanrev(buy_below=10.0,
  exit_above=60.0, period=2)` (Wilder RSI), `donchian_breakout(entry=20, exit=10)`
- `REGISTRY: dict[str, callable]` mapping roster names to functions
- `portfolio_weights(closes_by_sym, strategy_fn, params) -> dict[str, list[float]]`
  — applies per symbol, scales by 1/n_symbols

**Engine semantics (the shift(1) law — implement exactly):**
`w_eff[s][t] = target[s][t-1]` for t ≥ 1; `w_eff[s][0] = 0`.
`r_gross[t] = Σ_s w_eff[s][t]·(c[s][t]/c[s][t-1] − 1)` for t ≥ 1.
`turnover[t] = Σ_s |w_eff[s][t] − w_eff[s][t-1]|` (turnover[0]=0).
`cost[t] = turnover[t]·(fee_bps+slip_bps)/1e4`. `r_net = r_gross − cost`.
If `Σ_s |w_eff[s][t]| > max_leverage`, scale that day's weights down
proportionally. Equity compounds `equity[t] = equity[t-1]·(1+r_net[t])`.

- [ ] **Step 1: Failing tests**

```python
def test_hand_computed_two_days():
    closes = {"A": [100.0, 110.0, 99.0]}; dates = ["d0","d1","d2"]
    tw = {"A": [1.0, 1.0, 1.0]}
    cfg = EngineConfig(fee_bps=5, slip_bps=3)
    r = run_backtest(closes, dates, tw, cfg)
    # day1: w_eff=tw[0]=1 -> gross 0.10, turnover |1-0|=1 -> cost 8e-4
    assert abs(r.returns[1] - (0.10 - 0.0008)) < 1e-12
    # day2: gross = 99/110-1 = -0.1, turnover 0
    assert abs(r.returns[2] - (-0.1)) < 1e-12

def test_peeking_signal_gains_nothing():
    # signal that "knows" tomorrow's return sign, applied THROUGH the engine lag,
    # must equal an honestly lagged copy of itself — position on bar t comes
    # from target[t-1] regardless of how target was built.
    closes = {"A": [100, 101, 99, 103, 102, 105]}
    dates = [f"d{i}" for i in range(6)]
    peek = [1.0 if closes["A"][min(t+1,5)] > closes["A"][t] else 0.0 for t in range(6)]
    r = run_backtest(closes, dates, {"A": peek}, EngineConfig(fee_bps=0, slip_bps=0))
    manual = 1.0
    for t in range(1, 6):
        manual *= 1 + peek[t-1] * (closes["A"][t]/closes["A"][t-1] - 1)
    assert abs(r.equity[-1]/r.equity[0] - manual) < 1e-12

def test_leverage_cap():
    r = run_backtest({"A":[100,100,100]}, ["a","b","c"], {"A":[2.0,2.0,2.0]},
                     EngineConfig(max_leverage=1.0, fee_bps=0, slip_bps=0))
    assert max(abs(w) for w in r.weights_effective["A"]) <= 1.0 + 1e-12

def test_sma_gate_no_lookahead():
    closes = list(range(100, 400))          # rising
    w = sma_gate([float(c) for c in closes], window=10)
    assert w[:10] == [0.0]*10               # no signal before window filled
    assert w[-1] == 1.0
```

- [ ] **Step 2:** FAIL → **Step 3:** implement engine + 4 strategies
  (strategies emit 0.0 until their lookback is filled — never a partial-window
  value) → **Step 4:** green → **Step 5:** Commit
  `feat(quant): backtest engine (shift-1 law, turnover costs) + 4 reference strategies`.

### Task 5: walkforward.py

**Files:** Create `atlas/quant/quantlab/walkforward.py`; Test `atlas/quant/tests/test_walkforward.py`

**Interfaces (Produces):**
- `make_folds(n_obs, train=180, test=60, embargo_frac=0.01) -> list[Fold]`
  — `Fold` frozen dataclass `{train_start, train_end, test_start, test_end}`
  (half-open index ranges); folds tile the tail: first test starts at
  `train`; last partial test window < 30 obs is dropped
- `walk_forward(closes_by_sym, dates, strategy_fn, params, cfg, settings) -> WfResult`
  — per fold: build weights from `closes[:test_end]` (signal warmup =
  full history up to fold; fixed-rule strategies, no refit), score net
  returns ONLY on `[test_start, test_end)`; embargo: skip
  `int(embargo_frac * n_obs)` obs after each test block before the next
  fold's scoring may begin
- `WfResult` frozen: `folds: list[FoldMetrics{start_date, end_date,
  sharpe_native, ret, mdd}]`, `positive_folds: int`, `n_folds: int`,
  `worst_fold: FoldMetrics` (min sharpe), `oos_returns: list[float]`
  (concatenated), `oos_sharpe_native: float`

- [ ] **Step 1: Failing tests**

```python
def test_fold_construction():
    folds = make_folds(400, train=180, test=60, embargo_frac=0.0)
    assert folds[0].test_start == 180 and folds[0].test_end == 240
    assert folds[1].test_start == 240
    assert all(f.test_end <= 400 for f in folds)
def test_embargo_gap():
    folds = make_folds(1000, train=180, test=60, embargo_frac=0.01)  # embargo 10
    assert folds[1].test_start == folds[0].test_end + 10
def test_worst_fold_is_min():
    # constant-up series then crash in one fold: worst fold must be the crash fold
    closes = [100 + i for i in range(240)] + [340 - 2*i for i in range(60)] + [220 + i for i in range(100)]
    res = walk_forward({"A": [float(c) for c in closes]},
                       [f"d{i}" for i in range(len(closes))],
                       REGISTRY["buy_hold"], {}, EngineConfig(fee_bps=0, slip_bps=0),
                       {"walk_forward": {"train_days": 180, "test_days": 60, "embargo_frac": 0.0}})
    assert res.worst_fold.sharpe_native == min(f.sharpe_native for f in res.folds)
    assert res.worst_fold.ret < 0
```

- [ ] **Step 2:** FAIL → **Step 3:** implement → **Step 4:** green →
  **Step 5:** Commit `feat(quant): walk-forward folds + worst-fold judgment + embargo`.

### Task 6: leakage.py (the critic)

**Files:** Create `atlas/quant/quantlab/leakage.py`; Test `atlas/quant/tests/test_leakage.py`

**Interfaces (Produces):**
- `Check` frozen dataclass `{name: str, status: str, evidence: str}` — status ∈ {"PASS","FLAG","FAIL"}
- `run_critic(closes_by_sym, dates, universe_meta: dict, strategy_fn, params,
  cfg, bench_closes: list[float]) -> list[Check]` — exactly 8 checks named
  `look_ahead, survivorship, repainting, costs, fills, parameter_count,
  regime_coverage, alignment`
- `label_regimes(bench_closes, window=200) -> list[str]` — per-bar
  "bull" (close > sma), "bear" (close < sma and sma[t] < sma[t-1]), else "chop";
  first `window` bars "warmup"

Check logic (implement exactly):
1. `look_ahead`: at t ∈ {25%, 50%, 75% of T}: `strategy_fn(closes[:t+1])[t] ==
   strategy_fn(closes)[t]` per symbol → mismatch = FAIL.
2. `survivorship`: `universe_meta.get("point_in_time") is True` → PASS else
   FLAG citing `survivorship_note`.
3. `repainting`: with `h = strategy_fn(closes)`, for t = 75% of T:
   `strategy_fn(closes[:t+1])[i] == h[i]` for all i ≤ t − mismatch = FAIL
   ("indicator rewrites its history").
4. `costs`: `cfg.fee_bps + cfg.slip_bps > 0` else FAIL; evidence = final
   equity at 0×/1×/2× cost multipliers.
5. `fills`: engine marks at closes by construction; verify every close within
   its bar's [low, high] when bars provided; PASS with evidence string.
6. `parameter_count`: `len(params) > 5` → FLAG; evidence "k=… T=…".
7. `regime_coverage`: regimes present in the scored window (via
   `label_regimes(bench_closes)`); < 2 distinct of {bull,bear,chop} → FLAG;
   evidence lists counts.
8. `alignment`: dates strictly increasing + unique + equal length across
   symbols → else FAIL; evidence = lengths.

- [ ] **Step 1: Failing tests — every check catches a seeded violation AND passes a clean control**

```python
def _clean():   # 300 bars, benign
    closes = {"A": [100*1.001**i for i in range(300)]}
    dates = [f"2024-{i:04d}" for i in range(300)]
    return closes, dates
def test_look_ahead_catches_peeker():
    closes, dates = _clean()
    def peeker(cs, **p):   # uses last close for every bar — future data
        return [1.0 if cs[-1] > cs[0] else 0.0 for _ in cs]
    checks = {c.name: c for c in run_critic(closes, dates, {"point_in_time": False},
              peeker, {}, EngineConfig(), closes["A"])}
    assert checks["look_ahead"].status == "FAIL"
def test_clean_control_passes():
    closes, dates = _clean()
    checks = {c.name: c for c in run_critic(closes, dates, {"point_in_time": True},
              REGISTRY["sma_gate"], {"window": 50}, EngineConfig(), closes["A"])}
    assert checks["look_ahead"].status == "PASS"
    assert checks["repainting"].status == "PASS"
    assert checks["survivorship"].status == "PASS"
    assert checks["costs"].status == "PASS"
def test_zero_costs_fail():
    closes, dates = _clean()
    checks = {c.name: c for c in run_critic(closes, dates, {}, REGISTRY["buy_hold"],
              {}, EngineConfig(fee_bps=0.0, slip_bps=0.0), closes["A"])}
    assert checks["costs"].status == "FAIL"
def test_misaligned_dates_fail():
    checks = {c.name: c for c in run_critic({"A":[1.0,2.0],"B":[1.0]}, ["a","b"],
              {}, REGISTRY["buy_hold"], {}, EngineConfig(), [1.0,2.0])}
    assert checks["alignment"].status == "FAIL"
def test_one_regime_flags():
    closes, dates = _clean()   # monotonic rise = bull only
    checks = {c.name: c for c in run_critic(closes, dates, {}, REGISTRY["buy_hold"],
              {}, EngineConfig(), closes["A"])}
    assert checks["regime_coverage"].status == "FLAG"
```

- [ ] **Step 2:** FAIL → **Step 3:** implement → **Step 4:** green →
  **Step 5:** Commit `feat(quant): the critic — 8 leakage checks with seeded-violation tests`.

### Task 7: sizing.py + health.py

**Files:** Create `atlas/quant/quantlab/sizing.py`, `atlas/quant/quantlab/health.py`;
Test `atlas/quant/tests/test_sizing.py`, `atlas/quant/tests/test_health.py`

**Interfaces (Produces):**
- `fixed_fractional(equity, entry, stop, risk_frac=0.01, max_position_frac=0.20) -> dict`
  `{units, notional, risk_amount, capped: bool}`; raises `QuantError` if stop == entry
- `loss_streak_table(risk_fracs=(0.01, 0.02, 0.05), streak=12) -> list[dict]`
  `{risk_frac, drawdown_after_streak}` — geometric: `1 − (1−f)^12`
- `vol_target_leverage(returns, target_annual=0.10, span=20, periods=252) -> float`
  — EWMA vol → `min(target/vol_hat, 3.0)` cap
- `health_checks(backtest: dict, recent_returns: list[float],
  settings: dict) -> list[Check]` (reuses `leakage.Check`) — per window w in
  `settings["health"]["windows"]`: `sharpe_decay_{w}` HALT if
  `sharpe_native(recent[-w:]) < decay_factor × backtest["sharpe_native"]`
  (only when backtest sharpe > 0 and len(recent) ≥ w, else status "SKIP");
  `drawdown_exceedance` HALT if trailing |DD| of recent window >
  `|backtest["mdd"]|`; statuses here ∈ {"OK","HALT","SKIP"}
- `kill_conditions(backtest: dict, settings) -> list[str]` — human-readable
  pre-committed kill lines embedded in every PASS report

- [ ] **Step 1: Failing tests**

```python
def test_fixed_fractional_exact():
    r = fixed_fractional(100_000, entry=50.0, stop=45.0, risk_frac=0.01)
    assert r["units"] == 200 and r["risk_amount"] == 1000.0 and not r["capped"]
def test_position_cap():
    r = fixed_fractional(100_000, entry=50.0, stop=49.9, risk_frac=0.01)
    assert r["capped"] and r["notional"] <= 20_000.0 + 1e-9
def test_streak_table():
    rows = {r["risk_frac"]: r for r in loss_streak_table()}
    assert abs(rows[0.01]["drawdown_after_streak"] - (1 - 0.99**12)) < 1e-12  # ~11.36%
    assert abs(rows[0.05]["drawdown_after_streak"] - (1 - 0.95**12)) < 1e-12  # ~45.96%
def test_sharpe_decay_halt():
    bt = {"sharpe_native": 0.10, "mdd": -0.20}
    flat = [0.0001]*100; bad = [-0.01]*30 + [0.01]*0
    s = {"health": {"decay_factor": 0.5, "windows": [30]}}
    ok = {c.name: c for c in health_checks(bt, flat, s)}
    halt = {c.name: c for c in health_checks(bt, bad, s)}
    assert ok["sharpe_decay_30"].status == "OK"
    assert halt["sharpe_decay_30"].status == "HALT"
```

- [ ] **Step 2:** FAIL → **Step 3:** implement → **Step 4:** green →
  **Step 5:** Commit `feat(quant): sizing math + production health checks (pre-committed kills)`.

### Task 8: trials.py + data.py + report.py + cli.py

**Files:** Create `atlas/quant/quantlab/{trials.py,data.py,report.py,cli.py}`;
Test `atlas/quant/tests/{test_trials.py,test_data.py,test_report.py,test_cli.py}`

**Interfaces (Produces):**
- `trials.append_trial(path, *, idea, name, family, params, verdict="logged",
  note="", sr_native=None, ts=None) -> dict` — appends one JSON line
  `{ts, idea, name, family, params_hash, verdict, note, sr_native}`;
  `params_hash = sha256(canonical-json)[:12]`; ts injected (ISO UTC)
- `trials.lifetime_n(path) -> int` — raises `TrialsError` if missing/empty
- `trials.trial_sr_variance(path) -> float` — variance (ddof=1) of all
  non-null `sr_native`; raises if < 2 values
- `data.fetch_daily_bars(symbols, start, end, cache_dir, feed="iex",
  client=None) -> dict[str, list[bar]]` — client defaults to
  `tradingcore.alpaca_data.DataClient()` (imported lazily so tests run
  without creds); cache file `{sha256(symbols|start|end|feed)[:16]}.json`
  under cache_dir, returned verbatim when present; writes sibling
  `.manifest.json` `{symbols, start, end, feed, fetched_at, sha256, rows}`
- `data.closes(bars_by_sym) -> tuple[dict[str, list[float]], list[str]]` —
  intersect dates across symbols (inner join, sorted), extract closes
- `report.next_report_id(reports_dir) -> str` — "R-0001"-style max+1
- `report.write_report(reports_dir, *, rid, idea, strategy, params, symbols,
  window, metrics_summary, dsr_result, wf_result, checks, kills, provenance,
  settings) -> pathlib.Path` — writes `R-####/report.md`, `metrics.json`,
  `manifest.json`. Verdict law: `PASS` iff `dsr > dsr_threshold` AND
  `worst_fold.sharpe_native > 0` AND no critic FAIL; `REJECT` otherwise
  (FLAGs listed as caveats). report.md sections: `## Verdict`,
  `## The statistician` (N, V, SR0, DSR, PSR-vs-0), `## Walk-forward`
  (folds table + worst), `## The critic` (8 rows), `## Risk & sizing`
  (streak table + kill conditions), `## Caveats & provenance`
- `cli` subcommands (argparse, `python -m quantlab.cli …`):
  `preflight` (prints `ARMED` or `DISARMED — enabled: false`, exit 0;
  exit 3 on missing creds when enabled), `validate --idea --strategy
  --symbols --params-json [--start --end]` (full pipeline for one entry),
  `sweep` (roster.yaml → validate each; SKIPS everything with one DISARMED
  line when disabled), `health` (health pass over every prior PASS report,
  writes `reports/health-YYYY-MM-DD.json`)

Pipeline order inside `validate` (the honesty law): fetch bars →
build weights → full-window backtest + metrics → **append trial line
(sr_native, verdict "logged")** → walk-forward → critic → DSR with
`n_trials = lifetime_n(...)` and `var = trial_sr_variance(...)` (single
recorded-sr fallback: `QuantError` → report BLOCKED line and REJECT) →
write report → LEDGER entry appended (`## [R-####] VALIDATION <ts>` +
verdict line).

- [ ] **Step 1: Failing tests**

```python
def test_trials_roundtrip(tmp_path):
    p = tmp_path/"trials.jsonl"
    append_trial(p, idea="Q-0001", name="sma200", family="trend",
                 params={"window":200}, sr_native=0.05, ts="2026-09-16T00:00:00Z")
    append_trial(p, idea="Q-0002", name="rsi2", family="meanrev",
                 params={"buy_below":10}, sr_native=0.01, ts="2026-09-16T00:00:01Z")
    assert lifetime_n(p) == 2
    assert trial_sr_variance(p) > 0
def test_lifetime_n_fails_closed(tmp_path):
    with pytest.raises(TrialsError): lifetime_n(tmp_path/"missing.jsonl")
def test_data_cache_roundtrip(tmp_path):
    calls = []
    class FakeClient:
        def get_daily_bars(self, symbols, start, end, feed="iex"):
            calls.append(1)
            return {s: [{"t":"2026-01-02T05:00:00Z","o":1,"h":2,"l":0.5,"c":1.5,"v":10}] for s in symbols}
    a = fetch_daily_bars(["SPY"], dt.date(2026,1,1), dt.date(2026,1,3), tmp_path, client=FakeClient())
    b = fetch_daily_bars(["SPY"], dt.date(2026,1,1), dt.date(2026,1,3), tmp_path, client=FakeClient())
    assert a == b and len(calls) == 1                     # second hit served from cache
    assert list(tmp_path.glob("*.manifest.json"))
@pytest.mark.alpaca
def test_live_alpaca_smoke():
    # Requires atlas .env creds; skipped otherwise (marker registered in pyproject).
    bars = fetch_daily_bars(["SPY"], dt.date(2026,8,3), dt.date(2026,8,7),
                            pathlib.Path("/tmp/quant-live-test"))
    assert len(bars["SPY"]) >= 4 and {"t","o","h","l","c","v"} <= set(bars["SPY"][0])
def test_report_verdict_law(tmp_path):
    rid = next_report_id(tmp_path)                        # "R-0001" on empty dir
    path = write_report(tmp_path, rid=rid, ... , dsr_result=FAKE_DSR_096,
                        wf_result=FAKE_WF_POSITIVE_WORST, checks=CLEAN_CHECKS, ...)
    md = (tmp_path/rid/"report.md").read_text()
    assert "## Verdict" in md and "PASS" in md.split("## Verdict")[1][:80]
    mj = json.loads((tmp_path/rid/"metrics.json").read_text())
    assert mj["verdict"] == "PASS" and mj["dsr"] > 0.95
def test_cli_preflight_disarmed(tmp_path, capsys):
    # settings with enabled:false -> exit 0, prints DISARMED
```

(conftest.py registers the `alpaca` marker and auto-skips it unless
`ALPACA_KEY_ID` resolves via `tradingcore.env.resolve` — copy the swing
`pg`-marker pattern.)

- [ ] **Step 2:** FAIL → **Step 3:** implement all four modules →
  **Step 4:** full suite green (`.venv/bin/python -m pytest -q`; then once
  WITH creds: `.venv/bin/python -m pytest -q -m alpaca` must pass live) →
  **Step 5:** Commit `feat(quant): trials registry, alpaca data adapter, report writer, CLI`.
- [ ] **Step 6 (acceptance):** `.venv/bin/python -m quantlab.cli sweep` for
  real (creds from atlas `.env`): 4 roster entries → 4 reports under
  `quant/reports/R-000{1..4}/`, trials.jsonl has ≥ 4 lines, LEDGER has
  4 VALIDATION entries. Read one report end-to-end for sanity (DSR present,
  worst fold present, 8 critic rows, kill conditions). Commit artifacts:
  `research(quant): first validation sweep — R-0001..R-0004`.

### Task 9: /quant web page + glossary

**Files:**
- Create: `atlas/web/app/quant/page.tsx`, `atlas/db/migrations/00NN_glossary_quant.sql`
  (NN = current max + 1, re-check at push)
- Modify: `atlas/web/app/components/Nav.tsx` (add `["/quant", "Quant"]`),
  `atlas/glossary/terms.json` (new slugs)

**Interfaces (Consumes):** `reports/R-*/metrics.json` +
`reports/R-*/report.md` + `reports/health-*.json` written by Task 8.

Page (house patterns: `/momentum` fs-reading, `/firm` layout, tokens CSS,
`export const dynamic = "force-dynamic"`, every fs read wrapped so a missing
dir degrades to `.atlas-empty` naming the CLI that populates it):
- Header card: vertical status — settings `enabled` flag (read
  `quant/config/settings.yaml` via `node:fs` + a 20-line yaml-lite parse of
  the `enabled:` line), switch documentation line.
- Runs table (`.atlas-table`): R-id, strategy, symbols, window, Sharpe
  (annual, `.atlas-num`), DSR, worst-fold Sharpe, verdict
  badge (`.atlas-badge.gain` PASS / `.loss` REJECT).
- Critic panel for the latest run: 8 checks with PASS/FLAG/FAIL badges.
- Health panel: latest `health-*.json` rows (OK/HALT/SKIP).
- Latest memo: `<TermifiedMarkdown markdown={reportMd} />` (memo is prose —
  metrics stay in the JSX table; TermifiedMarkdown renders no md tables).
- Glossary slugs (seed + migration, `<Term>` in the page): `deflated-sharpe`,
  `probabilistic-sharpe-ratio`, `walk-forward`, `calmar-ratio`,
  `max-drawdown`, `look-ahead-bias`, `survivorship-bias`, `turnover`
  (check `terms.json` first; add only missing ones, both places).

- [ ] **Step 1:** Write page + Nav + glossary seed + migration.
- [ ] **Step 2:** `cd atlas/web && npx tsc --noEmit` — zero errors.
- [ ] **Step 3:** `dbmate --migrations-dir db/migrations up` locally (atlas
  `.env` DATABASE_URL); glossary rows present
  (`psql … "select term from glossary where term like '%sharpe%'"`).
- [ ] **Step 4:** verify-frontend pass: `npm run build && npm run start` (or
  dev server), `curl -w "%{http_code}" localhost:3000/quant` (dev port) —
  200 + grep for `R-0001` and `Deflated`; four states (loading n/a for
  server component; empty ⇒ move reports aside once; error ⇒ unreadable
  metrics.json; live); zero console warnings; evidence into `PROGRESS.md`.
- [ ] **Step 5:** Commit `feat(web): /quant — validation-desk page (runs, critic, health, memo)`.

### Task 10: skills + schedules + registries + paperwork (both repos)

**Files:**
- Create (atlas, staged): `atlas/integrations/ai-server/skills/atlas-quant-validate/{SKILL.md,GOTCHAS.md}`,
  `atlas/integrations/ai-server/skills/atlas-quant-governor/{SKILL.md,GOTCHAS.md}`
- Create (ai-server, byte-identical copies): `skills/atlas-quant-validate/…`,
  `skills/atlas-quant-governor/…`
- Modify (ai-server): `.context/SKILLS_REGISTRY.md` (2 rows),
  `.context/org/divisions/atlas/CHARTER.md` (2 roster rows),
  `scripts/seed-schedules.sh` (2 upserts), `.context/INDEX.md`
  (Additions 2026-09-16 quant block), `docs/README.md` if it indexes specs
- Modify (atlas): `atlas/CLAUDE.md` (verticals row + loops bullet),
  `atlas/evaluation/LOOP.md` (§1 stage rows, §2 single-writer rows —
  `quant/reports/** + evaluation/*` writer = atlas-quant-validate; audit
  entries writer = atlas-quant-governor; §6 ceilings: "quant thresholds,
  roster ceilings, any order path — owner"), `atlas/integrations/ai-server/README.md`
  (artifact rows + cp lines), `atlas/manifest.yml` +
  `ai-server skills/atlas-redeploy/SKILL.md` — NO: redeploy skill reads
  manifest gates; only if SKILL.md hard-codes vertical greps, mirror the
  `quant/` block there (check; the research says both are required)

Frontmatter — `atlas-quant-validate` (exact):

```yaml
name: atlas-quant-validate
description: "Atlas quant validation desk: weekly sweep of the strategy roster through the quantlab stack (engine→metrics→walk-forward→critic→DSR) producing R-#### reports. Dispatch for the atlas-quant-validate schedule/job_kind, or on demand."
model: claude-opus-5
effort: high
permission_mode: bypassPermissions
required_tools: [Read, Write, Edit, Bash, Glob, Grep]
max_turns: 60
isolation: workspace
subagents: [code-review]
post_review:
  trigger: always
role: worker
division: atlas
privilege_class: guarded-writer
context_files: ["skills/atlas-quant-validate/GOTCHAS.md"]
tags: [atlas, quant, research, scheduled-capable]
```

Body sections (required by lint: When to use / Inputs / Procedure /
Quality gate / Gotchas / Files this skill updates). Procedure: rebase pull →
venv self-heal → `python -m quantlab.cli preflight` (DISARMED ⇒ report and
stop, success) → `cli sweep` → `cli health` → `pytest -q` green →
code-review subagent on any code diff (artifact-only runs skip review) →
ONE commit (`research(quant): weekly sweep …` + `Job:` footer) → rebase →
push (one retry) → Telegram summary (verdicts, DSR, worst folds, HALTs).
Never: edit thresholds/roster ceilings/PROTOCOL/its own skill; add deps;
touch other verticals.

`atlas-quant-governor`: same frontmatter minus `subagents`/`post_review`,
`max_turns: 40`, description "adversarial audit of the quant desk", tags
`[atlas, quant, governor, scheduled-capable]`. Procedure: schedule-liveness
(validate row fired within 7d+25h; paused/missing ⇒ finding) →
trials-before-report ordering (ts comparison) → independent DSR recompute
from each new report's `metrics.json` inputs (python one-liner with
quantlab.dsr; mismatch > 1e-6 ⇒ finding) → critic FLAGs acknowledged in
memo caveats → `enabled: false` ⇒ verify last run no-op'd → AUDIT entry in
LEDGER (`## [A-####] AUDIT <ts>`) → commit/push → Telegram. Never edits
reports/config/code.

Seed rows (append near the other atlas rows; cron collision-checked against
existing rows at implementation):

```bash
upsert 'atlas-quant-validate' '10 14 * * 0' 'atlas-quant-validate' \
  'atlas-quant-validate: weekly quant validation sweep (skills/atlas-quant-validate)' \
  '{"project_slug":"atlas","session_timeout_seconds":3600}'
upsert 'atlas-quant-governor' '20 10 * * 2' 'atlas-quant-governor' \
  'atlas-quant-governor: weekly quant desk audit (skills/atlas-quant-governor)' \
  '{"project_slug":"atlas","session_timeout_seconds":1800}'
```

- [ ] **Step 1:** Author both skills in atlas staging; `cp -R` into ai-server
  `skills/`; `diff -qr` both pairs proves byte-identity.
- [ ] **Step 2:** All registry/paperwork edits above.
- [ ] **Step 3:** Gates: `cd ~/Documents/repos/ai-server && python scripts/lint_docs.py`
  PASS; `pipenv run pytest -q` green (skill-contract tests parse the new
  frontmatter); atlas `cd quant && .venv/bin/python -m pytest -q` green.
- [ ] **Step 4:** Commits: atlas `feat(quant): stage validation-desk skills +
  loop wiring`; ai-server `feat(skills): atlas-quant-validate + atlas-quant-governor
  (installed byte-identical) + schedules + registries`.

### Task 11: Deploy + live verification

- [ ] **Step 1:** atlas: `git pull --rebase origin master` → push. ai-server:
  `git fetch origin && git merge origin/main` → push.
- [ ] **Step 2:** Dispatch deploys through the legitimate gateway surface:
  read `src/runner/delivery.py` classify_trigger + `src/gateway/web.py` task
  endpoint; POST with `WEB_AUTH_TOKEN` from ai-server `.env`:
  `curl -s -X POST http://localhost:8080/api/task -H "Authorization: Bearer $TOKEN"`
  with `{"description":"deploy server"}` then, after it completes,
  `{"description":"redeploy atlas"}` (exact request shape per web.py —
  verify at implementation; fallback: psql insert into `jobs` with a
  created_by value `classify_trigger` maps to an allowed class).
- [ ] **Step 3:** Verify server deploy: job status success (psql), schedule
  rows exist unpaused with sane `next_run_at`
  (`psql assistant -c "select name, cron_expression, paused, next_run_at from schedules where name like 'atlas-quant%'"`),
  skills present in prod checkout, prod pytest was green (job summary).
- [ ] **Step 4:** Verify atlas deploy: `curl -so /dev/null -w '%{http_code}' http://localhost:8791/quant`
  → 200; `curl -s http://localhost:8791/quant | grep -o 'R-000[0-9]'` non-empty;
  deployed-sha marker advanced; migration applied in prod
  (`glossary` rows). Verify the switch live: pause+resume roundtrip via
  psql (`UPDATE schedules SET paused=true WHERE name='atlas-quant-validate'`
  → confirm → set false back), and `cli preflight` in the prod clone prints ARMED.
- [ ] **Step 5:** Trigger one real `atlas-quant-validate` job now (same
  gateway surface, description `atlas-quant-validate: first live run`) and
  confirm it completes: new R-#### committed by the job, Telegram summary
  sent, audit log written. This proves the loop end-to-end without waiting
  for Sunday.

### Task 12: Adversarial execution review

- [ ] **Step 1:** Multi-agent adversarial workflow (Workflow tool), lenses:
  (a) blueprint coverage — tweet/article component ↔ shipped artifact map,
  every gap explicit; (b) math verification — DSR/PSR/E[maxSR]/metrics
  recomputed independently against the papers + report numbers reproduced
  from committed artifacts; (c) prompt-fidelity — each clause of the owner's
  original prompt scored (tweet steps, research, documentation, plan,
  turn-on switch, thorough Alpaca-infra tests, page decision, deploy,
  adversarial analysis); (d) protocol/ceiling compliance — INV-22,
  protected paths untouched, stdlib ceiling, two-repo contract, byte-identity,
  lint/gates; (e) live-state probe — schedules, page, prod artifacts, job
  runs, switch. Verifiers must attempt to REFUTE each claimed completion.
- [ ] **Step 2:** Write findings to
  `~/Documents/repos/ai-server/docs/QUANT_STACK_ADVERSARIAL_2026-09-16.md`
  (verdict per prompt clause: MET / PARTIAL / MISSED + evidence paths),
  add to `.context/INDEX.md`, commit, push (with the usual merge dance).
- [ ] **Step 3:** Final chat report = the findings summary + owner follow-ups
  (LOOP.md `[system]` edits made under delegation, alpha-lab adoption
  decision, anything PARTIAL/MISSED).

## Self-review

- Spec coverage: §5 architecture → Tasks 1–8; §6 contracts → Tasks 2–8;
  §7 loop/switch → Tasks 1, 10, 11; §8 tests → every task carries its own;
  §9 paperwork/deploy → Tasks 9–11; adversarial requirement → Task 12. ✓
- Placeholders: none found (00NN migration number is a deliberate
  at-commit-time rule, stated as such). ✓
- Type consistency: `Check` defined once (Task 6) and reused by health
  (Task 7) and page (Task 9); `EngineConfig`/`BacktestResult` names match
  across Tasks 4–8; settings keys match Task 1's YAML everywhere. ✓
