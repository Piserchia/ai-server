---
name: atlas-swing-research
description: Weekly governed research cycle for the Atlas swing vertical — ONE pre-registered hypothesis card under swing/evaluation/PROTOCOL.md (analyst → engineer → adversarial validator → risk-officer on risk-surface diffs → documentarian), deterministic backtest evidence, ledger + trials close-out. Write surface is additive only. Dispatch for the atlas-swing-research schedule.
model: claude-opus-5
effort: high
permission_mode: bypassPermissions
required_tools: [Read, Write, Edit, Bash, Glob, Grep, Task]
max_turns: 80
isolation: workspace
subagents: [code-review]
post_review:
  trigger: always
role: worker
division: atlas
privilege_class: guarded-writer
context_files: ["skills/atlas-swing-research/GOTCHAS.md"]
tags: [atlas, swing, trading, research, scheduled-capable]
---

# atlas-swing-research — one card, honestly closed

Run ONE research cycle under `swing/evaluation/PROTOCOL.md` (read it in
full first — it is binding). Timer discipline: `date +%s > /tmp/cycle-start`
at the top; at 45 minutes jump to close-out — an honest INCOMPLETE beats a
timeout.

## Cycle

1. Workspace clone, rebase, bootstrap swing venv (+ sitecustomize script).
2. ANALYST (Task subagent, clean context): pick the highest-value open
   question (LEDGER backlog; first candidates: PEAD baseline once
   FINNHUB_TOKEN lands; universe refresh; TTM-EBIT refinement) and seal a
   card in `swing/evaluation/LEDGER.md`: causal claim, ≤2 params, success
   AND kill criteria with `Criteria observables:`, prior-art check.
3. ENGINEER: execute exactly the card. Backtests per PROTOCOL §3 (costs
   ≥3bps/side, walk-forward, stop-inclusive AND stop-less variants,
   trials.jsonl line BEFORE the verdict). The baseline harness at
   `swing/research/baselines/run_baselines.py` is reusable.
4. ADVERSARIAL VALIDATOR (clean context): kill-standing review of the
   result against the card as written.
5. RISK-OFFICER (only if the diff touches limits/kernel/executor/live-guard
   surface): adopts the atlas momo-risk-officer charter — live-wiring or
   cap-raising proposals are AUTO-DENY (owner ladder acts).
6. DOCUMENTARIAN: LEDGER close-out, verdict scored as written.

## Write surface (everything else is forbidden)

NEW `swing/config/strategies/setups_vN.yaml` (with card id; the adoption
gate enforces); appends to `swing/evaluation/*`; scratch under
`swing/research/`; NEW tests. Never: limits.yaml, settings.yaml, risk.py,
executor.py, tripwire tests, CLAUDE.md, LADDER.md, tradingcore/*, this
skill.

## Gates before push

swing pytest green; code-review subagent LGTM on any code diff; secrets
grep; ONE commit, `Swing-Cycle:` + `Job:` footers; rebase before push.
Stage-flip ceiling: candidate → validated PROPOSALS only (the governor
flips; live_capped is owner-only).

## Gotchas

Pre-loaded from `skills/atlas-swing-research/GOTCHAS.md` — trials.jsonl BEFORE verdict;
sealed files are superseded, never edited; 45-minute close-out timer;
owner-owned doctrine (limits/vetoes/sizing) is proposal-only territory.
