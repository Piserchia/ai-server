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
- 2026-09-20: the SGOV freshness clock is the last **ROUND-LOT** print, not
  the last print. `/v2/stocks/trades/latest` (what `alpaca.get_latest_trades`
  calls) honours the consolidated-tape convention and excludes odd lots
  (condition `I`), so T-0013's "count IEX prints in the 17:00–17:31Z band"
  method OVERSTATES freshness and mispredicts: 09-18 had a print 8m10s before
  the run (inside the 10-min limit → predicts `ok`) but the row is
  `stale_data`, because that print was 4 shares and the last qualifying print
  was 34m old. Always filter `"I" not in t["c"]` before computing staleness.
  With the filter, all five sessions of T-0017's week resolve exactly.
- 2026-09-20: the paper account credits **no distributions at all**. `GET
  paper-api.alpaca.markets/v2/account/activities` (unfiltered) returned 20
  lifetime rows — 18 `FILL`, 1 `FEE`, 1 `JNLC`, **zero `DIV`** — while two
  ex-dates passed with the positions held (SGOV 09-01 $0.305×99, SPY 09-18
  $1.89×117 = $251.33 = 25bp of opening equity, never received). So
  `equity_curve.equity` is a PRICE-return series too. Check the activity feed
  before quoting any total-return comparison; `cash` sitting unchanged for
  weeks is the cheap tell.
- 2026-09-20: **correction to the 2026-09-07 F5 entry** — the benchmark
  price-vs-total-return error is NOT one-directional. Because the book itself
  receives no distributions (see above), the error flatters the book against
  **SPY** (both sides understated; the book, at ~89.5% SPY, slightly less) and
  **penalises** it against **BIL** (book understated ~22bp, BIL unaffected
  when no bill-fund ex-date falls in the window). T-0017: +10.2bp/−85.2bp on
  the price convention vs +7.6bp/−63.1bp corrected. Always state which
  convention the grade used.
- 2026-09-20: `trader.orders` rows stuck at `pending_new` are NOT missing
  data — the fills are at the broker. `GET /v2/account/activities?
  activity_types=FILL` reconciles 1:1 to `broker_order_id` with qty and price
  (T-0017: all 10 rows fully filled, SPY vwap 765.6799). Before carrying
  observable (c) as "unscorable" another week, check the broker; the
  distinction between "no data" and "unreconciled data" is the whole finding.
- 2026-09-20: a week can arrive where **neither** benchmark endpoint exists in
  `equity_curve` (T-0017: both 09-11 and 09-18 were `stale_data`). Reconstruct
  from the last IEX print before 17:31Z and VALIDATE the method on the days
  the record does contain — T-0017 reproduced `bil_close` exactly and
  `spy_close` to 0.3–1.6bp on 09-14/09-15, and reproduced T-0013's
  independently-derived 09-11 SPY mark to the cent. Say in the entry that the
  pair was rebuilt; a grade that must rebuild the mandated pair is a failing
  result on its own terms.
- 2026-09-20: BIL is thin on IEX too — **zero** prints in the 17:00–17:31Z
  band on 09-18 and 7 all session. Widen the tape query to the full day when
  pulling a BIL mark, and state the mark's age (09-18's was 1h39m stale, ≤1bp
  of distortion on an instrument that moves ~1bp/day, but say it).
- 2026-09-27: `schedules.last_run_at` is stamped when the runner **ENQUEUES**,
  not when the job finishes — so a schedule whose job was enqueued and then
  stranded prints a perfect cadence. T-0022's 09-25 paper job shows
  `last_run_at` on time while `trader.runs` has no row for the session. Build
  liveness on terminal job **status**, and add this to the weekly sweep:
  `psql assistant -c "select id,kind,status,created_at,error_message from jobs
  where status in ('queued','running') and created_at < now() - interval '3
  hours' order by created_at;"` — a `queued` row older than a few hours is a
  lost session, and nothing else in the stack reports it.
- 2026-09-27: the quota-requeue path has a publish-before-commit race.
  `src/runner/main.py:449` LPUSHes the job id to the queue HEAD *before*
  `:450-455` commits the row back to `queued`; a consumer winning that window
  reads `running` and returns at `:332-333` with **no log line and no audit
  event**. Signature: status `queued`, `error_message = "queued for quota reset
  (…)"`, `started_at` still the FIRST claim, last audit event
  `job_requeued_for_quota`. Corroborate from `volumes/logs/runner.out.log`: if a
  job RPUSHed to the TAIL after the stranding starts the instant the pause
  expires, the head entry was already consumed. Eliminate the alternatives
  cheaply — `redis-cli info server` uptime (a restart loses the list),
  `/clear` sets `cancelled` not `queued`, last `runner starting` line predating
  the stranding rules out a restart, and `reconcile.requeue_stranded_queued()`
  is **startup-only** and writes a `REQUEUE_EVENT` when it fires.
- 2026-09-27: `scripts/schedule-monitor.sh` — the watchdog installed after the
  08-17 governor-dark incident — has failed **every** scheduled run since
  2026-09-02 (`pipenv: command not found`, rc=127: `pipenv` lives at
  `~/.local/share/virtualenvs/ai-server-*/bin/pipenv`, not on the PATH line 12
  exports). Line 25 (`(( rc != 0 )) && exit 0  # not a finding`) then exits
  before the DM block, so a dead collector is indistinguishable from an
  all-clear — including the unconditional Sunday one. NEVER read the absence of
  a schedule-monitor alert as health; `tail volumes/logs/schedule-monitor.log`
  and check for `rc=0` before crediting it.
- 2026-09-27: ex-date ≠ pay-date. T-0017 asserted $251.33 of distributions
  "silently foregone" from ex-dates alone; only SGOV's $30.20 (ex 09-01, pay
  ≈09-03) was actually overdue — SPY's $221.13 (ex 09-18) pays ≈09-30. An 8×
  overstatement. Before calling a credit missing, confirm the **pay** date has
  passed, then check `GET paper-api.alpaca.markets/v2/account/activities`.
- 2026-09-27: Alpaca trade timestamps carry a VARIABLE fractional-second width
  (5 to 9 digits seen in one week), so both `fromisoformat` and a fixed-width
  regex fail. Zero-pad and truncate to exactly 6:
  `h,f=s.rstrip("Z").split("."); datetime.fromisoformat(h+"."+(f+"000000")[:6])`.
- 2026-09-27: the round-lot staleness method (F10) is now **9/9 over two
  weeks** — it predicted all 4 of T-0022's `ok`/`stale_data` outcomes exactly.
  Treat it as the settled way to explain a `stale_data` row before opening any
  new hypothesis.
- 2026-09-27: in the `assistant` DB the schedule on/off column is `paused`
  (boolean, default false) — there is NO `enabled` column. `\d schedules`
  first; add it to the list of name drifts already recorded for 2026-08-30.
- 2026-10-04: the tape endpoint silently breaks the round-lot staleness method
  on liquid symbols. `/v2/stocks/trades` returns **ascending** and truncates at
  `limit`, so a wide intraday window (13:30Z → run time) hands you a page whose
  LAST element is mid-session, not the last print. T-0027 read SPY as STALE by
  97.5/67.3/120.6 min on three sessions that were `ok` — all three pages were
  exactly 10000 rows. Tell: `len(trades) >= limit`. Fix: query a NARROW window
  (40 min before the run resolved all 5 sessions exactly) or follow
  `next_page_token`. Never trust the last element of a capped page.
- 2026-10-04: BIL and SGOV go ex on the FIRST BUSINESS DAY of the month —
  together. 2026-10-01 took BIL $0.265 and SGOV $0.305 on the same day, which
  hits the benchmark (BIL) and the book (SGOV holding) simultaneously and in
  OPPOSITE directions for the comparison. A raw-price weekly read showed BIL at
  **−20.74bp** (a T-bill fund cannot lose 21bp/wk — that IS the tell) and
  flattered the book by +32.79bp against it. Always run the
  `adjustment=all` vs `adjustment=split` diff before quoting the pair.
- 2026-10-04: when the dev clone is dirty (LOOP.md R1) the grade does NOT have
  to be lost. `git clone` origin/master to `/tmp`, author the ledger entry
  there, commit and push from that clone, and leave the shared clone untouched
  — no stash, no reset, no clean, nothing forced. Declare the deviation in the
  ledger entry so it is auditable. Losing a week's durable grade is the worse
  failure; mutating another loop's state is the forbidden one.
- 2026-10-04: to recover a decoy round's answer-key plaintext (the governor must
  publish it, and it is delivered "out-of-band" i.e. NOT in the repo), grep the
  research job's audit log on the host:
  `grep -o 'bb06cce5' volumes/audit_log/<research_job_id>.jsonl` then read
  ~1500 chars of context — the key's construction is captured verbatim in the
  `tool_use` input. ALWAYS re-hash the reconstructed plaintext and compare to
  the committed digest before publishing; a mismatch voids the round and is
  itself the finding. Corollary worth reporting every time: this means the
  "out-of-band" channel is host-local cleartext co-located with the artifacts,
  which PROTOCOL §6 forbids (T-0027 F19).
- 2026-10-04: `trader.runs.equity` is populated even on `stale_data` rows while
  `equity_curve` is NOT — so the true day-over-day equity path is always
  recoverable from `runs` when the curve has holes. Use it to re-derive the
  daily-loss breaker independently (the F12 `prior_close_equity` widening makes
  the system's own check untrustworthy). T-0027: curve 4/5 but runs 5/5.
- 2026-10-04: a zero-order rebalance day can be arithmetically CORRECT —
  reproduce `diff_to_intents` before calling it a dead code path. On a $100k
  book at 90/10, SPY's rounding gap is routinely < one $765 share (`qty=0`) and
  SGOV's < `min_order_notional` $50, so the monthly rebalance legitimately
  emits nothing. Related standing fact: `cash` has been exactly $450.10 in
  every `equity_curve` row since inception because the floor sleeve gets a flat
  10% weight and there is NO residual-cash sweep, despite the YAML comment
  claiming the floor "receives all idle/residual cash" (T-0027 F20).
- 2026-10-04: check `jobs` for OLD stranded rows every week, not just the
  graded window — T-0022's two F14 casualties were still sitting in `queued`
  ten days later and nothing in the stack reaps or alerts on them. A fixed
  finding and an unreaped one look identical unless you re-query by status
  rather than by date.
