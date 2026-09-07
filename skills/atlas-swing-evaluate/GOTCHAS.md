# atlas-swing-evaluate GOTCHAS

- Dual-row DST crons: exactly one of -edt/-est lands in-window per day;
  the sibling's off_window run row is DESIGNED coverage, not a gap.
- Realized expectancy comes from swing.orders realized_pnl only — never
  from research YAMLs or backtest JSONs (poisoned-denominator rule).
- A stopless open stock lot = kernel breach = freeze recommendation now.
- 529-as-completed killed a governor before (08-17 incident): verify your
  own psql pulls returned rows before grading "no activity".

## Query mechanics (learned G-0001, 2026-09-07)

- `swing.runs.mode` values are **`manage`** and **`screen`**, not
  "supervise"/"trade" as SKILL.md prose says. manage≈supervise (09:40 ET),
  screen≈trade (15:45 ET). Query on the real values or you get zero rows and
  mis-grade it as a gap.
- The swing DST sibling scheme is **cron-level, not row-level**: the `-edt`
  rows carry months `3-11` and `-est` rows `1-3,11,12`, so the out-of-season
  sibling produces **no job and no run row at all** — not an `off_window`
  row. Either way it is DESIGNED; use the in-season schedule alone as the
  coverage denominator. (The off_window-row phrasing above describes the
  trader vertical's scheme; don't expect those rows here.)
- ai-server `POSTGRES_DSN` is `postgresql+asyncpg://…`; psql rejects that
  scheme — strip `+asyncpg` first. Also `. ./.env` **fails** on that file
  (unquoted `SERVER_ROOT` contains a space); grep the single var out instead.
  The atlas clone's `.env` sources fine.

## Liveness sources

- Grade liveness from `assistant` **`jobs` rows** (`resolved_skill like
  '%swing%'`), never from `volumes/telemetry/schedule_adherence.json`. During
  a host outage that file simply stops regenerating and keeps reporting
  `findings: []` — a frozen watchdog artifact looks identical to a healthy
  one. Always check its `generated_at` against now before trusting it.
- A burst of many jobs across many skills inside one minute is a **catch-up
  dispatch, not recovery**. Read it as the *end marker of an outage* and go
  find the start (last job row before the gap; corroborate with `last reboot`
  — a reboot with no preceding `shutdown time` record is an unclean death).
- The schedule watchdog (`scripts/schedule-monitor.sh`) is a launchd timer on
  the same host as everything it watches, so it cannot detect whole-host
  outages. Recurring owner finding (DR-0004 / trader T-0010), not a new bug.

## Grading empties honestly

- `provisioning_gap` is NOT in LADDER.md Phase S's clean-session taxonomy
  ("halted/off_window/market_closed count as clean; crashes do not"). Score
  it **not clean** and file a DECISION-REQUEST for the owner to ratify —
  counting it would clear the shakedown bar with zero broker interaction.
  The governor escalates undefined taxonomy; it never reinterprets it.
- An empty `swing.equity_curve` makes the SPY/BIL pair **undefined**, not
  flat and not a win. Say "not computable" and rest the grade on coverage,
  liveness and the shakedown scorecard — never manufacture a comparison.
- Zero kernel breaches when zero orders ever reached a broker is a **vacuous
  zero**. Label it as such; it is not evidence the kernel works.
- `swing.strategy_state` may be empty even when the LEDGER declares stages
  (D-0001 registers S1–S5 at `stage=candidate` in prose only). PROTOCOL §4
  demotions are then un-appliable. Flag it as a DECISION-REQUEST — seeding
  those rows is an engineering act, outside the frozen governor's authority.
