# atlas-trader-evaluate — gotchas

Seeded 2026-08-26 at commissioning. Append mechanical lessons here; never
rewrite old entries.

- 2026-08-26: `atlas-dash` requires DATABASE_URL passed explicitly (no
  .env autoload) and runs from the dashboard venv:
  `set -a; source .env; set +a; dashboard/.venv/bin/atlas-dash ...`
  (pattern from skills/atlas-evaluate/GOTCHAS.md).
- 2026-08-30: `atlas-dash learn trader_strategist|trader_adversary` FAILS —
  `unknown expert`. The roster is the `EXPERTS` tuple in
  `dashboard/atlas_dash/knowledge.py:23-27` and the trader vertical was
  never added to it. Until that lands (LEDGER T-0005 proposal 4), record
  earned lessons verbatim in the ledger entry instead of dropping them.
- 2026-08-30: `trader.runs` has NO `started_at` column — the timestamp is
  `ts` (same for `orders` and `halts`). `equity_curve` keys on `day` (date).
  Save a round trip: `\d trader.runs` before writing the first query.
- 2026-08-30: in the `assistant` DB the columns are `schedules.name` /
  `job_kind` / `cron_expression` (NOT `kind`/`cron`) and `jobs.kind` /
  `resolved_skill` / `completed_at` (NOT `skill`/`finished_at`).
  `schedules.last_run_at` prints in local time (EDT), so a 17:30 UTC cron
  correctly shows 13:30.
- 2026-08-30: check `trader.orders` for rows stuck in a non-terminal status
  EVERY week. `open_recorded_orders` filters `status IN
  ('new','accepted','partially_filled')`, so Alpaca's `pending_new` is never
  reconciled and the row strands at `filled_qty=0`/`filled_avg_price=NULL`
  forever. Positions still reconcile (that path queries the broker, not our
  table), so runs look clean and the suite stays green — the daily report
  will NOT catch this. Query:
  `select status, count(*) from trader.orders group by 1;`
- 2026-08-30: coverage denominator = NYSE sessions AFTER
  `schedules.created_at`, not the raw calendar week. Sessions predating the
  schedule are not misses; state both numbers so the grade is honest either
  way.
- 2026-09-07: derive coverage from an INDEPENDENT NYSE session calendar, not
  from the rows that exist. A missed run leaves no row anywhere, so absence
  is invisible to every query that starts from `trader.runs`. T-0010 found a
  lost session (2026-09-04) only by listing the week's sessions first and
  diffing. Cheap confirmation that a date was a real session (read-only, no
  order path): `GET data.alpaca.markets/v2/stocks/bars?symbols=SPY&
  timeframe=1Day&adjustment=split` with the repo's `.env` creds — if a
  completed daily bar exists, the market was open.
- 2026-09-07: an IDENTICAL `schedules.last_run_at` microsecond across
  unrelated schedules is an OUTAGE signature, not a cadence — it means the
  runner restarted and drained every overdue schedule at once. Confirm the
  host with `last reboot` (a boot with NO preceding `shutdown time` = unclean
  down) and by `ls -la volumes/logs/` mtimes, which cluster at the last write
  of the old boot and the first of the new. `scripts/schedule-monitor.sh` is
  a launchd timer on the same host and detects NONE of this.
- 2026-09-07: a catch-up run is NOT a recovered run. `trader/executor.py` is
  today-only — it has no gap detection and no backfill — so the paper job
  firing late runs for *today* and leaves the missed session permanently
  absent. Never read "the schedule fired" as "the session was covered".
- 2026-09-07: the frozen benchmark pair is recorded on the WRONG convention.
  `trader/alpaca.py:148` requests `"adjustment": "split"`, so
  `equity_curve.spy_close/bil_close` are PRICE series, while CLAUDE.md rule 7
  demands SPY TOTAL RETURN (and the T-0003 harness used dividend-adjusted
  bars — different series). BIL and SGOV go ex MONTHLY on the first business
  day; SPY quarterly (Mar/Jun/Sep/Dec). Check every window for an ex-date
  before quoting the pair: a ~29bp one-day drop in BIL *and* SGOV together is
  a distribution, not a rate move. The error is one-directional and always
  flatters the book. Correct by substituting the mean of the neighbouring
  non-ex-date daily returns and SAY you did.
- 2026-09-07: `equity_curve.*_close` are 13:31 EDT PARTIAL-bar marks, not
  closes (executor runs 17:30 UTC, 2.5h before the 16:00 close; T-0008 A3).
  Book and benchmarks share the instant so relative returns are valid — but
  never call them closes and never expect them to tie to published figures.
- 2026-09-07: use the LIVE convention's backtest maxDD for PROTOCOL §4
  demotion thresholds: `v1_dailygate` **0.188521** (T-0008), NOT the
  `v1_monthend` control 0.307268 that T-0005 used. The executor runs the
  daily gate, so the correct thresholds are ~39% tighter.
- 2026-09-13: run `select status, count(*) from trader.runs where ts >= ...
  group by 1` EVERY week and treat `stale_data` as a failure, not a row.
  Coverage ("did a row appear?") and productive coverage ("did the executor
  finish its path?") are different numbers — T-0013 was 4/4 = 100% on the
  first and 1/4 = 25% on the second. Always report both.
- 2026-09-13: `stale_data` returns at executor step 5, BEFORE the kernel
  (step 7) and the equity/benchmark snapshot (step 9). So a stale session
  writes NO `equity_curve` row and NEVER evaluates `daily_loss_halt_pct` or
  `max_drawdown_kill_pct` — the book sits unguarded. Step 4 still honours
  *standing* halts; it is detection of a NEW breach that disappears. Never
  read `stale_data` as "a safe no-op".
- 2026-09-13: the usual cause of `stale_data` is `missing: ["SGOV"]`, and it
  is structural, not market conditions. `settings.yaml` uses
  `data_feed: iex` + `stale_quote_halt_minutes: 10`, and SGOV has near-zero
  IEX market share — it had ZERO IEX prints in the 17:00–17:35Z band on 2 of
  4 sessions in T-0013's week while SPY printed ~900. Confirm per session
  with `GET data.alpaca.markets/v2/stocks/trades?symbols=SGOV&
  start=<day>T17:00:00Z&end=<day>T17:35:00Z&feed=iex` and compare the last
  print time against the 17:30Z run.
- 2026-09-13: `ledgerlink.prior_close_equity` returns the last
  `equity_curve` row that EXISTS, not the previous session. Every hole in the
  curve silently widens the "daily" loss breaker's window (T-0013: 09-10's
  check measured a 5-session move against a 1-day limit). When grading, always
  recompute the true day-over-day equity path yourself before accepting
  "0 breaker trips" — the trip counter is produced by a mechanism that may
  have run on a minority of sessions.
- 2026-09-13: T-0002 observable (a) admits `stale_data` as a SATISFYING
  status, so it scores 100% in a week the executor worked once in four.
  Score it as written anyway (PROTOCOL §1 — never re-read a sealed clause to
  reach a preferred outcome, in either direction) and record the gap as a
  card-design finding + proposal. Sealed cards are never amended; a successor
  card is the only route.
- 2026-09-13: cheap ex-dividend check for the benchmark pair — pull the same
  bars twice, `adjustment=all` and `adjustment=split`, over the window. If
  the two series are identical, no distribution went ex and F5 has zero
  magnitude that week; if they differ, the split series understates total
  return. Faster and more reliable than eyeballing for a ~29bp drop.
- 2026-09-13: the skill's GOTCHAS/SKILL live in TWO places — the prod
  checkout `skills/atlas-trader-evaluate/` (where sessions write) and the
  atlas repo `integrations/ai-server/skills/atlas-trader-evaluate/` (the
  staged copy). They drift: T-0010's six appends never reached the atlas copy
  and were re-synced in T-0013. `diff` them at the start of every grade and
  re-sync as part of the ledger commit.
