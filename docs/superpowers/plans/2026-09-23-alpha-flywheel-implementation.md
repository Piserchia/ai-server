# Alpha Flywheel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans.
> Executed inline by the authoring session (established context); tasks keep
> their own test cycles and commits.

**Goal:** Ship the continuous generate→evaluate→learn flywheel per
`docs/superpowers/specs/2026-09-23-alpha-flywheel-design.md`.

**Spec:** docs/superpowers/specs/2026-09-23-alpha-flywheel-design.md

## Global Constraints

- INV-22 untouched; no protected path (events.py is NOT protected; INV-4
  lane applies: gates + code-review LGTM + owner notification).
- alpha-lab tests must stay green untouched (PROTOCOL keeps the literal
  strings "95th percentile" and "Deflated Sharpe").
- quantlab stays stdlib+pyyaml; distinct-N is additive (line-count
  `lifetime_n` remains for compatibility).
- Frozen-skill edits (alpha-research, alpha-governor) are recorded as
  front-door actions in the spec Status line.

### Task 1: quantlab distinct-N (D-0001 resolution)
Files: `atlas/quant/quantlab/trials.py`, `cli.py`; tests
`test_trials.py`, `test_cli.py`; `quant/evaluation/PROTOCOL.md` §2;
`quant/evaluation/LEDGER.md` (D-0001 DECISION entry).
Interfaces: `distinct_n(path) -> int` (distinct (family, params_hash);
fail-closed like lifetime_n); `distinct_sr_variance(path) -> float`
(variance ddof=1 over LATEST sr_native per pair; raises if <2 pairs).
`cli._report_entry` switches `n_trials=distinct_n`, `var=distinct_sr_variance`.
Test vectors: 8-line file with 4 distinct pairs duplicated → distinct_n
== 4 while lifetime_n == 8; variance uses latest sr per pair (assert a
changed latest value shifts variance); <2 pairs raises.
Steps: failing tests → run RED → implement → GREEN (full quant suite) →
PROTOCOL §2 + LEDGER DECISION → commit `feat(quant): distinct-variant N (D-0001 resolved)`.

### Task 2: alpha-lab flywheel constitution
Files (atlas): `alpha-lab/config/budget.yaml` (12/4/6 + max_scout_files_per_run 3
+ max_refinement_depth 2), `evaluation/FAMILIES.md` (seed 8 open families:
calendar-seasonality, index-rebalance/flows, post-earnings-drift,
cross-asset lead-lag, vol-term-structure, mean-reversion-liquidity,
momentum-decay, ETF-primary-market frictions — each w/ mechanism + free-data
feasibility), `evaluation/LESSONS.md` (seed A-0001 mechanism-first,
A-0002 free-data-ceiling, A-0003 cost-floor lessons), `evaluation/PROTOCOL.md`
(new §2b Generation: families+mining only, mechanism-first; §2c Refinement:
near-miss ≤20% margin, one per verdict, depth ≤ 2, parent cited; §3 note:
daily-bar harnesses MAY import quantlab (read-only, `-e ../quant`); §4:
lifetime N = distinct (family, params_hash); §6: LESSONS line mandatory per
DECISION), `alpha-lab/CLAUDE.md` (read-only imports += quant/, bootstrap
`-e ../quant`), LEDGER NOTE (owner decisions of 2026-09-23 verbatim).
Verify: `cd alpha-lab && .venv/bin/pip install -q -e ../quant &&
.venv/bin/python -m pytest -q` green; `python -c "import quantlab"` from
alpha-lab venv works. Commit `feat(alpha-lab): flywheel constitution`.

### Task 3: skills — alpha-scout (new) + research/governor amendments
Files (ai-server): `skills/alpha-scout/{SKILL.md,GOTCHAS.md}` (read-only+
dispatch posture cloned from alpha-intake; procedure per spec §2a; Gotchas
section present); `skills/alpha-research/SKILL.md` (+quantlab harness
preference & venv line, +LESSONS append at close-out, +near-miss refinement
dispatch rule, +GO memo graduation offer, +close-out turn reservation
promoted from GOTCHAS, +distinct-N wording); `skills/alpha-governor/SKILL.md`
(+audit duties: lessons line, refinement caps, distinct-N spot-check, scout
liveness; summary states scheduled-vs-idle provenance).
Verify: `pipenv run pytest tests/test_skill_contracts.py -q` green.
Commit `feat(skills): alpha-scout + flywheel amendments (front-door)`.

### Task 4: idle drainer (events.py) + tests
Files: `src/runner/events.py` (+`ALPHA_IDLE_COOLDOWN_HOURS = 4`,
`ALPHA_DAILY_JOB_VALVE = 12`, pure `_should_trigger_idle_alpha(
queued_or_running, last_governor_at, alpha_jobs_24h, cooldown_hours=4,
daily_valve=12) -> bool`, `_check_idle_queue_alpha()` mirroring the
review check: last COMPLETED alpha-governor via resolved_skill, count of
alpha-research jobs created in 24h, enqueue kind `alpha-governor`
created_by `event-trigger:idle-queue`; called from event_loop next to the
review check, non-fatal, breaker-exempt like its sibling); tests mirroring
the existing idle-review predicate tests (find them via grep
`_should_trigger_idle_review` in tests/): idle+never-run → True; busy →
False; recent governor → False; valve reached → False; stale+idle → True.
Also `.context/modules/runner/CHANGELOG.md` entry (pre-commit hook).
Verify: full `pipenv run pytest -q` green. Commit
`feat(runner): idle-queue alpha drainer (INV-4 lane)`.

### Task 5: schedules + registries + docs
Files: `scripts/seed-schedules.sh` (+2 rows: alpha-scout '10 8 * * *'
and '10 20 * * *', no payload — read-only dev-clone posture like
alpha-intake/governor? NO: governor row carries project_slug for its
workspace; scout is read-only unisolated like alpha-intake → NO payload,
matching intake), `.context/SKILLS_REGISTRY.md` (+scout row, amend
research/governor rows), `.context/org/divisions/atlas/CHARTER.md`
(+scout row), `.context/INDEX.md` (Additions 2026-09-23 block).
Verify: `python scripts/lint_docs.py` All clean. Commit with Task 4 or
separate `feat(schedules): alpha-scout 2x daily`.

### Task 6: gates, review, push, deploy, live acceptance
In-session code-review agent over both repos' diffs (events.py = server
code ⇒ INV-13). Secrets grep. Push atlas → push ai-server →
`server-deploy` job (skills+schedules+events) → `atlas-redeploy` job
(quant + alpha-lab gates). Live: dispatch one `alpha-scout` job now;
verify it reads FAMILIES/LESSONS, files ≤3 ideas (or honest no-file),
chains start; verify schedule rows; verify idle predicate via unit tests
+ a later quiet-window observation note. Update memory + final report.
