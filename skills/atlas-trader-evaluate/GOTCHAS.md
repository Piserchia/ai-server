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
