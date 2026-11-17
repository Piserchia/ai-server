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
- CORRECTION (G-0006): the stamp-with-no-job above is **not** scheduler
  recovery and **not** a DST/month-restricted-cron bug. It is the **D1
  provisioning pre-check** (`src/runner/main.py`, `if missing:` branch —
  sets `sched.last_run_at = now`, advances `next_run_at`, builds no Job on
  purpose). The discriminator is **`env_required` ∌ the project .env**, not
  the cron shape. Measured 2026-11-17: all 4 swing operational rows (the
  ones carrying `TRADIER_SANDBOX_TOKEN`) stamped with 0 job rows, while
  `atlas-swing-{evaluate,research}` stamped with 1 each. G-0005's 2/2-vs-0/27
  split was a coincidence of which rows carried the missing token. So DR-0012
  is misdiagnosed and **no scheduler/DST fix is owed** — don't chase it.
- D1 (2026-10-21) silently removed this governor's PRIMARY coverage source.
  Before it, every unprovisioned slot wrote a `swing.runs`
  `status='provisioning_gap'` row — the exact rows G-0001…G-0005 counted (77
  lifetime). After it a deferred slot writes **no `swing.runs` row at all**,
  so `swing.runs` reads identically (zero) for "deferred by design" and
  "worker dead" — precisely the 08-17 governor-dark ambiguity. The surviving
  evidence is OUTSIDE `swing.*`: `volumes/audit_log/schedules/<schedule_id>.jsonl`
  `schedule_deferred` events, plus one ops DM per project per UTC day
  (`notifications`). **Always pull the deferral stream before calling a zero-row
  window a dead lane** (G-0006: 37 events / 11 days proved 4 lanes healthy).
- Verify a DR's identity before citing it; the register has already drifted.
  The sandbox-token blocker is **DR-0001** (P0, filed G-0001). **DR-0005** is
  `FINNHUB_TOKEN`/PEAD, P2 — a different, lesser item. G-0004 and G-0005 both
  cited "DR-0005 (provisioning)" for the token, conflating two blockers under
  one number for two grades. `grep -o 'DR-00[0-9][0-9]' LEDGER.md | sort -u`
  for the highest number before filing a new one (swing's register, not the
  value/trader ones, which run ahead).
- Dirty-tree gate: distinguish **untracked** from **tracked-modified**. The
  cap-stop-orphan blocker (2026-11-01) was two *tracked* modifications whose
  mtimes matched a sibling's `max_turns` death minute. Long-lived untracked
  scaffolding (`AGENTS.md`, `.agents/`, `.codex/`, mtime 2026-09-30) is NOT
  that class: it blocks neither `git rebase` nor a path-scoped commit. Check
  `git status --porcelain` for a leading ` M`/`M ` before stopping, and stage
  by explicit path (never `git add -A`) so the untracked files stay out.
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
