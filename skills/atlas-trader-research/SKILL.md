---
name: atlas-trader-research
description: Weekly trader-vertical research cycle for Atlas — one governed hypothesis cycle over the strategy population (pre-registered card -> deterministic backtest evidence -> adversarial validation -> risk review if the risk surface moves -> ledger + trial-registry close-out) in a workspace clone, under trader/evaluation/PROTOCOL.md as the binding contract. May produce a new ADDITIVE strategy_vN.yaml candidate; never touches limits.yaml, the kernel, or live anything. Dispatch for the atlas-trader-research schedule/job_kind, or on demand ("run a trader research cycle").
model: claude-opus-5
effort: high
permission_mode: bypassPermissions
required_tools: [Read, Write, Edit, Bash, Glob, Grep]
max_turns: 80
isolation: workspace
subagents: [code-review]
post_review:
  trigger: always
role: worker
division: atlas
privilege_class: guarded-writer
context_files: ["skills/atlas-trader-research/GOTCHAS.md"]
tags: [atlas, trader, research, scheduled-capable]
---

# atlas-trader-research — one governed research cycle, then stop

You are running the trader vertical's weekly research cycle.
`trader/evaluation/PROTOCOL.md` is the binding contract — read it in full
this run, plus `trader/CLAUDE.md` and `evaluation/LOOP.md` §6 (human
ceilings). Momentum's separated-duty discipline applies (trader/CLAUDE.md
rule 8): walk the stages as distinct Task subagents with clean contexts —
analyst (card only) → engineer (executes exactly the card, numbers only) →
adversarial validator (kill-standing) → risk-officer IF the diff touches
any risk surface (adopt `.claude/agents/momo-risk-officer.md`; its
live-wiring auto-DENY applies verbatim here) → documentarian (ledger +
trials.jsonl + close-out). Timer discipline: first command
`date +%s > /tmp/trader-cycle-start`; check elapsed before each stage; at
45 min jump to the documentarian close-out — an honest INCOMPLETE entry
beats a timeout.

## Ground rules (non-negotiable)

- Workspace clone; `git pull --rebase origin master` first and again before
  the final push. One hypothesis cycle per run.
- EVERY candidate evaluated this cycle — including rejects and every
  exploratory grid cell — appends a line to `trader/evaluation/trials.jsonl`
  BEFORE the verdict is written. A promotion claim must state lifetime N and
  the deflated-Sharpe reasoning against it (PROTOCOL §2).
- Cards are sealed in `trader/evaluation/LEDGER.md` BEFORE any run, with
  `Criteria observables:`, Success/Kill criteria, and a `Prior-art check:`
  citing the nearest ledger + trials entries. Criteria are scored as
  written.
- Backtests: free daily data only, costs modeled, walk-forward or purged
  CV per PROTOCOL §3. LLM-signal candidates: historical backtests are
  INADMISSIBLE — post-cutoff paper evidence + ticker-anonymization probe
  only.
- Your write surface: `trader/config/strategies/strategy_vN.yaml` (NEW
  files only), `trader/evaluation/*` appends, backtest scratch under
  `trader/research/` (create it), NEW test files for new candidate code.
  You NEVER edit: limits.yaml, the kernel (trader/trader/risk.py), the
  executor, settings.yaml, sealed strategy files, GO_LIVE.md, CLAUDE.md,
  this skill — or the mechanical tripwires `tests/test_paper_only.py` and
  `tests/test_adoption_gate.py` (any diff touching those or any existing
  enforcement test IS a risk-surface change: it routes to the risk-officer
  stage, whose charter auto-DENIES it). Proposals for any of those go in
  the summary + a ledger DECISION-REQUEST entry.
- Stage flips: your ceiling is `candidate → validated` proposals recorded
  in the ledger. The GOVERNOR (atlas-trader-evaluate) executes flips;
  `paper → live_*` does not exist (owner ceiling).
- Gates before push: `cd trader && .venv/bin/python -m pytest -q` green
  (bootstrap venv like momentum if missing), code-review subagent LGTM on
  any code diff, secrets grep. ONE commit, `Trader-Cycle:`/`Job:` footers.
  Red gate → no push, blocker report.

## Close-out

Documentarian appends the ledger entries + trials lines, updates atlas
`CHANGELOG.md` + SESSION_HANDOFF per repo CLAUDE.md. Final message =
Telegram summary: cycle id, cards touched, verdicts with the single
strongest reason, lifetime trial count N, and any decision waiting on the
owner or governor.

## Gotchas

- trials.jsonl is append-only and the DSR's denominator — "I didn't log the
  rejects" invalidates the cycle's conclusions (PROTOCOL §2).
- The trader venv may be missing in a fresh clone: `cd trader &&
  python3.12 -m venv .venv && .venv/bin/pip install -q -e '.[dev]'`.
- The package is stdlib+pyyaml by owner ceiling — a candidate needing
  numpy/pandas is a blocker note for the owner, never a pip install
  (momentum E-0033 precedent).
- Schedule row (ai-server seed-schedules.sh, Wed 13:00 UTC) MUST carry
  '{"project_slug":"atlas","session_timeout_seconds":3600}'.
