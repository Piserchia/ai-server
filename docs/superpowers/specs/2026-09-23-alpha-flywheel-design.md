# Alpha flywheel — continuous generate→evaluate→learn loop (design)

Date: 2026-09-23
Status: APPROVED (owner Q&A this date: throughput "steady grind"; sources
"families + mining"; "yes to both" quantlab adoption + D-0001 resolution;
GO handling "memo + graduation offer"). Owner-owned knobs (budget.yaml,
both PROTOCOLs, frozen-skill edits via LOOP.md §7) are exercised HERE by
explicit owner instruction — this spec is the front-door record.

## 1. Goal

Alpha-lab currently evaluates one owner-submitted idea at a time
(A-0001..A-0003 all terminal). Owner wants a self-feeding flywheel:
generate → evaluate → learn → generate, running "somewhat non-stop" on
idle capacity, until it surfaces validated opportunities. The evaluation
rigor (sealed cards, placebo, adversarial validator, DSR) is unchanged —
the flywheel feeds it and learns from it. Ceiling unchanged (INV-22): a
GO is a memo + a prepared graduation offer; nothing builds or trades.

## 2. Components

### 2a. alpha-scout (new skill — the generator)
Read-only + dispatch (alpha-intake posture: `privilege_class: read-only`,
`acceptEdits`, `needs-dispatch-mcp`, no isolation writes). Twice daily
(08:10 / 20:10 UTC) and cheap. Procedure: read `FAMILIES.md` +
`LESSONS.md` + all five verticals' ledgers/trials → generate up to
`max_scout_files_per_run: 3` candidates, **mechanism-first** (each must
state the mechanism and who is on the other side losing; pattern-only
candidates are not filed), only within registered families or as mining
finds (offered-but-unfiled variants, near-miss refinements) → dedup
sweep (intake's) → dispatch FILE-mode alpha-research jobs while
`active_ideas < max_active_ideas` and the daily job budget allows.
Quiet-capacity behavior: at cap → file nothing, one-line summary.

### 2b. FAMILIES.md (owner-seedable hypothesis-space registry)
`alpha-lab/evaluation/FAMILIES.md`. One `## F-## <name>` section per
family: mechanism sketch, data feasibility on free tier, status
(open | saturated | owner-closed). Scout generates ONLY inside open
families (+ mining). Owner appends/edits freely; agents may append new
family PROPOSALS flagged `status: proposed` (scout may not use them
until the owner flips them open). Seeded at birth with ~8 families.

### 2c. LESSONS.md (the "fix the generator" channel)
`alpha-lab/evaluation/LESSONS.md`, append-only. Every verdict close-out
appends exactly ONE structured line:
`- [A-####] <family> | <kill-class> | <reusable constraint>` — e.g.
A-0003 → "microstructure | cost-floor | free-data 6bps+ round trip kills
horizons where gross < ~10bps; don't file sub-hour-horizon top-of-book
ideas". Scout MUST read it before generating; governor audits that every
DECISION has its lesson line.

### 2d. Near-miss refinement (the bounded "fix the idea")
PROTOCOL amendment: a verdict whose kill margin is narrow (any kill
clause within 20% of its threshold, stated numerically in the DECISION)
MAY propose ONE refined variant: a new idea, new card citing
`parent: A-####`, `refinement_depth: parent+1`, capped at depth 2.
Filed through the normal path, counts fresh trials, deflates against
lifetime N like everything else — the DSR is the license to iterate.
Depth and one-per-verdict are audited by the governor.

### 2e. D-0001 resolved + distinct-N (owner decision)
Lifetime N for the DSR = count of **distinct (family, params_hash)
pairs** in trials.jsonl; identical re-validations do not increment.
V[SR] = variance over the LATEST `sr_native` per distinct pair.
Implemented once in `quantlab.trials` (`distinct_n`, `distinct_sr_variance`)
and used by BOTH the quant desk sweep and alpha-lab harnesses. Quant
LEDGER gets the D-0001 DECISION entry; both PROTOCOLs get the rule.

### 2f. quantlab adoption (frozen-skill edit, front door exercised)
`alpha-research` harness stage: for daily-bar ideas, import `quantlab`
(engine/metrics/dsr/walkforward/leakage) instead of hand-rolling;
alpha-lab venv installs `-e ../quant` (the tradingcore precedent;
quantlab is stdlib+pyyaml so the dependency ceiling holds). Intraday
ideas (like A-0003) keep bespoke stdlib harnesses. `quant/` joins
tradingcore as a named read-only import in alpha-lab/CLAUDE.md.
This is quantlab's second consumer; per atlas CLAUDE.md the engine/
graduation question is NOTED for the owner, not performed now.

### 2g. Idle drainer (server change, INV-4 lane)
`src/runner/events.py`: new pure predicate + check mirroring the
review-and-improve idle trigger — when the queue is idle AND the last
completed `alpha-governor` ended > 4h ago AND alpha-research jobs in the
last 24h < 12 (server-side safety valve matching the budget), enqueue an
`alpha-governor` job (`created_by="event-trigger:idle-queue"`). The
governor already resumes stalled chains and drains INBOX within caps and
no-ops cheaply — this turns quiet hours into flywheel hours while kernel
ops always win (any queued job suppresses the trigger; quota breaker
unaffected).

### 2h. Budgets (owner-set via this Q&A)
`budget.yaml`: `max_alpha_jobs_per_day: 12`, `max_active_ideas: 4`,
`max_cycles_per_idea: 6` (unchanged), new `max_scout_files_per_run: 3`,
`max_refinement_depth: 2`. Ledger NOTE records the owner decision.

### 2i. GO handling — memo + graduation offer
`alpha-research` close-out on GO: loud Telegram memo (N, DSR, worst
fold, placebo percentile, build sketch) PLUS, for daily-frequency rules,
a ready-to-paste quant-roster line (`{idea, strategy, symbols, params}`)
and the sentence "reply 'graduate A-####' to add it to the quant desk's
weekly re-validation roster". Applying it stays a human/owner action.

### 2j. Governor additions (frozen-skill edit, front door exercised)
New audit duties: every DECISION has a LESSONS line; refinement depth ≤
cap and one-per-verdict; N-distinct spot-check on new reports; scout
liveness (2 rows fired daily); idle-trigger provenance is visible in its
summary (scheduled vs idle-triggered).

## 3. Cadence picture

scout 08:10/20:10 UTC (generate ≤3 when capacity) · governor 09:30 daily
(full audit) + idle-triggered every ≥4h of quiet (resume/drain) ·
stage jobs self-chain as today · steady-state throughput ≈ 2–3 ideas
fully evaluated/day, bursting into idle windows, hard-capped at 12
jobs/day and by the org-wide quota breaker.

## 4. Files touched

Atlas: `alpha-lab/config/budget.yaml`, `evaluation/{PROTOCOL.md,
FAMILIES.md,LESSONS.md,LEDGER.md}`, `alpha-lab/CLAUDE.md` (read-only
import + bootstrap `-e ../quant`), `quant/quantlab/trials.py` + tests +
`quant/quantlab/cli.py` (distinct-N), `quant/evaluation/{PROTOCOL.md,
LEDGER.md}` (D-0001 DECISION). ai-server: new `skills/alpha-scout/`,
edits `skills/alpha-research/SKILL.md` + `skills/alpha-governor/SKILL.md`
(front-door), `src/runner/events.py` + tests, `scripts/seed-schedules.sh`
(2 scout rows), registries (SKILLS_REGISTRY, atlas CHARTER, INDEX), this
spec + plan.

## 5. Acceptance

- pytest green: ai-server (incl. new idle-predicate tests), quant (incl.
  distinct-N tests), alpha-lab (strings "95th percentile" + "Deflated
  Sharpe" preserved in PROTOCOL).
- lint_docs All clean; deploys green both repos.
- Live: first scout run files ≥1 idea (or honestly reports the registry
  gives it nothing new — with A-0003's lesson pruning microstructure,
  filing from seeded families is expected); its chain advances without
  manual shepherding; idle trigger observed enqueueing a governor within
  a quiet window.
- Telegram digest behavior unchanged except scout summaries + GO memos.

## 6. Non-goals / ceilings restated

No order path, no auto-build from GO, no auto-graduation (offer only),
no paid data, scout never files outside families+mining, budgets remain
owner-owned (this change IS an owner action), `.context/PROTOCOL.md` and
all MISSION §M protected paths untouched.
