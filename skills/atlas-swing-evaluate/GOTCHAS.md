# atlas-swing-evaluate GOTCHAS

- Dual-row DST crons: exactly one of -edt/-est lands in-window per day;
  the sibling's off_window run row is DESIGNED coverage, not a gap.
- Realized expectancy comes from swing.orders realized_pnl only — never
  from research YAMLs or backtest JSONs (poisoned-denominator rule).
- A stopless open stock lot = kernel breach = freeze recommendation now.
- 529-as-completed killed a governor before (08-17 incident): verify your
  own psql pulls returned rows before grading "no activity".
- `schedules.last_run_at` lies in TWO ways, not one. Known: it stamps at
  enqueue, so it understates lateness. New (G-0005): on scheduler recovery
  it can be stamped and `next_run_at` advanced with **no job row created
  at all** — observed 2/2 on the month-restricted DST crons
  (`atlas-swing-{supervise,trade}-edt`, `* 3-11 1-5`) vs 0/27 on
  unrestricted schedules. Both lanes then read "ran today" while dark for
  days. Grade liveness ONLY from `jobs.started_at` + terminal status.
- Before blaming swing for a coverage gap, check whether the HOST died:
  `kern.boottime`, `last reboot`/`last shutdown` (a reboot with no paired
  shutdown record = unclean stop), and `pmset -g log` (no entries at all in
  the window = host gone, not asleep). G-0005 found a 100h16m dark window
  this way. Filter `pmset -g log` with `grep -v coreaudiod` — assertion
  spam buries the real events.
- An on-host watchdog CANNOT report its own host's death — it dies with it,
  and its last log line reads green. Do not accept "control exists" or an
  organic firing as closure for a liveness finding (G-0004 closed
  F6/DR-0007 that way; G-0005 had to reopen it). Closure needs an off-host
  deadman + an induced drill.
- `schedule-monitor`'s launchd plist has `RunAtLoad false`, so after any
  reboot the watchdog stays dark until the next 07:15 local slot. Always
  state that residual dark window when grading a post-recovery week.
