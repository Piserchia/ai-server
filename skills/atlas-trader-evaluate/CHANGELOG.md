## 2026-11-20 — GOTCHAS: breaker-trip forensics, SGOV distributions, and unclean-down non-discriminating test

**Agent task**: self-diagnose for job 90d0b65c; multiple GOTCHAS entries appended as runtime learnings from the 2026-11-17 T-0046 grade.
**Files changed**:
- `skills/atlas-trader-evaluate/GOTCHAS.md` — three new entries: (1) `trader.halts` daily_loss rows quote the last-exists prior close, not necessarily the prior session, so a halt is not evidence the named breach happened that day; (2) `breaker_tripped` status is productive coverage but scores as a MISS on T-0002 observable (a)'s allowlist — score as written and file a successor card; (3) paper account now credits SGOV distributions (first DIV row 2026-11-05, cash 450.10 → 482.63), creating a convention break in the equity series; (4) `last shutdown` returns zero records lifetime on this host, making the unclean-down boot test non-discriminating — use healthcheck.log gap instead.

**Why**: Each entry emerged from a live grading session (T-0046). The breaker trip was forensically wrong twice before the root cause (stale_data skips check_breakers at step 7) was understood; the SGOV distribution changes the equity series convention mid-history; the boot-test non-discrimination was discovered during the 11-day healthcheck-all dormancy gap diagnosis.

**Side effects**: None — documentation-only entries.

**Gotchas discovered**: None beyond the ones now recorded.

## 2026-11-02 — E-0230: entry-loss run of four ends, cost-column convention pinned to `cost_usd_list` (from governor job 391c7029)

**Agent task**: alpha-governor scheduled run E-0230; confirmed that the prior run (6398f0ff) closed `ok` and landed E-0229 — ending the streak of four consecutive destroyed entries at exactly four; measured a 12.7% discrepancy between the two `jobs` cost columns (`cost_usd_list` vs `sdk_cost_usd`) over the hold era and pinned the ledger convention to `cost_usd_list` to prevent a silent direction-reversal in cost reporting.

**Files changed**:
- `alpha-lab/evaluation/LEDGER.md` — E-0230 (PROTOCOL-VIOLATION) appended, append-only (+0 deletions)
- `alpha-lab/research/GOTCHAS.md` — entry added: hold `cost_usd_list` as the cost-series column; switching to `sdk_cost_usd` mid-series would report the era getting cheaper while it got dearer
- `CHANGELOG.md` (atlas) — E-0230 entry recorded

**Why**: Two cost columns exist in `jobs`: `cost_usd_list` (OpenAI list-price basis) and `sdk_cost_usd` (SDK-reported). Over the 44-run hold era they diverge by 12.7% ($112.66 vs $98.37 on the governor lane). Every prior LEDGER entry quoted `cost_usd_list`; switching columns now would reverse the apparent cost trend, the one direction a cost series must never be wrong in. The GOTCHAS entry locks the convention so future evaluators never inadvertently switch.

**Side effects**: None — documentation-only change; no dispatches, no state changes.

**Gotchas discovered**: `jobs.cost_usd_list` and `jobs.sdk_cost_usd` are 12.7% apart on the alpha-governor lane; always quote `cost_usd_list` for ledger entries to stay consistent with all prior entries.

---

## 2026-11-02 — Push (not commit) is the loss-safe unit; E-0229 committed and pushed before docs write-back (from governor job 6398f0ff)

**Agent task**: alpha-governor idle-triggered run E-0229; verified the canonical ledger was intact after the prior run (7012fded) was destroyed by the turn cap; measured that 4 of 5 `max_turns` runs lost their ledger entry because they died holding a local commit that never pushed; recorded new owner item #16 (one-line skill close-out amendment: push before the docs write-back); amended `.agents/skills/` SKILL.md files accordingly; updated LEDGER.md with E-0229 and corrected E-0228's spend figures.

**Files changed**:
- `trader/evaluation/LEDGER.md` — E-0229 appended; E-0228 §1 corrected (roll-up was $133.29 / 57 jobs, not $122.13 / 55)
- `integrations/ai-server/skills/atlas-trader-evaluate/GOTCHAS.md` — entry for push-vs-commit loss-safe unit added
- `.agents/skills/design-system/SKILL.md` — close-out amended: push before docs write-back
- `.agents/skills/sector-research/SKILL.md` — same amendment
- `.agents/skills/source-command-bootstrap/SKILL.md` — same amendment
- `.agents/skills/source-command-evaluate-project/SKILL.md` — same amendment
- `.agents/skills/verify-frontend/SKILL.md` — same amendment
- `.agents/skills/verify-migration/SKILL.md` — same amendment
- `.agents/skills/verify-pipeline/SKILL.md` — same amendment
- `.codex/agents/code-reviewer.toml` — updated to reflect push-first convention

**Why**: Cross-referencing all 43 hold-era governor rows against 37 landed entries isolated 6 runs with no entry, 4 of them `max_turns`. In every lost case the session had committed locally but the harness cut the run before `git push`. The single survivor (2e67bdc5, E-0223) had already pushed. Commit is not the loss-safe unit; push is. Codifying this as a skill amendment prevents the same 4-entry loss pattern in future capped runs.

**Side effects**: Seven `.agents/skills/` SKILL.md files amended — any skill that uses a close-out sequence is now push-before-docs. `.codex/agents/code-reviewer.toml` updated.

**Gotchas discovered**: "Push is the loss-safe unit, not commit" — a `max_turns` kill delivers an atomically clean workspace but loses any local-only commit; the only defense is to push before writing back docs.

---

## 2026-11-01 — GOTCHA: per-run cost oscillates (not monotone), PROTOCOL §4 60-session convention, adjustment=all vs split screen, and control-presence trap details (from governor job a22a9606)

**Agent task**: alpha-governor idle-triggered run E-0228; audited 7 days / 37 runs of governor cost data and found no monotonic cost trend despite ledger growth, then appended six new evaluation gotchas to the server-side GOTCHAS.md.

**Files changed**:
- `skills/atlas-trader-evaluate/GOTCHAS.md` — six entries added (2026-11-01):
  1. **Whole-host outage** signature (expanded detail): multi-day gap in `jobs.started_at` AND `healthcheck.log`; `schedules.last_run_at` self-heals; diff sessions against an independent bar list.
  2. **`status='completed'` is not evidence of work** — logged-out CLI returns `terminal_reason='error'`, `model_served=NULL`, zero tokens; 24 such jobs in T-0040's window.
  3. **Grep on audit logs yields false positives** — meta-jobs re-read logs; confirm against DB columns.
  4. **Never credit a control from its presence in the repo** — credential canary is committed but not installed (no launchd plist, no log).
  5. **PROTOCOL §4 rule 3 is settled at 60 NYSE sessions** — count from independent bar list; sign of Sharpe = sign of cumulative return.
  6. **Run `adjustment=all` vs `split` ex screen for every window quoted** — not just the grading week.

**Why**: E-0228 confirmed that six prior entries had treated per-run cost as inexorably rising (a plausible causal story) without measuring the trend. Measured across 37 runs it is a 1.67× oscillation with no monotonicity, meaning the run's own reading discipline — not ledger length — determines realised cost. The gotchas codify this and five other classification errors found during T-0040 grading.

**Side effects**: None — documentation-only change.

**Gotchas discovered**: See the six bullet points above; all are now in GOTCHAS.md.

---

## 2026-11-01 — GOTCHA: host-outage signature, null-token completed jobs, grep false positives, and control-presence trap (from governor job 906c469a)

**Files changed**: `skills/atlas-trader-evaluate/GOTCHAS.md` — four new entries appended

**Agent task**: alpha-governor idle-triggered run E-0227; the session also
  retracted two prior findings (idle cooldown DOES reset on scheduled runs,
  `num_turns` is ruled out for item #14) and appended four new evaluation
  gotchas to the server-side GOTCHAS.md.

**Files changed**:
- `skills/atlas-trader-evaluate/GOTCHAS.md` — four entries added:
  1. **Whole-host outage** is invisible to in-box watchdogs and self-heals the
     metric they watch; signature is a multi-day gap in both `jobs.started_at`
     and `healthcheck.log` with a cold-boot `last reboot` and no `runner
     starting` line across the gap; `schedules.last_run_at` reads HEALTHY
     afterwards because the recovery drain re-stamps before the watchdog runs.
  2. **`status='completed'` is not evidence of work done** — a logged-out CLI
     returns in 2–13 s with `terminal_reason='error'`, `model_served=NULL`, and
     zero tokens; the correct liveness predicate queries those three columns.
  3. **Grep on audit logs yields false positives** — meta-jobs re-read logs so
     the error string appears in their own `tool_result`; always confirm a grep
     census against `jobs.terminal_reason + model_served + input_tokens`.
  4. **Never credit a control from its presence in the repo** — the audit must
     confirm it is installed and running, not just committed.

**Why**: T-0040's grading sweep (job 906c469a) uncovered a multi-day host
  outage that had been invisible to every watchdog and self-healed before any
  monitor ran; 24 of that week's jobs were null-token completed failures that
  the standard `status='completed'` check passed. Each gotcha prevents a future
  evaluation run from repeating the same mis-classification.

**Side effects**: None — documentation-only change.

**Gotchas discovered**: See the four bullet points above; all are now in
  GOTCHAS.md.

## 2026-11-22 — T-0054 grade: ten new gotchas, headlined by two control defects

**What**: Appended ten mechanical lessons to GOTCHAS.md from the T-0054 grading
  run (job b02a4198), and re-synced the atlas staged copy in the same commit:

  1. **A `daily_loss` halt blocks the de-risk it exists to enable.**
     `risk.validate` unions new breakers into `halt_kinds` (`risk.py:85-86`) and
     blanket-rejects on `:90-91` — the kernel is not side-aware. `risk.py:92`
     already exempts `daily_loss` under `mode="flatten"`, but `executor.py:225`
     reaches flatten only from the kill-switch. Tell: `gate_flipped=True` on a
     `breaker_tripped` row.
  2. **PROTOCOL §4's demotion lever is INERT** — `strategy_state.stage` is
     write-through only (`executor.py:424`); the order path keys off
     `settings.yaml:active_strategies` and a hardcoded `:402` lookup. Fire the
     mandated DB demotion, then report the inertness; never treat the write as
     enforcement. Both config routes are traps (red adoption gate / mid-run
     `KeyError`).
  3. **A demotion can collide with a pending de-risk, on a deadline** — halts
     auto-clear next session and `diff_to_intents` trades past the drift band
     even off a rebalance day, so a blocked rotation re-fires with no action
     from anyone. Give the owner the UTC deadline and say which way inaction
     resolves.
  4. **A supervisor session can re-enter the only order path twice in one job.**
     Tell: run-row count > paper-job count for a date. Read the audit JSONL's
     Bash `input.command` values; don't assume one row per job.
  5. **The 17:31Z sample is fail-open inside the breaker too** (−301 bp sampled
     vs −323.36 bp close-to-close). Use `/v2/account` as a third witness — the
     close-convention rebuild matched the broker to the cent.
  6. **F33's halt check can come back CLEAN** — report the pass, and always run
     the complement (no halt ≠ no breach).
  7. **§4 rule 2's "two trips in 10 sessions" needs session-counting, not dates**
     — T-0054's trips missed by exactly one session; its remedy is also a no-op
     at paper stage.
  8. **T-0002's kill criterion needs the full weekly series** — exactly 80%
     breaks a `< 80%` run; the count was 2, not 4. Don't fire early.
  9. **The §6 no-lessons baseline deadline arrived un-runnable** — file the
     instruction to record it MISSED-BY-CONSTRUCTION; don't fabricate a baseline.
  10. **The two skill copies were in sync for the second week** — keep diffing,
      and re-sync in the same commit as the ledger entry.

**Why**: T-0054 was the week PROTOCOL §4 rule 3 matured (session #60 =
  2026-11-18) and fired. Executing the mandated demotion surfaced that it has no
  mechanical effect, and the vertical's first gate flip surfaced that the two
  risk controls fight each other. Lessons 1-3 exist so a successor governor does
  not mistake a recorded demotion for a stopped executor, and leads the grade
  with the control interaction rather than the coverage number.

**Side effects**: None to the skill body — documentation plus the mandated
  `trader.strategy_state` DB write, which is the skill's own authorised action.

**Gotchas discovered**: The ten above, all in GOTCHAS.md and mirrored to
  `integrations/ai-server/skills/atlas-trader-evaluate/GOTCHAS.md`.
