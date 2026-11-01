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
- 2026-11-01 (G-0006 blocked): the dirty-tree gate is not hypothetical —
  **a sibling governor's cap-stop head-of-line blocks this one**, because
  all atlas governors share one dev clone. Signature: `atlas-trader-evaluate`
  ran 10:00–10:12 EST, wrote its finished 511-line `T-0040` grade +64 GOTCHAS
  lines to disk, then died at `terminal_reason='max_turns'` (61 turns)
  BEFORE its commit/rebase/push step. Swing's 11:00 slot then found two
  tracked modifications and had to stop. Diagnose authorship before judging:
  `jobs.terminal_reason` + `completed_at` on the sibling's job id (quoted in
  its own ledger entry header) vs the files' mtimes — matching minutes means
  cap-stop orphan, not a human mid-edit.
- Corollary: `status='completed'` + `terminal_reason='max_turns'` is the
  *orphaned-write* class — the work is complete on disk but unpublished, so
  per atlas CLAUDE.md rule 7 it does not exist. Never "help" by committing
  it: a `git add -A`/`commit -a` sweeps a sibling's unattributed grade into
  your `Swing-Grade:` footer, and `git rebase` refuses a dirty tree anyway,
  so the only paths are stash (= cleaning another loop's state, forbidden)
  or STOP. Stop, and hand the owner the one-line unblock.
- Do not write your own learnings into the atlas clone while reporting it
  dirty — that adds dirt you also cannot commit. Append them to this
  server-side GOTCHAS instead; `sync-learnings.sh` publishes it hourly to
  `origin/runtime-learnings`. Prod main commits are guarded, so do not
  commit here either — just leave the edit for the sync.
