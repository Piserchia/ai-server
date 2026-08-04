---
name: atlas-refresh-knowledge
description: Monthly Atlas knowledge refresh — curator condensation of knowledge/<sector>/CLAUDE.md files (150-line budgets), re-verification of stale (>90d) load-bearing claims, gaps-sync reconciliation. Dispatch for the atlas-refresh-knowledge schedule/job_kind.
model: claude-sonnet-4-6
effort: medium
permission_mode: bypassPermissions
required_tools: [Read, Write, Edit, Bash, Glob, Grep, WebSearch, WebFetch]
max_turns: 80
escalation:
  on_failure:
    model: claude-opus-4-7
    effort: high
tags: [atlas, knowledge, scheduled-capable]
---

# atlas-refresh-knowledge — curate budgets, re-verify stale claims, reconcile

You are running Atlas's monthly knowledge-maintenance job. Mechanical
first, verification second — never a rewrite of sector judgment.

## Ground rules (non-negotiable)

- Work in the dev clone `~/Documents/repos/atlas` (NEVER the runtime clone).
- First command: `git pull --rebase origin master`. Last commands:
  `git pull --rebase origin master && git push origin master`.
- Free-only policy binding; matrix statuses are never altered by curation
  (only a re-verification that FAILS may downgrade a row, with a dated note).
- No deploys, no restarts. Escalate per CLAUDE.md §Escalation.

## Procedure

1. **Curator pass.** Read `.claude/agents/knowledge-curator.md` and apply
   it to every `knowledge/<sector>/CLAUDE.md`: measure against the 150-line
   budget; relocate / merge / tighten in that order; flag `[STALE —
   reverify]` on load-bearing claims older than 90 days; append the
   curation footer line. Structure rules in the charter are binding
   (sources survive moves, headers stay stable).
2. **Re-verify what you flagged** (the curator role never verifies — you
   do it as a second, separate pass): for each `[STALE — reverify]` claim,
   check the current source (WebSearch/WebFetch; you have real egress).
   Claim still true → refresh the checked date, drop the flag. Changed →
   correct it with the new source + date, and note the correction in the
   sector log. Source gone/paid-walled → say so honestly; if a spec relied
   on it, downgrade the matrix row with a dated note and file a gap:
   `dashboard/.venv/bin/atlas-dash gaps-file "<title>" --sector <sector>
   --detail "<what died>" --source refresh-knowledge` (bootstrap venv if
   missing: `python3 -m venv .venv && .venv/bin/pip install -q -e
   '.[dev,feeds]' -e ../engine`).
3. **Reconcile the ledger.** `.venv/bin/atlas-dash gaps-sync` — mirrors
   every matrix's NEEDS_FEED/FEED_SPECCED rows into `data_gaps` (idempotent;
   catches rows added by humans or builds that bypassed filing).
4. **Glossary guard.** Run the scanner
   (`dashboard/.venv/bin/python .claude/skills/glossary-audit/scripts/scan_terms.py`);
   if your edits surfaced an undefined term, add the entry (glossary-audit
   skill has the quality bar).
5. **Write back + commit + push**: `CHANGELOG.md` entry (files curated,
   lines saved, claims re-verified/corrected, gaps synced), conventional
   commit e.g. `docs(knowledge): monthly refresh — N files curated, M
   claims re-verified, gaps-sync`. Rebase before push; stop and report on
   repeated conflicts.

## Output (job report)

Report: per-file line deltas, claims re-verified (true/corrected/dead),
gaps-sync count, scanner result. Under 12 lines — it lands in Telegram.

## Gotchas

- **This file is a synced copy.** Canonical source:
  `integrations/ai-server/skills/` in the ATLAS repo; the ai-server copy
  must stay byte-identical. Edit the atlas staging copy first, re-copy,
  commit both repos.
- **The three living-loop skills share one working tree** (the Mini dev
  clone). A rebase-in-progress or `.git/index.lock` means another loop job
  is active — stop and report, never force.
- **The dev clone needs `.env`** (`DATABASE_URL`) for `atlas-dash gaps*`
  commands; empty DSN fails at connect time, not with a clear missing-env
  message.
- **Curation is not judgment**: the 150-line budget trims are mechanical
  (relocate/merge/tighten); a claim's TRUTH only changes in the separate
  re-verification pass with a fresh source + date.
