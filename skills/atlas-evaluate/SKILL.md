---
name: atlas-evaluate
description: Weekly Atlas project evaluation — score the dashboard against the rubric, triage the data_gaps ledger, grade shipped builds, promote built→live with evidence, re-route the backlog. Dispatch for the atlas-evaluate schedule/job_kind, or on demand ("evaluate atlas", "what should atlas build next").
model: claude-opus-5
effort: high
permission_mode: bypassPermissions
required_tools: [Read, Write, Edit, Bash, Glob, Grep]
max_turns: 60
escalation:
  on_failure:
    model: claude-opus-5
    effort: xhigh
tags: [atlas, evaluation, scheduled-capable]
context_files: ["skills/atlas-evaluate/GOTCHAS.md"]
---

# atlas-evaluate — weekly scorecard + gap triage + backlog re-route

You are running Atlas's scheduled evaluation job — stage 1 (governor) of
the closed loop; `evaluation/LOOP.md` is the binding contract, read it this
run. You JUDGE and ROUTE — you never build features, never deploy, never
restart services.

## Ground rules (non-negotiable)

- Work in the dev clone `~/Documents/repos/atlas` (NEVER the runtime clone
  under ai-server projects/).
- First command: `git pull --rebase origin master`. Last commands:
  `git pull --rebase origin master && git push origin master`.
- Free-only policy is binding (Atlas CLAUDE.md §Repo conventions): any gap
  or backlog item that requires a paid source is rejected/`DEFERRED —
  paid-only`, never budgeted for.
- You do NOT deploy and do NOT build. Builds belong to `atlas-build`
  (Tue/Fri), which dispatches its own gated deploy chain; your levers are
  the backlog, the ledger, and `built → live` promotion with evidence
  (LOOP.md §3).
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
3. **Grade shipped builds + promote built→live (LOOP.md §4.1).**
   `git log --since='8 days ago' --grep='^Loop-Item:' --format='%h %s'` —
   for each build commit: confirm its PROGRESS.md evidence + REVIEW verdict
   exist and its deploy job went green (`psql assistant`, kinds
   deploy_director/atlas_redeploy). **Also read the build job's
   post-session verdict** — `psql assistant -c "SELECT id,review_outcome
   FROM jobs WHERE resolved_skill='atlas-build' AND created_at >
   now()-interval '8 days';"`: a `blocker`/`error` (or a `post_review_flagged`
   audit event) on an already-deployed build is a top-of-backlog `[build:*]`
   fix item (atlas-build is unattended — this weekly read is how a flagged
   diff surfaces). For each gap at `built`: check the LIVE
   DB for landed rows / a fresh `feed_status` row; rows landed → matrix row
   `PIPELINE_BUILT → LIVE` + `gaps-set <id> live` (evidence pasted in the
   scorecard); no rows after 7 days → STUCK-BUILT: file a `[build:*]` fix
   item with the failing evidence, never flip live.
4. **Stuck-state + liveness sweep**: `specced` gaps idle >21 days →
   re-triage. Failed atlas-build jobs since last run → read the summary,
   encode the lesson. Confirm the FOUR loop schedules fired within
   cadence+25h (`psql assistant -c "SELECT name,last_run_at,paused FROM
   schedules WHERE name IN ('atlas-evaluate','atlas-build','atlas-gap-scout',
   'atlas-refresh-knowledge');"` — other atlas-% rows like the daily brief
   are NOT yours to police) — a silent or paused loop schedule is a
   `[system]` finding.
5. **Score** every rubric dimension with one line of evidence each;
   explain every delta vs. the previous `evaluation/SCORECARD.md` entry.
   Run the glossary scanner
   (`dashboard/.venv/bin/python .claude/skills/glossary-audit/scripts/scan_terms.py`)
   for the educational-depth evidence.
6. **Re-route the backlog**: rewrite `evaluation/BACKLOG.md` — max 12 open
   items, each tagged/routed/sized per the charter, ordered by expected
   money-making improvement per unit effort. Done-detection is
   footer-AGNOSTIC: sweep `git log` + CHANGELOG since last run for ANYTHING
   shipped (humans and dev-machine sessions don't write `Loop-Item:`
   footers) and move it to Done — footered commits additionally get graded
   in step 3; an open item whose work already shipped footer-less would
   otherwise be rebuilt by Tuesday's builder. **Builder-eligibility
   contract (LOOP.md §4.1)**: every
   item the builder may pick carries effort S or M and deterministic
   done-evidence in its line; design-needed work is tagged `[design:*]`
   (builder-ineligible) until a plan exists.
7. **Write back**: append the SCORECARD entry, save the BACKLOG, add a
   `CHANGELOG.md` entry (what moved, what got triaged/rejected, verdict).
8. **Commit + push**: conventional message, e.g.
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
- **Date the scorecard from `date -u +%F`, never from memory** — the first
  live run (2026-08-04) stamped its report a week in the future (2026-08-11).
- **Verify deploy state before claiming "pending deploy"**: compare
  `git -C "$HOME/Library/Application Support/ai-server/projects/atlas" log -1
  --format=%h` against `origin/master`. The first live run declared the
  living-loops arc frozen-pending-deploy minutes after it had been deployed
  and verified.
- **Every write goes to the dev clone — `$ATLAS`-style paths in docs are the
  RUNTIME clone, read-only.** The first live run duplicated its CHANGELOG
  entry into the runtime clone's tracked file, which blocked that evening's
  redeploy at the ff-only pull (incident 2026-08-04). If you must read
  runtime state, read it; never edit, and never resolve a relative write
  path against anything but `~/Documents/repos/atlas`.
