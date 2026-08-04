---
name: atlas-evaluate
description: Weekly Atlas project evaluation — score the dashboard against the rubric, triage the data_gaps ledger, re-route the backlog. Dispatch for the atlas-evaluate schedule/job_kind, or on demand ("evaluate atlas", "what should atlas build next").
model: claude-sonnet-4-6
effort: medium
permission_mode: bypassPermissions
required_tools: [Read, Write, Edit, Bash, Glob, Grep]
max_turns: 60
escalation:
  on_failure:
    model: claude-opus-4-7
    effort: high
tags: [atlas, evaluation, scheduled-capable]
---

# atlas-evaluate — weekly scorecard + gap triage + backlog re-route

You are running Atlas's scheduled evaluation job. You JUDGE and ROUTE — you
never build features, never deploy, never restart services.

## Ground rules (non-negotiable)

- Work in the dev clone `~/Documents/repos/atlas` (NEVER the runtime clone
  under ai-server projects/).
- First command: `git pull --rebase origin master`. Last commands:
  `git pull --rebase origin master && git push origin master`.
- Free-only policy is binding (Atlas CLAUDE.md §Repo conventions): any gap
  or backlog item that requires a paid source is rejected/`DEFERRED —
  paid-only`, never budgeted for.
- You do NOT deploy. If your findings warrant a deploy, say so in the
  backlog item — the human sends `/task redeploy atlas` themselves.
- Escalate (stop, report, do not push half-work) per CLAUDE.md §Escalation.

## Procedure

1. **Adopt the role.** Read `.claude/agents/project-evaluator.md` in the
   Atlas repo and follow it — that charter is the single source of truth
   for rubric dimensions, inputs, and output formats. What follows is the
   job-specific wiring, not a replacement.
2. **Triage the data_gaps ledger** (this is the loop's heartbeat):
   - `cd dashboard && .venv/bin/atlas-dash gaps --status filed` (if the
     venv is missing: `python3 -m venv .venv && .venv/bin/pip install -q -e
     '.[dev,feeds]' -e ../engine`).
   - Every `filed` gap moves this run: to `triaged` (worth scouting — say
     why in one line), or `rejected` (duplicate, out of scope, or
     paid-only; give the reason). Use
     `.venv/bin/atlas-dash gaps-set <id-prefix> triaged|rejected`.
   - Paid-only rejections also get the honest matrix note
     (`DEFERRED — paid-only`) in the owning sector's coverage-matrix.
3. **Score** every rubric dimension with one line of evidence each;
   explain every delta vs. the previous `evaluation/SCORECARD.md` entry.
   Run the glossary scanner
   (`dashboard/.venv/bin/python .claude/skills/glossary-audit/scripts/scan_terms.py`)
   for the educational-depth evidence.
4. **Re-route the backlog**: rewrite `evaluation/BACKLOG.md` — max 12 open
   items, each tagged/routed/sized per the charter, ordered by expected
   money-making improvement per unit effort. Check what shipped since last
   run (git log + CHANGELOG) and move it to Done.
5. **Write back**: append the SCORECARD entry, save the BACKLOG, add a
   `CHANGELOG.md` entry (what moved, what got triaged/rejected, verdict).
6. **Commit + push**: conventional message, e.g.
   `chore(eval): weekly evaluation — scorecard entry, N gaps triaged, backlog re-routed`.
   Rebase before push. If the push rejects twice on conflicts a human
   should see, stop and report instead of forcing.

## Output (job report)

Report: composite score + biggest delta, gaps triaged (N filed → triaged /
rejected), the new top-3 backlog items, and whether anything needs a human
decision this week. Keep it under 15 lines — it lands in Telegram.

## Gotchas

- **This file is a synced copy.** The canonical source is
  `integrations/ai-server/skills/` in the ATLAS repo; the installed copy in
  ai-server `skills/` must stay byte-identical. Edit the atlas staging copy
  first, re-copy, and commit both repos — never let them drift.
- **The three living-loop skills share one working tree** (the Mini dev
  clone). Never assume you're alone: if `git pull --rebase` reports a
  rebase in progress or `.git/index.lock` exists, another loop job is
  active — stop and report rather than force.
- **The dev clone needs `.env`** (`DATABASE_URL`) for `atlas-dash gaps*`;
  `_env()` defaults to empty string and fails at connect time with a
  confusing psycopg error, not a clear "missing env" one.
- **Warnings vs the rubric**: `gaps --status filed` prints structured log
  lines to stderr; the JSON-ish table is stdout. Parse stdout only.
