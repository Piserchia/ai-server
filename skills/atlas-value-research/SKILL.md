---
name: atlas-value-research
description: Weekly value-advisor research cycle — ONE pre-registered card under value/evaluation/PROTOCOL.md improving the screen/thesis machinery (universe breadth, TTM EBIT, consensus source, sector map). Additive write surface; adversarially validated; ledger + trials close-out. Dispatch for the atlas-value-research schedule.
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
context_files: ["skills/atlas-value-research/GOTCHAS.md"]
tags: [atlas, value, advisor, research, scheduled-capable]
---

# atlas-value-research — one card, honestly closed

ONE cycle under `value/evaluation/PROTOCOL.md` (read in full; binding).
Timer discipline: 45-minute close-out jump; honest INCOMPLETE beats
timeout. The D-0001 ledger entry lists the founded backlog: universe
breadth (~77 → hundreds, with UNMEASURABLE-rate tracking), TTM-EBIT
refinement, consensus-delta source, financials-sector sleeve, PEAD overlay
once FINNHUB_TOKEN lands.

Roles as in swing-research: analyst seals the card (Criteria observables
mandatory) → engineer executes exactly → adversarial validator →
risk-officer on any gate/threshold-loosening diff (loosening a suggestion
gate is a risk-surface change — auto-escalate; NEVER weaken the earnings
veto or obligation-based sizing, those are owner-owned doctrine) →
documentarian closes out.

Write surface: additive config versions, `value/evaluation/*` appends,
scratch under `value/research/`, NEW tests. Never: screen.yaml thresholds
(propose via DECISION-REQUEST), CLAUDE.md, test_no_order_path.py,
tradingcore/*, this skill. Gates before push: value pytest green,
code-review LGTM, secrets grep, ONE commit with `Value-Cycle:` footer,
rebase before push.

## Gotchas

Pre-loaded from `skills/atlas-value-research/GOTCHAS.md` — trials.jsonl BEFORE verdict;
sealed files are superseded, never edited; 45-minute close-out timer;
owner-owned doctrine (limits/vetoes/sizing) is proposal-only territory.
