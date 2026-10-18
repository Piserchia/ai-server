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

## 3 of 3 — the DoS is now the headline finding (2026-10-11, G-0004 still NOT written)

- **Three consecutive scheduled grades lost** to the dirty-tree precondition
  (09-27, 10-04, 10-11) — **four calendar weeks with no ledger grade since
  G-0003 (2026-09-20)**. All three governor jobs ran and were marked
  `completed` in `jobs` (`2082c8c5`, `92ac907d`, `0fd562b3`), so the
  *dispatch* telemetry is green while the *function* has produced nothing for
  a month. A skill whose success metric is "job completed" cannot see this
  class of failure. Lead with it; it outranks every substantive finding.
- `swing/` was **provably clean for the third time in a row**
  (`git status --porcelain -- swing/` → empty, whole tree dirty). The
  path-scoped precondition would have let all three grades through. That is
  now a 3/3 measured case for the DR, not a hypothesis.
- The orphan class **escalated from scaffold to a sibling's finished grade**.
  10-11's dirty set was `M CHANGELOG.md`, `M evaluation/BACKLOG.md`
  (356 lines), `M evaluation/SCORECARD.md` (**+187 lines = a complete
  2026-10-05 project-evaluator run, composite 3.92→3.65**),
  `M knowledge/stocks/coverage-matrix.md`, all mtime 2026-10-05 07:17–07:27,
  plus the same recurring untracked `.agents/`, `.codex/`, `AGENTS.md`
  (mtime 09-30) that `stash@{0}` already rescued once. Verified **not**
  duplicated on origin (`git show origin/master:CHANGELOG.md | grep -c
  '<headline>'` → 0; origin SCORECARD 867 lines vs local 1054). This is real,
  unpushed, six-day-old work by another governor — all the more reason not to
  touch it, and a far stronger owner-attention item than stray scaffold.
- The clone drifted to **61 behind, 0 ahead**. Read ALL substantive evidence
  via `git show origin/master:<path>` — the local `swing/evaluation/LEDGER.md`
  was 2560 lines vs origin's 2892, i.e. **the local ledger was missing
  C-0004's RESULT and all of C-0005**. Grading off the local copy would have
  mis-reported the research lane as idle. The orphaned CHANGELOG entry
  explains the drift: a commit authored *inside the pull-only runtime clone*
  made every `--ff-only` deploy pull refuse, stranding 46 commits.

## Watchdog: closing a finding on control-exists evidence (2026-10-11)

- **F6/DR-0007 (the rc=127 watchdog) is genuinely FIXED** and is the first
  finding closeable under the "not-recurring ≠ fixed" rule — because the
  *control now demonstrably exists*, not because the week was quiet:
  `volumes/logs/schedule-monitor.log` shows the rc=127 streak ending
  2026-10-04 and **7 consecutive `rc=0` runs 10-05→10-11**, and
  `schedule_adherence.json` `generated_at` was **46 minutes old** at grade
  time (vs 19 days stale at G-0003). Check both the rc histogram and the
  artifact's `generated_at` before crediting the fix — either alone is
  forgeable by the other's failure mode.
- Phase S still requires an **induced silent-worker drill**; a watchdog that
  merely runs green has not been shown to *fire*. Working ≠ drilled — do not
  let the rc=0 streak satisfy that exit criterion.

## Query mechanics, round 2

- `swing.runs` has **no `started_at`** column — the timestamp is **`ts`**
  (schema: `id, ts, status, mode, git_sha, config_hash, equity, cash,
  details`). `started_at` raises `column does not exist` and will abort a
  whole chained pull.
- The assistant `jobs` table likewise has **no `finished_at`**; use
  `created_at` for last-seen liveness.
- Atlas DB creds: the atlas clone's `.env` sources fine and its
  `DATABASE_URL` needs `+asyncpg` stripped for psql. Enumerate rowcounts with
  a loop over `information_schema.tables where table_schema='swing'` — it
  proves the tables exist AND that the zeros are real in one pass
  (the 529-as-completed guard).
- `provisioning_gap` is still outside Phase S's clean taxonomy, so a 100%
  `provisioning_gap` week scores **0/10 clean sessions**, not 10/10. At
  62/62 lifetime (day 42 of DR-0005) the shakedown denominator has never
  advanced past zero.

## The precondition broke by itself — untracked ≠ dirty (learned G-0004, 2026-10-18)

- **G-0004 finally got written, after 3 lost grades.** The unblocking insight is
  narrow and reusable: `git status --porcelain` showed three entries, but all
  three were `??` **untracked** (`.agents/`, `.codex/`, `AGENTS.md`) and there
  were **zero tracked modifications**. Untracked files cannot be swept into a
  pathspec commit and **do not block `git pull --rebase`** — so the operational
  blocker the precondition exists to prevent (per the 09-27 lesson: "rebase is
  blocked, the only way through is stashing someone else's work") was simply
  **absent**. Classify the dirt before stopping: `M`/`A`/`D` on tracked paths is
  a real stop; a pure `??` set is not.
- Do not read this as "the precondition is optional". It is the same rule,
  applied to its actual operational test rather than to the one-line summary of
  `git status`. DR-0008 (path-scoped precondition) stays OPEN: this week was
  clean because siblings behaved (trader committed T-0032 as `65373ee` *before*
  the slot; the 10-11 governor parked its orphans in `stash@{0}` instead of the
  worktree), not because a control appeared. Not-recurring ≠ fixed.
- **The atlas-side GOTCHAS mirror goes stale during DoS weeks.** Three blocked
  sessions wrote lessons only to the ai-server copy, so
  `integrations/ai-server/skills/atlas-swing-evaluate/GOTCHAS.md` was missing
  everything after 2026-09-13. `diff` the two copies every run and re-sync; the
  atlas mirror is the one a future atlas-side reader will find.

## jobs.started_at EXISTS — and created_at is ENQUEUE time (corrects "round 2")

- The earlier note "the assistant `jobs` table has no `finished_at`; use
  `created_at` for last-seen liveness" is **wrong and dangerous**. The real
  columns are `… created_at, started_at, completed_at, task_id`. Verify with
  `select column_name from information_schema.columns where table_name='jobs'`.
- `created_at` is when the scheduler **enqueued**, `started_at` is when the job
  actually **ran**. Grading liveness on `created_at` reports a flawless cadence
  across a totally dead window. On 10-12→10-16 every swing slot was enqueued
  exactly on cron and ran **6h05m to 3d09h14m late**.
- Same trap one level up: **`schedules.last_run_at` also stamps at ENQUEUE.**
  It read `atlas-swing-trade-edt` = 10-16 15:45:17 (perfect) for a job that
  started 23:55. Never grade swing liveness from that column.
- The one-line fleet-health probe, worth running every grade:
  `select date(created_at at time zone 'America/New_York') d, count(*),
   round(avg(extract(epoch from (started_at-created_at))/60)::numeric,1) avg_min,
   round(max(extract(epoch from (started_at-created_at))/60)::numeric,1) max_min
   from jobs where created_at >= '<mon>' and started_at is not null group by 1 order by 1;`
  Healthy reads `0.0`. G-0004 week peaked at **4216.5 min avg (70h)**.

## The LLM-quota pause outage class (new, G-0004)

- A fleet-wide **`seven_day` subscription-quota pause** can stop every job on
  the host for days. Detect it directly:
  `grep -n "queue paused on quota" volumes/logs/runner.out.log | head -2` and
  `grep -n "quota pause expired" volumes/logs/runner.out.log | tail -5`.
  G-0004: set `2026-10-12 20:30:34 EDT reset_at=2026-10-16T00:00:00Z`, expired
  `2026-10-15 20:00:04 EDT` = **71h29m30s**, triggered by ~44 `atlas-report`
  children fanned out by one sweep on 10-11. Swing consumed almost none of it.
- Expect a tail of `five_hour` pauses *after* the big one as the backlog drains
  — four of them on 10-16. The burst of late job starts is the **drain**, not a
  recovery; same reading rule as the catch-up-dispatch lesson.
- The trading lane is a **minority tenant of a shared quota it barely uses**,
  with no reservation or priority tier. Filed as DR-0009. The trader hit this
  independently the same hour (T-0032 F27, their P13 proposes moving the
  executor to its own launchd timer) — corroboration, raises priority.
- Swing's rows survived the lateness **only by schema luck**: `provisioning_gap`
  is a statement about a missing credential and is true at any instant, whereas
  the trader's `market_closed` is a market-state claim and went affirmatively
  false. Once DR-0005 clears, swing inherits the same corruption risk — hence
  DR-0010 (a `stale_slot` abort guard), which in turn needs DR-0011 (ratify the
  Phase S taxonomy) or it will produce another unscoreable status.

## Two watchdog readings that look like bugs and are not

- **`0 finding(s)` immediately followed by `ALERT DM sent` is the designed
  Sunday all-clear** (`scripts/schedule-monitor.sh:83` bypasses the findings
  gate; line 77 is the real findings DM). The log reuses one string for both
  paths. Check the day-of-week and read the script before reporting a spurious
  alert — this cost a cycle to rule out.
- **The watchdog FIRED on a real event** 10-14/15/16 (13/19/15 findings),
  naming `atlas-swing-supervise-edt` and `atlas-swing-trade-edt` as STUCK with
  an owner DM each day. rc histogram now `rc=0 × 15, rc=127 × 29`, i.e. **14
  consecutive rc=0 since 10-05**, artifact 50 min fresh. F6/DR-0007 stays
  CLOSED with stronger evidence. **But an organic firing is still not the Phase
  S "induced silent-worker drill"**, and the kill switch remains unexercised
  end-to-end. Working ≠ drilled, even when it works on a real outage.
- Detection worked and nothing could act. Record that shape explicitly: this
  was **not** a governor-dark incident, it was an everything-saw-it-and-no-one-
  could-respond incident. Different finding, different fix.

## Other G-0004 mechanics

- **G-0002's phantom run rows did NOT recur.** All 9 rows mapped 1:1 onto the 9
  successful job executions, each within 90s of its `job_started`, with 9
  distinct `git_sha` values and one constant `config_hash`. Keep running the
  cross-check — it is what *proved* the clean result — but report the clean
  finding plainly; the missing per-slot guard in `executor.py` is still missing.
- A failed job auto-escalates to `self-diagnose`; read the child's verdict from
  `jobs.result` (it is **jsonb** — `left(result::text, N)`, not `left(result,N)`,
  which errors). G-0004: the child correctly called the SDK `initialize` timeout
  transient but scoped to one job and missed that the whole fleet was 1–3 days
  behind — its own "concurrent-session startup contention" hypothesis *was* the
  backlog. Per-job diagnostics do not check fleet state; don't inherit their
  scope when deciding whether a failure is noise.
- Useful lag-table one-liner for the grade:
  `to_char(justify_interval(started_at-created_at),'DD"d" HH24"h" MI"m"')`.
- DR-0005 day count: first `provisioning_gap` 2026-08-30 → day 50 at G-0004,
  71/71 lifetime runs `provisioning_gap`, shakedown denominator still 0.
