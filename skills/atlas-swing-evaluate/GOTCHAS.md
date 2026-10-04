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

## Coverage denominator (learned G-0002, 2026-09-13)

- Compute coverage from `assistant` **`jobs` rows, NOT `swing.runs` rows.**
  Run rows are not 1:1 with sessions: `Executor._ensure_run_row`/`_report`
  (swing/swing/executor.py:152,168) write a row **per executor invocation**,
  with no per-slot guard. An agent that re-invokes `python -m swing.executor`
  while troubleshooting silently forges an extra "session". Observed 09-10:
  ONE `atlas-swing-trade` job produced TWO `screen` rows 20s apart (distinct
  UUIDs, identical git_sha+config_hash). Grading off run rows would have
  reported 9/8 slots — phantom over-coverage.
- Corollary: before calling a run-row count a session count, cross-check it
  against `jobs` rows for the same window. Discrepancy = re-invocation, not
  double dispatch — confirm by counting jobs in the hour.
- Order-level idempotency DOES exist (`executor.py:608`,
  `find_orders_by_tag(tag) → continue`) keyed on setup/symbol/date/index, so a
  re-run should not duplicate broker orders. But it has **never executed
  against a broker** (0 orders lifetime) — another vacuous zero. Don't cite it
  as proof re-runs are safe, and don't cry duplicate-order either; state both
  halves.

## The watchdog itself (learned G-0003, 2026-09-20)

- `volumes/telemetry/schedule_adherence.json` being stale is not a hypothetical:
  as of G-0003 it had been frozen at `2026-09-01T21:26Z` for **19 days** while
  still reporting `findings: []`. Root cause, reproduced: `pipenv` lives only in
  the project venv (`~/.local/share/virtualenvs/ai-server-*/bin/pipenv`) and is
  NOT on the PATH `scripts/schedule-monitor.sh:12` exports, so every launchd
  firing since 2026-09-02 exited **rc=127** (`rc=0 × 1, rc=127 × 15` over the
  whole log). The one success was an interactive run.
- The failure stayed invisible because `scripts/schedule-monitor.sh:25` reads
  `(( rc != 0 )) && exit 0  # collector failure … not a finding`. launchd
  therefore records exit status **0** and no owner DM is sent. **Never read
  `launchctl list`'s exit status as evidence a timer's work happened** — read
  the script's own log and the artifact's `generated_at`.
- Always check `volumes/logs/schedule-monitor.log` (not just the JSON) during
  the liveness sweep; `grep -oE "rc=[0-9]+" … | sort | uniq -c` gives the whole
  history in one line.
- `skills/atlas-firm-rollup/SKILL.md:74` consumes that artifact, so a frozen
  watchdog silently greens the firm rollup too. Widen the finding to every
  consumer, not just swing.

## Not-recurring ≠ fixed

- A finding whose failure did not repeat this week is NOT closeable. DR-0004
  (off-host watchdog) survived G-0002 only because the host stayed up — the
  control is still absent, only the failure is. Close findings on evidence
  that the control exists, never on a quiet week.

## The dirty-tree precondition (learned 2026-09-27, G-0004 NOT written)

- The shared clone `~/Documents/repos/atlas` is shared with the **trader**
  governor, which runs Sundays ~11:00 ET — i.e. **immediately before** this
  skill's 12:00 ET slot. 2026-09-27: job `b62a387d` (atlas-trader-evaluate)
  ran 15:00–15:23Z, wrote a complete 756-line T-0022 grade, and **exited
  without committing**. The swing governor then found a dirty tree and, per
  its own precondition, could not write G-0004. Expect this collision; check
  `git log --oneline -3` + `git status` mtimes against the sibling's audit log
  (`volumes/audit_log/<id>.jsonl` first/last ts) to identify the owner.
- The precondition is **operationally real, not ceremonial**: even committing
  only `swing/evaluation/LEDGER.md` by pathspec still leaves the mandated
  "rebase, push" step blocked, because `git pull --rebase` refuses to run with
  uncommitted changes and the only way through is to stash the sibling's work
  — which is exactly the forbidden "clean up someone else's state".
- Correct action: **STOP the write, but still do the full read-only evidence
  pull and liveness sweep**, and report the grade in the final message with
  the orphaned sibling work as the TOP owner-attention item. A silent stop
  loses two grades; an evidenced stop loses none of the findings. Never commit
  another governor's unreviewed output under your own `Swing-Grade:` footer.
- Do NOT write the ledger entry and leave it uncommitted "so it isn't lost" —
  that adds a 4th dirty file and invites the next agent to sweep your grade
  into their commit. Leave `swing/` provably clean and say so.
- Corollary on convergence: two governors independently hitting the same
  infrastructure defect in the same hour (here, the 22/22 rc=127 watchdog —
  swing F6/DR-0007 and trader F15) is **corroboration, not duplication**.
  Report it as two independent detections; it raises the priority.

## The precondition is now a measured DoS (learned 2026-10-04, G-0004 again NOT written)

- **2 of 2 consecutive scheduled grades have been lost to the dirty-tree
  precondition** (09-27 and 10-04), i.e. three calendar weeks with no ledger
  grade since G-0003. The rule is correct as a safety rule and has become a
  **denial-of-service on the governor function**. Say that out loud in the
  grade; it is a finding about the skill, not an excuse.
- It is NOT always a sibling governor. 10-04 the trader behaved (T-0027
  committed+pushed as `8193ef4` *before* this slot). The dirty state was
  instead two **orphaned writeback/build artifacts**: `M CHANGELOG.md` (a
  redundant entry for build job `c3fa7845` whose real entry already landed on
  origin at a *different path* — `dashboard/atlas_dash/fundamentals.py`, not
  the `engine/stocks/...` paths the orphan claims) plus untracked `.agents/`,
  `.codex/`, `AGENTS.md` from job `2842fbca`, whose CHANGELOG entry **is
  committed** while the files it documents were never `git add`ed.
- That orphan class **recurs**: `git stash list` showed
  `stash@{0}: scout-rescue: prior alpha-governor .agents/.codex uncommitted
  work (job af787ec7 parked)` — the same scaffold had already been rescued
  once and reappeared. Expect the shared clone to accumulate orphans
  continuously, so expect the precondition to fire most weeks.
- **Check `git status --porcelain -- swing/` separately from the whole-tree
  status.** On 10-04 `swing/` was *provably clean* while the tree was dirty —
  i.e. a path-scoped precondition would have let the grade through. Report
  both facts; the gap between them is the evidence for the DR.
- Always diff the orphan against `origin/master` before calling it lost work:
  `git show origin/master:CHANGELOG.md | grep -c '<headline>'`. Beware
  `grep -c` returning 0 → exit 1, which silently breaks an `&&` chain.
- The clone also drifts **behind** (10-04: 16 behind, 2 ahead with unpushed
  `Write-back for …` commits). Being behind matters for grading substance:
  the C-0004 research RESULT had landed on origin and was absent locally.
  Read evidence with `git show origin/master:<path>` — read-only, needs no
  rebase, and cannot disturb the dirty tree.
- The ai-server-side GOTCHAS/CHANGELOG append is **always still available**:
  it is a different repo (production checkout, runtime-learnings lane,
  auto-published by `sync-learnings.sh`). A blocked atlas write never means
  the session has nothing to record.
