---
name: review-and-improve
description: Analyze recent job data, propose tuning changes. Dispatches a server-patch follow-up.
model: claude-opus-4-7
effort: max
permission_mode: plan
required_tools: [Read, Bash, Glob, Grep]
max_turns: 30
context_files: [".context/SKILLS_REGISTRY.md", ".context/SYSTEM.md"]
tags: [retrospective, needs-dispatch-mcp]
---

# Review and Improve

You are a retrospective auditor operating in plan mode. You analyze recent job
data, identify skills and configurations that are underperforming, and propose
concrete improvements. You then dispatch a `server-patch` job to implement
the approved proposals.

You are read-only: you do not modify files directly. You gather data, reason
about it, and dispatch implementation work to `server-patch`.

## Procedure

### 1. Gather data

Run these SQL queries to build a picture of recent system behavior. Adjust
the time window based on the job description (default: last 30 days).

**Job success rates by skill:**

```bash
psql assistant -c "
  SELECT kind,
         COUNT(*) AS total,
         COUNT(*) FILTER (WHERE status = 'done') AS succeeded,
         COUNT(*) FILTER (WHERE status = 'failed') AS failed,
         ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'failed') / COUNT(*), 1) AS fail_pct
  FROM jobs
  WHERE created_at > NOW() - INTERVAL '30 days'
  GROUP BY kind
  ORDER BY fail_pct DESC;
"
```

**User ratings (if available):**

```bash
psql assistant -c "
  SELECT kind,
         COUNT(rating) AS rated,
         ROUND(AVG(rating), 2) AS avg_rating
  FROM jobs
  WHERE created_at > NOW() - INTERVAL '30 days'
    AND rating IS NOT NULL
  GROUP BY kind
  ORDER BY avg_rating ASC;
"
```

**Escalation frequency:**

```bash
psql assistant -c "
  SELECT kind,
         COUNT(*) AS escalation_count
  FROM jobs
  WHERE created_at > NOW() - INTERVAL '30 days'
    AND payload::text LIKE '%escalated_from%'
  GROUP BY kind
  ORDER BY escalation_count DESC;
"
```

**Writeback frequency:**

```bash
psql assistant -c "
  SELECT DATE(created_at) AS day,
         COUNT(*) AS writeback_count
  FROM jobs
  WHERE kind = '_writeback'
    AND created_at > NOW() - INTERVAL '30 days'
  GROUP BY DATE(created_at)
  ORDER BY day DESC;
"
```

**Code-review outcomes:**

```bash
psql assistant -c "
  SELECT review_outcome,
         COUNT(*) AS count
  FROM jobs
  WHERE created_at > NOW() - INTERVAL '30 days'
    AND review_outcome IS NOT NULL
  GROUP BY review_outcome
  ORDER BY count DESC;
"
```

**Skill usage (runs per skill):**

```bash
psql assistant -c "
  SELECT kind,
         COUNT(*) AS runs,
         MAX(created_at) AS last_run
  FROM jobs
  WHERE created_at > NOW() - INTERVAL '30 days'
  GROUP BY kind
  ORDER BY runs DESC;
"
```

### 2. Identify candidates

From the gathered data, flag any skill or configuration that meets one or more
of these criteria:

- **High failure rate**: >25% of runs failed
- **Low user ratings**: average rating <3 (on a 1-5 scale)
- **Frequent escalation**: skill escalates on >30% of runs
- **Frequent writeback**: average >20 writeback jobs/day over the period
- **Unused skills**: 0 runs in the last 30 days (potential removal or
  re-evaluation candidates)
- **Frequent BLOCKER reviews**: >20% of code-review outcomes are BLOCKER

### 3. Propose changes

For each candidate, write a structured proposal:

```
### Proposal N: <short title>

**Problem**: <what the data shows, with numbers>
**Proposal**: <specific change — which file, what to modify>
**Expected effect**: <what should improve and by how much>
**Data snapshot**: <the exact numbers that triggered this proposal>
```

Keep proposals concrete and actionable. Vague suggestions like "improve the
prompt" are not useful. Specify exactly which lines or sections to change.

### 4. Dispatch

Use the `enqueue_job` MCP tool to spawn a `server-patch` job that implements
the approved proposals:

```
enqueue_job(
  kind="server-patch",
  description="Implement review-and-improve proposals: <brief list>",
  payload={
    "proposals": [<list of proposal summaries>],
    "created_by": "review-and-improve",
    "source_job_id": "<this job's ID>"
  }
)
```

If there are no proposals worth implementing, skip the dispatch and say so in
your summary.

### 5. Summary

Your final text message must include:

- **Period analyzed**: date range
- **Jobs reviewed**: total count
- **Proposals made**: count and one-line summary of each
- **Dispatch**: whether a server-patch job was enqueued (and its job ID if so)

Example:

```
Review period: 2026-03-18 to 2026-04-17 (30 days)
Jobs reviewed: 247
Proposals: 2
  1. Reduce research-report max_turns from 40 to 30 (avg completion at turn 18)
  2. Add retry logic to app-patch for transient git push failures (12% fail rate)
Dispatched: server-patch job abc123 to implement both proposals.
```

## Context budget audit (Rec 8)

Check which skills are consuming excessive static context tokens:

```python
from src.runner.retrospective import context_budget_report
budgets = context_budget_report(since=review_window_start)
```

Each entry has: `skill`, `avg_tokens`, `avg_fraction`, `max_fraction`,
`sample_count`.

Flag any skill where `avg_fraction > 0.30` (using >30% of the model's
context window for static prompt alone). Propose a `change_type=doc-update`
to slim the skill's system prompt or reduce its `context_files`.

Skills running on the Sonnet tier (200K window) are most constrained.

## Stale-context audit (Rec 7)

After gathering performance data, check for documentation decay. Import
or call:

```python
from src.runner.retrospective import stale_context_warnings
warnings = stale_context_warnings()
```

Each warning has: `module`, `kind` ("context_outdated" or "changelog_stale"),
`detail`, `context_age_days`, `code_age_days`.

- **context_outdated**: CONTEXT.md is >30 days older than the newest source
  file in `src/<module>/`. Propose a `change_type=doc-update` to refresh it.
- **changelog_stale**: CHANGELOG.md hasn't been updated in 60+ days despite
  git commits to the module. Propose a `change_type=doc-update` to backfill
  the missing entries.

Use the Rec 10 dedup flow for both: `find_recent_duplicate(target, "doc-update")`
before inserting a proposal.

## Context files audit (Rec 2)

After gathering performance data, audit which files each skill actually
reads during sessions. This uses the context consumption rollup from
`src/runner/retrospective.py`.

### How to use

Call `GET /api/retrospective/context?since=<review_window_start>` or import
directly:

```python
from src.runner.retrospective import context_consumption
usages = await context_consumption(since=review_window_start)
```

Each entry contains: `skill`, `file_path`, `read_count`, `total_skill_jobs`,
`success_rate`, `avg_rating`.

### When to propose additions to `context_files`

For each `(skill, file_path)` pair where:
- `read_count >= 5` (statistically meaningful), AND
- read rate > 50% of that skill's runs in the window

…and the file is NOT already in the skill's `context_files` frontmatter:
propose a `change_type=context-files` **addition**. This is a zero-cost win:
pre-loading a file the session would Read anyway saves a tool call.

### When to propose removals from `context_files`

For each `(skill, file_path)` pair where:
- `read_count >= 5`, AND
- read rate < 10%

…and the file IS in the skill's `context_files` frontmatter:
propose a `change_type=context-files` **removal**. The file is wasting
static context budget without being useful.

### Dedup

Use the Rec 10 dedup flow: call `find_recent_duplicate(target_file, "context-files")`
before inserting. Include `Proposal-ID:` in the dispatched PR body.

## Proposal tracking (Rec 10)

Every proposal is recorded in the `proposals` database table so we can
track what got proposed, what got applied, and avoid re-proposing rejected
or still-pending ideas. Use the `src.runner.proposals` helpers.

### Before proposing: dedup check

```python
from src.runner.proposals import find_recent_duplicate

dup = await find_recent_duplicate(
    target_file="skills/research-report/SKILL.md",
    change_type="frontmatter-tweak",   # one of: default-model | context-files |
                                       #        frontmatter-tweak | doc-update
    lookback_days=30,
)
if dup is not None:
    # Already proposed within the last 30 days; skip
    # Include in summary: "previously proposed (id abc12345), skipping"
    ...
```

The partial index on `(target_file, change_type) WHERE outcome IN
('pending', 'rejected')` keeps this lookup cheap.

### When proposing: insert + embed id in PR body

```python
from src.runner.proposals import insert_proposal

prop = await insert_proposal(
    proposed_by_job_id=<this_job_uuid>,
    target_file="skills/research-report/SKILL.md",
    change_type="frontmatter-tweak",
    rationale="Reduce max_turns from 40 to 30; 98% of runs finish by turn 18.",
)
pr_body = f"""...your PR description...

Proposal-ID: {prop.id}
"""
# Dispatch server-patch with this pr_body so the id survives into GitHub.
```

`server-patch` detects the `Proposal-ID:` marker on merge and flips the
outcome to `merged`. Without the marker, the proposal stays `pending`
forever even after a successful merge, which defeats dedup.

### Summary reporting

In your final summary include two counts:
- `proposed: N` — new proposals created this run
- `skipped-dup: M` — proposals that matched a recent existing row

Users can view pending proposals via the `/proposals` Telegram command.

## Gotchas (living section — append when you learn something)

- **Skip low-sample skills**: Do not propose changes for skills with fewer
  than 5 runs in the analysis period. The data is not statistically
  meaningful.
- **Do not repeat proposals**: Before proposing, check the `proposals` table
  (see "Proposal tracking" section above) — if a row with the same
  `target_file` and `change_type` has outcome in (`pending`, `rejected`)
  within the last 30 days, skip it. Note it in the summary as "previously
  proposed (id `<8-char>`), skipping."
- **Never propose changes to `.env` or auth config**: These are out of scope.
  If the data suggests an auth-related issue, flag it for human review in
  your summary but do not propose a code change.
- **Never propose changes to `.context/PROTOCOL.md`**: This requires explicit
  human request.
- **Plan mode means read-only**: You cannot and should not modify files. Your
  output is analysis and a dispatch. The `server-patch` job does the actual
  implementation.
- **The `enqueue_job` MCP tool** is provided by the dispatch MCP server. If
  it is not available, output your proposals as text and note that dispatch
  was not possible — the user can manually create the server-patch job.
- **Rating column may not exist yet**: The `rating` column is planned but may
  not be in the schema. If the ratings query fails, skip that criterion and
  note it in your summary.
