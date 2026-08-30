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
