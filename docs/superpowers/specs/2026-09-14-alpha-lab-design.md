# Alpha-Lab: owner-submitted alpha ideas → autonomous research → GO / NO-GO verdict

**Date:** 2026-09-14
**Status:** Approved design (owner, 2026-09-14). Implementation plan to follow.
**Owner decisions baked in:** new atlas vertical; continuous-until-verdict pacing;
intake via both Telegram and a repo inbox file; GO produces a decision memo only
(no auto-build).

## 1. Purpose

The owner submits an idea for where alpha might be found ("small-cap PEAD drifts
longer than large-cap", "VIX term-structure inversion predicts 5-day SPY
reversal", ...). The system autonomously researches, backtests, and adversarially
validates the idea under the momentum-lab constitution, looping until it reaches
a terminal verdict:

- **GO** — evidence memo to the owner (lifetime N, deflated Sharpe, placebo
  percentile, robustness) plus a recommended target vertical
  (trader/swing/value/momentum) and a sketch of what to build. Building is the
  owner's call; alpha-lab files nothing into any build queue.
- **NO-GO** — documented no-edge trail. Per the parent protocol §10, this is a
  *success of the process*, not a failure.
- **BLOCKED-ON-DATA** — the test cannot be run honestly on free data. Paid data
  is owner-only (atlas `evaluation/LOOP.md` §6); alpha-lab never budgets for it.

Alpha-lab is a triage lab. Its only product is verdicts. It never builds
strategies, never touches an order path, never promotes anything into a trading
vertical.

## 2. Repo layout (atlas side: `atlas/alpha-lab/`)

```
alpha-lab/
  CLAUDE.md                  # invariants; rule 1 = verdicts-only ceiling
  config/
    budget.yaml              # owner-owned caps (see §7)
  evaluation/
    PROTOCOL.md              # parent = momentum/evaluation/PROTOCOL.md
    LEDGER.md                # append-only, ## [E-####] <TYPE> <ISO-ts>
    trials.jsonl             # one line per candidate ever evaluated (lifetime N)
    INBOX.md                 # append-only intake; both surfaces land here
  ideas/
    A-0001/
      card.md                # pre-registered idea card
      state.json             # stage, cycles_used, budget, chain-resumption state
      research/              # per-cycle artifact dirs w/ manifest.json provenance
  tests/
    test_verdicts_only.py    # mechanical tripwire (trader test_paper_only.py pattern)
    test_state_machine.py
    test_inbox_format.py
    test_budget_accounting.py
```

- `CLAUDE.md` rule 1: *alpha-lab produces verdicts only — no order paths, no
  live wiring, no promotion into any trading vertical without an owner-initiated
  build task. Changing this rule requires the owner to edit this file first.*
  `test_verdicts_only.py` asserts the rule text is present and that no file
  under `alpha-lab/` imports order-placing modules (`tradingcore.tradier`
  order endpoints, trader executor).
- `PROTOCOL.md` declares momentum's PROTOCOL the parent document ("where this
  file is silent, the parent's rule applies with 'momo' read as 'alpha-lab'"),
  exactly as `trader/evaluation/PROTOCOL.md` does. Additions:
  - **Card fields** (all mandatory): causal claim with predicted direction;
    `Criteria observables:` line (§2a discipline); `Success criterion:`;
    `Kill criterion:`; `Prior-art check:` citing nearest entries across ALL
    verticals' ledgers and trials files (momentum, trader, swing, value,
    alpha-lab) — an idea already killed elsewhere is a same-day NO-GO citing
    the prior trial.
  - **Evidence standards**: inherited from trader §3 — costs always modeled,
    walk-forward or purged CV with embargo, minimum trades per OOS slice,
    survivorship probe mandatory for any universe-selection idea, LLM-signal
    backtests inadmissible (such ideas verdict BLOCKED-ON-DATA with a note
    that the only honest evidence would be forward paper in a real vertical).
  - **Trial accounting**: every backtest cycle and every grid cell appends to
    `trials.jsonl`. A GO memo that does not state lifetime N and the deflated
    Sharpe ratio is invalid on its face.
  - **Verdict rules are deterministic** (§4 pattern): computed from artifacts,
    never re-judged by a model after the fact.
- `LEDGER.md` TYPE set: `IDEA, HYPOTHESIS, RESULT, VERDICT, DECISION,
  PROTOCOL-VIOLATION, AUDIT` — parsed with the same `## [E-####]` regex
  discipline as momentum's `governance.py`.

## 3. Idea lifecycle state machine

```
submitted → triaged → carded → backtesting (≤ max_cycles) → validated → verdict
                │                      │                          │
                └── NO-GO (prior art / infeasible / no free data) ┘
                                        └── BLOCKED-ON-DATA at any stage
```

`state.json` per idea: `{"idea_id", "stage", "cycles_used", "max_cycles",
"last_advanced_at", "last_job_id", "verdict": null|{...}}`. This is the
chain-resumption state — any stage worker can pick up an idea cold from it.

Stage semantics:

1. **triage** — prior-art sweep, feasibility, free-data availability check.
   Cheap; kills weak ideas same-day. Data check follows the "error ≠ absence"
   discipline: a fetch failure is a retry, not a BLOCKED verdict.
2. **carded** — the pre-registered card is written AND pushed to origin
   **before** any backtest runs (the momentum E-0032 lesson: a card sealed
   after execution voids the measurement).
3. **backtesting** — one confirmatory cycle per session against the card,
   harness per the `trader/research/T-0003` exemplar: stdlib+pyyaml only,
   pessimistic fills, stop-inclusive and stop-less variants where applicable,
   placebo baseline (random-entry M≥200; candidate must beat the placebo
   distribution's 95th percentile), `manifest.json` provenance (source_url,
   sha256, row counts, dividend-adjustment note). Cycle results append to
   `trials.jsonl` and the ledger.
4. **validated** — adversarial validator pass with kill-standing: it scores
   criteria exactly as written on the card and may override nothing.
5. **verdict** — DECISION ledger entry + Telegram memo. Budget exhaustion
   (cycles_used == max_cycles without a PASS) is an automatic NO-GO recorded
   as "budget death".

## 4. Intake (both surfaces)

- **Telegram**: a router rule in `src/runner/router.py` matches
  `^alpha( idea)?:` (case-insensitive) → skill `alpha-intake`; explicit
  `--kind=alpha_intake` also works (kind→skill 1:1 mapping is existing runner
  behavior). NL-first triage remains untouched — only the explicit prefix
  routes here, so ordinary chat never lands in the lab by accident.
- **Repo inbox**: the owner may append directly to
  `alpha-lab/evaluation/INBOX.md` in the atlas dev repo. Entry format:
  `- [ ] <idea text> (owner, YYYY-MM-DD)`. The weekly governor (§6) sweeps for
  unchecked entries with no corresponding `A-####` and dispatches intake for
  them, so hand-edits are picked up within a week; Telegram is the fast path.

`alpha-intake` skill (ai-server, `isolation: workspace`,
`project_slug: atlas`, tags include `needs-dispatch-mcp`):
parse the idea → dedup against all ledgers/trials (a duplicate gets a reply
citing the prior verdict, no new idea) → assign next `A-####` → write
`ideas/A-####/` skeleton + INBOX entry (checked) + IDEA ledger entry → commit,
push (standard git gates) → dispatch the first `alpha-research` job with
payload `{"project_slug": "atlas", "idea_id": "A-####"}` → final message
confirms the ID and stage (final message = Telegram summary, existing
convention).

## 5. The research chain (`alpha-research` skill)

One stage per session, then dispatch the next — never one long session (the
`atlas-momo-research` timeout history is the binding precedent; do not lean on
`session_timeout_seconds`).

- Frontmatter: `isolation: workspace`, `subagents: [code-review]`,
  `post_review: {trigger: always}`, `role: worker`, `division: atlas`,
  `privilege_class: guarded-writer`, tags `[atlas, alpha-lab, research,
  scheduled-capable, needs-dispatch-mcp]`. Model per the de-fabled loop
  convention (opus-5 primaries). Timer discipline copied from
  `atlas-trader-research` (elapsed check before each phase; at 45 min, write
  an honest INCOMPLETE state and stop — the chain resumes from `state.json`).
- Body contract: read `state.json` → execute exactly the current stage (using
  in-session subagent stages analyst/engineer/validator per the trader-research
  fleet pattern where the stage calls for them) → write artifacts + ledger
  entries + updated `state.json` → run the alpha-lab test suite → commit, push
  (git gates) → then either dispatch the next `alpha-research` job via the
  dispatch MCP `enqueue_job` (`src/runner/mcp_dispatch.py`), or, on a terminal
  state, write the DECISION entry and stop (no further dispatch).
- **Dispatch-after-push ordering** (LOOP.md §5 design rule): all repo artifacts
  of a stage travel in one commit; the enqueue is the only out-of-band write
  and happens after the push, so a crash at any point leaves a state the
  governor can detect and resume.
- Explicit write surface: `alpha-lab/**` only. Never-edit list: every other
  vertical, `tradingcore/` (read-only import), the alpha-lab test tripwires,
  its own SKILL.md (frozen-evaluator property), budgets (`config/budget.yaml`
  is owner-owned).

## 6. Governor (`alpha-governor` skill)

Weekly, shared dev clone (no `project_slug` payload — deliberate, same as
`atlas-trader-evaluate`; do not "fix" it). Ordered duties:

1. **Chain liveness**: any idea whose `state.json` is non-terminal and
   `last_advanced_at` > 48h old is a broken chain — re-dispatch its next stage
   and record the finding (lead with it; the governor-dark incident class).
2. **Inbox sweep**: uncarded INBOX entries → dispatch intake.
3. **Budget audit**: recompute `cycles_used` from ledger vs `state.json`;
   discrepancies are PROTOCOL-VIOLATION entries.
4. **Verdict integrity spot-check**: newest DECISION's evidence chain
   (card sealed before results? trials.jsonl rows present? placebo run?).
5. Report (final message → Telegram).

Frozen evaluator: reads everything, edits only the ledger (AUDIT entries) and
dispatches; never edits harnesses, budgets, or skills.

Schedule row in `scripts/seed-schedules.sh` (the sole cadence writer):

```bash
upsert 'alpha-governor' '0 10 * * 0' 'alpha-governor' \
  'alpha-governor: weekly alpha-lab chain-liveness + inbox sweep + budget/verdict audit' \
  # no payload — runs in the shared dev clone
```

(Sun 10:00 UTC is a free slot per the current schedule map; confirm against
the map at implementation time.)

## 7. Budgets and quota protection (`config/budget.yaml`, owner-owned)

```yaml
max_cycles_per_idea: 6        # confirmatory backtest cycles; exhaustion = NO-GO
max_alpha_jobs_per_day: 2     # intake + research combined
max_active_ideas: 3           # others queue in INBOX until a slot frees
```

Enforcement: `alpha-research` checks the day's alpha-lab job count (audit
events / jobs table via read-only query) before dispatching; over cap → it
stops the chain and the weekly governor resumes it. This bounds worst-case
quota draw so alpha-lab can never starve the kernel or the other Atlas loops.
Defaults are deliberately conservative; the owner tunes the yaml directly.

## 8. Governance and safety fit

- **INV-22 clean by construction**: no order path exists anywhere in the
  vertical; GO output is prose addressed to the owner. The verdicts-only rule
  is triple-backed: CLAUDE.md rule 1 + `test_verdicts_only.py` + the skill
  never-edit lists.
- **Free data only**: enforced at triage; BLOCKED-ON-DATA is a first-class
  verdict, never a budget request. Add alpha-lab lines to atlas
  `evaluation/LOOP.md` §6 (paid data, verdicts-only ceiling stay human).
- **No new protected paths touched**: intake router rule and dispatch wiring
  are ordinary server-patch-lane changes (INV-4 gates apply); no auth config,
  no guards.py, no executor-skill edits.
- Atlas `manifest.yml`: add a deploy gate with
  `when_paths: ["alpha-lab/"]` running the alpha-lab pytest suite.
- Registries/doc map: `.context/SKILLS_REGISTRY.md` (3 skills),
  `.context/INDEX.md` (this spec + the vertical), atlas `CLAUDE.md` binding
  note, `docs/README.md`.

## 9. Testing and acceptance

- **Atlas side**: pytest suite in `alpha-lab/tests/` (state machine, inbox
  parse, verdicts-only tripwire, budget accounting) wired into the manifest
  deploy gate.
- **Server side**: `python scripts/lint_docs.py`; existing pytest suite stays
  green; seed-schedules re-run is idempotent; an `evals/cases/alpha-intake.yml`
  case for the router prefix.
- **End-to-end acceptance**: submit one deliberately weak throwaway idea via
  Telegram; it must reach NO-GO (at triage or by kill criterion) with a
  complete ledger trail and a Telegram memo, with no human touch after
  submission. Then submit one data-infeasible idea; it must verdict
  BLOCKED-ON-DATA at triage.

## 10. Non-goals

- No auto-build on GO (owner decision 2026-09-14) — revisitable later as its
  own change.
- No new data providers, paid or free-tier-keyed, beyond what atlas already
  has (Alpaca IEX, yfinance-as-source with its stated survivorship caveat,
  Finnhub, FRED).
- No forward-paper stage inside alpha-lab — forward evidence belongs to the
  target vertical after an owner-initiated build.
- No decoy-idea integrity cadence in v1 (momentum/trader carry that burden);
  the governor's verdict spot-check is the v1 control. Revisit if verdict
  volume grows.

## 11. Build order (for the implementation plan)

1. Atlas vertical scaffold (docs, protocol, ledger, tests) — no server changes;
   provable by pytest alone.
2. `alpha-intake` + router rule + dispatch wiring; acceptance: Telegram idea →
   carded skeleton + first job dispatched.
3. `alpha-research` stage worker (triage + card stages first, then backtest +
   validation + verdict stages).
4. `alpha-governor` + schedule row.
5. End-to-end acceptance runs (§9), registry/doc updates, LOOP.md §6 lines.

## Amendments (2026-09-14, discovered at implementation planning)

1. **Intake is read-only + dispatch (§4 revised).** A router-created job
   carries no `project_slug` payload, so a workspace-isolated intake
   would clone the ai-server repo, not atlas
   (`session._resolve_project`); an unisolated writer would need an
   `UNISOLATED_WRITER_ALLOWLIST` entry in `scripts/lint_docs.py` — a
   protected path. Intake therefore dedups read-only against the atlas
   dev clone and dispatches a FILE-mode `alpha-research` job carrying
   the idea text; the stage worker is the vertical's single writer.
2. **Governor is workspace-isolated and DAILY (§6 revised).** Shared
   dev-clone posture would also require the protected-path allowlist
   edit; workspace isolation avoids it and adds guard hooks. Daily
   (09:30 UTC) instead of weekly because chain resumption is the
   governor's job: with a weekly governor, any cap-stall or crashed
   stage would freeze a chain for up to a week, contradicting the
   approved continuous-until-verdict pacing.
3. **`max_alpha_jobs_per_day` default is 6, not 2 (§7 revised).** At 2,
   a 5–7-job idea chain mathematically stalls to the governor every
   day; 6 lets one idea traverse its whole chain within a day while
   still bounding quota. Owner-tunable in `alpha-lab/config/budget.yaml`
   as before.
4. **Charter roster rows landed with their skills (Task 11 §3).** lint's
   check_org_charters requires every skill to be claimed by exactly one
   division charter, so the three atlas roster rows were added in the
   same commits as their skills (Tasks 8–10), not at documentation time.
