# docs/

Reading guide for this documentation set. Start here if you're a Claude Code
session picking up work on this repo, or a human returning after a break.

## What's in here

| Doc | Purpose | When to read |
|---|---|---|
| [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md) | Failure-mode-first debugging guide | **Always** when something's broken |
| [`PHASE_3_PLAN.md`](PHASE_3_PLAN.md) | Domain + tunnel + Caddy + bingo + market-tracker | **SHIPPED** — historical reference |
| [`PHASE_4_PLAN.md`](PHASE_4_PLAN.md) | Expansion skills + MCP servers + event triggers | **SHIPPED** — historical reference |
| [`PHASE_5_PLAN.md`](PHASE_5_PLAN.md) | Operations (upkeep, backup, server-patch, review-and-improve) | **SHIPPED** — historical reference |
| [`PHASE_6_PLAN.md`](PHASE_6_PLAN.md) | Polish (research-deep, ideas, update-poll, restore, SSE, /schedule) | **SHIPPED** — historical reference |
| [`assistant-system-design.md`](assistant-system-design.md) | Original full system design doc | Background reading; phase plans supersede it where they disagree |

## Recommended reading order for a new Claude Code session

**If you're debugging a broken installation:**

1. Read `../MISSION.md` — understand what the system is supposed to do
2. Read `TROUBLESHOOTING.md` from the top — find your symptom
3. Follow the diagnostic commands, then the fix
4. If the root cause doesn't match anything in the file, add a new entry
   following the template at the end of that doc

**If you're implementing a new phase:**

1. Read `../MISSION.md` — stay oriented on objectives
2. Read `../CLAUDE.md` and `../SERVER.md` — current state of the repo
3. Read `../.context/SYSTEM.md` — module graph and invariants
4. Read the specific `PHASE_N_PLAN.md` for the phase you're executing
5. Read module-level `../.context/modules/<x>/CONTEXT.md` for every module the
   phase touches
6. Start executing the runbook at the end of the phase plan

**If you're an SDK session (runner-invoked):**

1. Your SKILL.md already contains your instructions — follow them
2. If your skill declares `context_files` in frontmatter, read those files first
3. Otherwise, follow the instructions in your Active Skill section
4. The server directive preamble has already been tailored to your task type

**If you're making ad-hoc improvements (not tied to a phase):**

1. Read `../MISSION.md`
2. Skim `../.context/SKILLS_REGISTRY.md` — don't duplicate existing skills
3. Skim `../.context/PROJECTS_REGISTRY.md` — know what's hosted
4. Do the work
5. Update the relevant `CHANGELOG.md` per `../.context/PROTOCOL.md`

## How each phase plan is structured

Every `PHASE_N_PLAN.md` follows the same 10-section layout:

1. **Goal** — one paragraph on what this phase delivers
2. **Done =** — the concrete, observable success criterion
3. **Status** — shipped / in-progress / not-started
4. **Decisions locked in** — things prior sessions agreed; don't re-litigate
5. **Open decisions** — things that must be resolved before / during execution
6. **Architecture refresher** — the mental model for this phase
7. **File-by-file plan** — every file to create or modify, with a sketch
8. **Runbook** — step-by-step commands with checkpoints
9. **Rollback** — how to back out if something breaks
10. **NOT in this phase** — explicit scope ceilings

If something conflicts between a phase plan and actual repo state: **trust
the repo, flag the discrepancy** as a new entry in `TROUBLESHOOTING.md`.

## Self-contained promise

Each phase plan is designed to be opened in a fresh Claude Code session with
no prior chat context. The only prerequisites for a phase plan to be
executable:

- The repo at the prior phase's commit
- The phase plan itself
- `../MISSION.md` and `../.context/SYSTEM.md` for orientation
- Standard Mac Mini environment (Postgres, Redis, claude CLI, gh CLI, etc.
  per `../GETSTARTED.md`)

If a phase plan references a file that's supposed to exist but doesn't, that
means either (a) an earlier phase wasn't fully executed — fix that first —
or (b) the plan has drift; update it before proceeding.

## Using these docs in Claude Code CLI

A typical session:

```bash
cd "$HOME/Library/Application Support/ai-server"
claude

# In Claude Code:
> Read docs/PHASE_3_PLAN.md. We're executing Phase 3. Start at step 1
> of the runbook.
```

Or for debugging a failed job:

```bash
> Read docs/TROUBLESHOOTING.md and volumes/audit_log/<job_id>.jsonl.
> The job failed with <error message>. Diagnose and propose a fix.
```

The repo's `CLAUDE.md` already primes the session with these conventions,
so you usually don't need to re-state them.

## Keeping this doc set current

- When you **ship a phase**: update the corresponding `PHASE_N_PLAN.md`'s
  "Status" line to `SHIPPED` with commit SHA. Add a brief "What actually
  happened vs the plan" section at the bottom if any deviations.
- When you **hit a new failure**: add to `TROUBLESHOOTING.md` using the
  template at its bottom.
- When you **change an architectural decision** that a future phase
  depends on: update that phase's "Decisions locked in" section.

Do not rewrite history in these docs. They're a permanent record of
intent. If a decision reversed, *add* the reversal with a date; don't
delete the original.
