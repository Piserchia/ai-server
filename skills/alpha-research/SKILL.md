---
name: alpha-research
description: "Alpha-lab stage worker — advances ONE owner idea exactly one lifecycle stage per job under atlas alpha-lab/evaluation/PROTOCOL.md (file+triage -> seal card -> one backtest cycle -> adversarial validation -> verdict GO/NO-GO/BLOCKED-ON-DATA), then dispatches the next stage job after the push. Dispatch-driven chain, not scheduled. Payload requires project_slug=atlas plus idea_id (advance existing) or idea_text (file new). Kind alpha-research."
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
context_files: ["skills/alpha-research/GOTCHAS.md"]
tags: [atlas, alpha-lab, research, needs-dispatch-mcp]
---

# alpha-research — one stage, one commit, one dispatch

You advance ONE alpha-lab idea exactly ONE stage, then stop. Binding
docs, read this run: `alpha-lab/CLAUDE.md`,
`alpha-lab/evaluation/PROTOCOL.md`, `evaluation/LOOP.md` §6. Timer
discipline: first command `date +%s > /tmp/alpha-stage-start`; check
elapsed before each phase; at 45 min write an honest note into your
summary, commit what is sealed, and close out — the chain resumes from
state.json (an honest INCOMPLETE beats a timeout).

Venv (fresh clone): `cd alpha-lab && python3.12 -m venv .venv &&
.venv/bin/pip install -q pytest pyyaml`.

Mode from payload:

- **`idea_text` present (FILE mode):** count non-terminal ideas
  (`ideas/*/state.json` with stage != "verdict"). At/over budget.yaml
  `max_active_ideas` → append the idea to `evaluation/INBOX.md` as an
  unchecked `- [ ] <text> (owner, <today>)` line (only if no identical
  unchecked entry already exists — the governor may have dispatched you
  from that very line), commit, push, report "queued at capacity"; STOP
  (no dispatch). Otherwise: assign the next
  A-#### (max existing ideas/ id + 1, A-0001 if none), create
  `ideas/A-####/state.json` via `alphalab.state.new_state` (max_cycles
  from budget.yaml), record the idea in INBOX — checked, with
  ` -> A-####` (append the line if it came via Telegram; check off the
  existing line if the governor dispatched it from a hand-edit), append
  an IDEA ledger entry (first body line `Idea: A-####`, then the idea
  text verbatim), then run the TRIAGE stage in this same session.
- **`idea_id` present (ADVANCE mode):** load `ideas/<id>/state.json`;
  if terminal, report "already decided — <outcome>" and STOP. Execute
  exactly the current stage.

## Stages

**triage** (submitted → triaged | verdict): authoritative prior-art
sweep (all five verticals' ledgers + trials registries); mechanism
plausibility; free-data availability — name the exact series/universe
needed and which existing free source covers it (Alpaca IEX daily,
yfinance WITH its survivorship caveat stated, FRED, Finnhub earnings).
A fetch error is a retry, not absence (error ≠ absence). Write
`ideas/A-####/research/triage.md` with the findings. Outcomes: advance
to `triaged`; or terminal NO-GO (prior art / implausible mechanism) or
BLOCKED-ON-DATA (paid-only data; LLM-signal class) — then run the
VERDICT close-out below in this same session.

**card** (triaged → carded): write `ideas/A-####/card.md` + a
HYPOTHESIS ledger entry with every PROTOCOL §2 field (`Criteria
observables:`, `Success criterion:`, `Kill criterion:`, `Prior-art
check:`). The card commit MUST be pushed to origin/master before the
backtest stage is dispatched — dispatch only after the push succeeds
(momentum E-0032: a card sealed after execution voids the measurement).

**backtest cycle** (carded → backtesting; backtesting → backtesting |
validated | verdict): ONE confirmatory cycle against the sealed card.
Build the harness under `ideas/A-####/research/cycle-<n>/` where n =
cycles_used + 1 (stdlib + pyyaml only; for DAILY-BAR ideas import
`quantlab` — venv: `.venv/bin/pip install -q -e ../quant` — for
engine/metrics/DSR/walk-forward/critic instead of hand-rolling them
(owner-approved 2026-09-23, PROTOCOL §3); intraday ideas stay bespoke;
costs ≥3bps/side, pessimistic fills, walk-forward/purged CV, placebo
M≥200, `manifest.json` provenance — PROTOCOL §3). Lifetime N and V[SR]
for any DSR use `quantlab.trials.distinct_n` / `distinct_sr_variance`
(distinct (family, params_hash) — PROTOCOL §4). Append trials.jsonl lines for EVERY variant
evaluated, then RESULT and VERDICT ledger entries; increment
cycles_used. Success or kill criterion met AS WRITTEN → advance to
`validated`. Neither met, budget remaining → stay `backtesting`. A repeat
cycle's amended card (new HYPOTHESIS entry, ≤2 params changed) is that
job's FIRST act and is committed AND pushed on its own BEFORE the cycle
runs (PROTOCOL §2 seal-before-run); cycle jobs with an amended card
therefore make TWO commits — card seal, then results — an explicit
exemption from the one-commit rule below. Budget exhausted → terminal
NO-GO "budget death" (deterministic; skip validation) → VERDICT
close-out now.

**validation** (validated → verdict): spawn the adversarial validator as
a Task subagent with a clean context — give it ONLY the card and the
cycle artifacts, not your narrative. It scores each criterion AS
WRITTEN and holds kill-standing; its scoring is final. Record its
findings as a VERDICT ledger entry, then run the VERDICT close-out.

**VERDICT close-out** (terminal, from any path above): set state.json
stage="verdict" with verdict.outcome ∈ GO / NO-GO / BLOCKED-ON-DATA and
a one-line reason; append the DECISION ledger entry citing evidence
E-ids, then append exactly ONE lesson line to `evaluation/LESSONS.md`
(`- [A-####] <family> | <kill-class> | <reusable constraint>` —
PROTOCOL §6; for a GO the "constraint" states what made it pass). A GO
must state lifetime N (distinct pairs, `quantlab.trials.distinct_n`),
the Deflated Sharpe Ratio against it, the placebo percentile, a
recommended target vertical (trader / swing / value / momentum), a
≤5-line build sketch — and, for daily-frequency rules, a ready-to-paste
quant-roster graduation OFFER line (`{idea, strategy, symbols, params}`
+ "reply 'graduate A-####' to add it to the quant desk's weekly
roster"); applying it is the owner's reply, never yours. Reserve the
LAST ~15 turns of any stage for this close-out chain — an unpushed
workspace is worthless (INV-16; the c6cfbf6b loss).

**Near-miss refinement** (optional, after a NO-GO close-out only): if a
decisive kill clause landed within 20% of its threshold (state the
numbers in the DECISION), and the idea's refinement_depth <
`max_refinement_depth`, and no sibling refinement exists, you MAY
dispatch ONE FILE-mode job for a single refined variant (payload
idea_text citing `parent: A-####`, `refinement_depth: <depth+1>`,
family unchanged) — budget-checked like any dispatch. This is the only
dispatch a terminal stage may make (PROTOCOL §2c).

## Chain mechanics (after every NON-terminal stage)

1. Gates: `cd alpha-lab && .venv/bin/python -m pytest -q` green;
   code-review subagent LGTM on any code diff; secrets grep. ONE
   commit, footers `Alpha-Idea: A-####` + `Job: <job-id8>`. Every
   stage's state.json write also refreshes `last_advanced_at` (UTC
   now) and `last_job_id` — the governor's liveness sweep keys on them;
   a stale timestamp gets your chain double-dispatched.
2. `git pull --rebase origin master`, then push (on reject: rebase,
   retry ONCE; still failing → report divergence, do NOT dispatch).
3. Budget check: `psql assistant -tAc "SELECT count(*) FROM jobs WHERE
   kind = 'alpha-research' AND created_at > now() -
   interval '24 hours'"`. At/over budget.yaml `max_alpha_jobs_per_day`
   → skip the dispatch ("cap-stalled" in your summary; the daily
   governor resumes it). The cap bounds stage jobs; intake jobs run
   under kind 'task' (router) and are cheap, owner-initiated, and
   self-limiting.
4. Dispatch AFTER the push: `enqueue_job`, kind `alpha-research`,
   description `alpha-research: <next stage> A-#### — <short idea
   tag>`, payload `{"project_slug": "atlas", "idea_id": "A-####",
   "session_timeout_seconds": 3600}`.

## Write surface

`alpha-lab/**` only. You NEVER edit: any other vertical, `tradingcore/`
(read-only import), `config/budget.yaml`, the tests (tripwire OR module
suite), sealed cards, past ledger entries, this skill. Proposals go in
a DECISION-REQUEST ledger entry + your summary.

## Close-out

Final message = Telegram summary: idea id, stage executed, outcome,
cycles used vs budget, next dispatched job id — or, on a terminal
stage, the verdict memo: outcome, the single strongest reason, N / DSR
/ placebo percentile for a GO, and what (if anything) waits on the
owner.

## Gotchas

- The card push precedes the backtest DISPATCH, not merely the backtest
  run — never run even a "quick look" backtest in the card session.
- trials.jsonl lines land before the cycle's VERDICT entry; "I didn't
  log the rejects" invalidates the cycle (PROTOCOL §4).
- Never bump session_timeout_seconds toward the 5400 cap as a stage
  stopgap — split the work across chain jobs instead (the
  atlas-momo-research timeout incident class).
- A dispatch that fails AFTER a successful push is safe to leave: the
  daily governor detects the stalled chain from state.json and
  re-dispatches (LOOP.md §5 design rule — repo artifacts travel in one
  commit; the enqueue is the only out-of-band write, after the push).
- A candidate needing numpy/pandas is a blocker note for the owner,
  never a pip install (momentum E-0033 precedent).
