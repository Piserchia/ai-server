# Phase 6 — Polish

> **For the Claude Code session executing this**: Phase 6 is the final planned
> phase. By the time you're building this, the system is self-maintaining
> (Phase 5), can patch itself and add projects (Phase 4), is publicly hosted
> (Phase 3), and has one working content-producing skill (Phase 2). Phase 6
> fills in remaining skills and the nice-to-have features that were deferred
> from earlier phases because they weren't load-bearing.

## Goal

Fill in the skill catalog, make day-to-day operation more convenient, and
add the last pieces of auto-tuning infrastructure that the `review-and-improve`
skill (Phase 5) is expected to consume.

## Done =

All of these work:

1. `/task deep research: <topic>` → spawns `research-deep` skill (Opus 4.7 / high),
   produces a long-form report with more sources, more synthesis, explicit
   "disputes in the literature" section. Drops to `projects/research-deep/`.
2. Scheduled `idea-generation` runs weekly, produces 3-5 ideas, dedupes against
   history, DMs TL;DR. Ideas stored in `projects/ideas/`.
3. `project-update-poll` runs per-project on its own cron, cheap (Haiku 4.5 / low),
   refreshes the project's underlying data (market-tracker prices, nba-scores,
   etc.). Fails cleanly; never blocks other jobs.
4. `/task restore <backup-date>` works: unpacks the tarball, restores pg_dump,
   writes audit logs back, reports success or failure.
5. `/schedule` command in Telegram for creating/listing/pausing schedules
   without touching SQL.
6. Web dashboard has a live-streaming job-detail view via SSE. Open a job mid-run
   and watch tool calls stream in real time.
7. Auto-tuning retrospective query is working — `review-and-improve` has real
   data (`jobs.resolved_model × resolved_effort × outcome × rating`) grouped
   and summarized.
8. Optional: cloud backup target (Backblaze B2) configured if `B2_ACCOUNT_ID`
   is set in `.env`; falls back to local-only if not.

## Status

- [ ] `research-deep` skill
- [ ] `idea-generation` skill
- [ ] `project-update-poll` skill
- [ ] `restore` skill
- [ ] `/schedule` command in Telegram
- [ ] SSE streaming for job detail (web)
- [ ] Auto-tuning retrospective query module
- [ ] B2 backup target (optional)
- [ ] Documentation: PHASE_6_PLAN as executed

## Decisions locked in

- **`research-deep` is its own skill, not a flag on `research-report`**: different
  model tier, different expectations, different project directory. Keep them
  separate so users can discover the distinction.
- **Ideas go in their own project** (`projects/ideas/`), not a DB table. Same
  rationale as research: markdown files are grep-able, git-tracked, portable.
- **`project-update-poll` is per-project, not global**: each project's
  `manifest.yml` declares its own `on_update.cron` and `on_update.command`.
  The skill just executes what the manifest says.
- **`/schedule` command is read-add-pause only, not edit**: editing a schedule
  is rare and dangerous. For edits: pause old, create new. Simpler mental model.
- **SSE over WebSocket for job streaming**: FastAPI has first-class SSE via
  `sse-starlette`, browsers support it natively with `EventSource`, no
  additional deps. WebSocket would be overkill for one-way push.
- **Cloud backup is optional**: add code path, but don't require B2 creds.
  Local-only is the default; `B2_ACCOUNT_ID` being set enables upload.
- **No Grafana, no Prometheus**: the dashboard and `psql` queries are the UI.
  Phase 6 does NOT add new observability stacks.

## Open decisions (Chris resolves before execution)

### 6.1. Ideas publishing — private or public?

The `ideas` project directory can be either:

- **Private**: git-tracked locally and on GitHub (`Piserchia/ideas`, private),
  not served publicly.
- **Public-to-you**: served at `ideas.<domain>` behind Cloudflare Access (you
  can read from anywhere; world can't).
- **Fully public**: `ideas.<domain>` open to the internet. Portfolio-style.

Recommended: **private** — ideas are often half-baked. Can change later with
one line in manifest.yml.

### 6.2. Cloud backup target

Options if you want offsite backup:

- **Backblaze B2** (recommended): $6/TB/month, S3-compatible API, low friction
  setup. A year of daily backups of a personal server is well under 100 GB,
  so effectively ~$0.50/month.
- **iCloud Drive**: free with your iCloud plan, but mounting inside launchd
  is flaky. Not recommended for automation.
- **A private GitHub repo**: abusing it. The backup is binary data + pg_dump;
  git LFS works but is also awkward. Skip.
- **External USB drive**: works but isn't offsite. Fine as a supplement.

Recommended: **B2 if you want offsite backup; skip entirely if not**. The local
backup is already sufficient for "I fat-fingered a DELETE" recovery; offsite is
for "the Mac Mini is physically destroyed."

### 6.3. `project-update-poll` frequency defaults

Should there be a global min/max frequency cap? E.g., "no project may poll more
often than every 5 minutes" to avoid one bad manifest hammering the API.

Recommended: **yes**, enforce `min_interval_seconds: 300` in `manifest.py` validation.
Projects can override in their own manifest but the default validator rejects
`*/1 * * * *` cron expressions for `on_update`.

---

## Architecture refresher

### Skill model tier map (as of Phase 6 complete)

| Tier | Model | Effort | Skills |
|------|-------|--------|--------|
| Haiku (cheap, volume) | Haiku 4.5 | low | `project-update-poll` |
| Sonnet default | Sonnet 4.6 | low-medium | `chat`, `_writeback`, `idea-generation`, `new-project` (simple), `research-report`, `server-upkeep`, `restore` |
| Sonnet quality | Sonnet 4.6 | high | `new-project` (escalated), `notify-me` |
| Opus default | Opus 4.7 | high | `app-patch`, `code-review`, `research-deep`, `self-diagnose` |
| Opus deep | Opus 4.7 | xhigh | `server-patch`, `new-skill` |
| Opus max (plan mode) | Opus 4.7 | max | `review-and-improve` |

### Data collection surface (for auto-tuning)

Every job writes to:
- `jobs.resolved_skill` — what ran
- `jobs.resolved_model` — what model
- `jobs.resolved_effort` — what effort level
- `jobs.status` — outcome
- `jobs.user_rating` — 1-5 if set via `/rate`
- `jobs.review_outcome` — LGTM / changes_requested / blocker if code-review ran
- `jobs.completed_at - started_at` — latency
- `jobs.result.tokens_used` — (if SDK populated) model token cost
- `jobs.error_message` — if failed

The monthly retrospective query in Phase 5 joins these and produces a tuning
report. Phase 6 finalizes the SQL and ensures all the columns are populated.

---

## File-by-file plan

### `skills/research-deep/SKILL.md` (new)

Longer, slower version of `research-report`. Targets `projects/research-deep/`
(separate from research-report's `projects/research/`).

```yaml
---
name: research-deep
description: Deep-dive research. More sources, more synthesis, explicit treatment of conflicting evidence.
model: claude-opus-4-7
effort: high
permission_mode: acceptEdits
required_tools: [Read, Write, Edit, Bash, Glob, Grep, WebSearch, WebFetch, AskUserQuestion]
max_turns: 80
escalation:
  on_failure:
    model: claude-opus-4-7
    effort: xhigh
tags: [research, writing, slow, high-quality]
---
```

Body differences from `research-report`:

- **Source count**: 10-20 sources for standard, 20-40 for deep. Explicitly
  instruct Claude to keep searching until it has multiple independent primary
  sources on each major claim.
- **Disputes section required**: every deep report has a `## Where sources
  disagree` section, even if short. If there's no disagreement, say so
  explicitly (often a sign we haven't searched adversarially enough).
- **Methodology section required**: `## How I researched this` — 1-2 paragraphs
  describing search strategy, what got cut, what you'd still want.
- **Length target**: 2000-5000 words vs research-report's 500-1500.
- **Templates**: reuse `skills/research-report/templates/` — the research-deep
  skill writes to its own `projects/research-deep/` but uses identical
  scaffolding conventions.

**Gotchas to include in the SKILL.md**:
- Deep research on recent fast-moving topics (last 72 hours) usually isn't
  deep, it's shallow with more words. Prefer evergreen or 1-month-old topics
  for "deep." Warn the user if the topic is too recent.
- Paywall encounters: note them explicitly; do not paraphrase a source you
  couldn't read. Listed as "paywalled" in sources.

### `skills/idea-generation/SKILL.md` (new)

```yaml
---
name: idea-generation
description: Generates 3-5 novel ideas on a topic, dedupes against prior ideas.
model: claude-sonnet-4-6
effort: medium
permission_mode: acceptEdits
required_tools: [Read, Write, Edit, Bash, Glob, Grep]
max_turns: 20
tags: [creative, scheduled-capable]
---
```

Body:

1. **Inputs**: `topic` (required), `count` (default 3), `style` (default
   "actionable" — alternatives: "speculative", "technical-only", "product-only").
2. **Read prior ideas**: `cat projects/ideas/history.jsonl` — get the list of
   titles and one-line descriptions of past ideas on this topic. This is the
   dedup set.
3. **Generate candidates**: produce 2x the requested count internally.
4. **Filter against dedup set**: reject any candidate that's <0.8 similar
   (semantic proximity, your best judgment) to a prior idea.
5. **Write output**: `projects/ideas/<topic-slug>-YYYY-MM-DD.md` with:
   - one H2 per idea
   - description (2-3 sentences)
   - "Why now" (1 sentence)
   - "Hardest part" (1 sentence)
   - "First concrete step if I started today" (1 sentence)
6. **Append to history.jsonl**: one JSON line per idea for the dedup set.
7. **Commit + DM TL;DR**.

**Scheduling**: there is a row in `schedules` seeded in Phase 5 that runs this
weekly on Monday at 9am. Seed a few topics (`"developer tools"`, `"sports
betting analytics"`, `"crypto infrastructure"`) — Chris can add/remove via
`/schedule`.

### `skills/project-update-poll/SKILL.md` (new)

Per-project data refresh, very cheap. Driven by the project's `manifest.yml`.

```yaml
---
name: project-update-poll
description: Runs a project's configured update command. Cheap, fast, fail-silent.
model: claude-haiku-4-5-20251001
effort: low
permission_mode: acceptEdits
required_tools: [Read, Bash]
max_turns: 4
tags: [scheduled, per-project, cheap]
---
```

Body:

1. Expect `payload.project_slug` — error out if missing.
2. Read `projects/<slug>/manifest.yml`. If no `on_update` section, exit with
   "no update configured; no-op."
3. Run `on_update.command` with cwd = `projects/<slug>`.
4. Capture stdout/stderr to audit log.
5. If exit code 0: done, short success message.
6. If nonzero: one retry after 60s. If still fails, log and give up. Do NOT
   enqueue self-diagnose — that's too expensive for a polling failure.
   (If a project's update fails 5x in a row, healthcheck-all's noticing logic
   from Phase 5 should flag it.)

**Why Haiku**: 99% of invocations are "run this bash command and report back."
Haiku is perfect for this. Cost: ~100 tokens per invocation.

**Scheduling**: driven by per-project manifest. `register-project.sh` (Phase 3)
already parses `on_update.cron` and adds a row to `schedules` pointing at
this skill. No additional seeding needed — Phase 6 just ships the skill.

### `skills/restore/SKILL.md` (new)

Inverse of `backup` from Phase 5. User-initiated, careful.

```yaml
---
name: restore
description: Restore from a backup tarball. DESTRUCTIVE — overwrites current state.
model: claude-sonnet-4-6
effort: medium
permission_mode: default
required_tools: [Read, Write, Edit, Bash, Glob, Grep, AskUserQuestion]
max_turns: 30
tags: [operations, destructive]
---
```

Body:

1. **Confirm via `AskUserQuestion`**: "You're about to restore from <date>.
   This will DROP the current jobs table and restore it from backup. Type
   EXACTLY 'RESTORE <date>' to proceed."
2. **Stop runner + web + bot** so nothing writes during restore:
   ```bash
   bash scripts/run.sh stop
   ```
3. **Verify tarball exists and integrity**:
   ```bash
   tar -tzf volumes/backups/<date>.tar.gz > /dev/null || exit 1
   ```
4. **Extract to temp**:
   ```bash
   TEMP=$(mktemp -d)
   tar -xzf volumes/backups/<date>.tar.gz -C "$TEMP"
   ```
5. **Restore pg_dump**:
   ```bash
   dropdb assistant --if-exists
   createdb assistant
   psql assistant < "$TEMP/pg_dump.sql"
   ```
6. **Restore audit logs** (additive — don't overwrite newer logs):
   ```bash
   rsync -a "$TEMP/audit_log/" volumes/audit_log/
   ```
7. **Restart services**:
   ```bash
   bash scripts/run.sh start
   ```
8. **Report**: number of jobs restored, date range, any anomalies.

**Hard rules**:
- NEVER restore without AskUserQuestion confirmation.
- NEVER delete existing backups during a restore (user may want them for forensics).
- NEVER restore from a backup older than 30 days without a second confirmation.

**Gotchas**:
- Research-report reports and project CHANGELOGs aren't in backups (they're in
  their own git repos). If you need to restore a project's state, `git reset
  --hard` to the appropriate date inside that project's dir. Document this
  in the final summary.

### `src/gateway/telegram_bot.py` — add `/schedule` command

Allow schedule management from Telegram:

```
/schedule list                          — list all schedules with next run time
/schedule add <name> <cron> <kind>: <description>
                                        — create a new schedule
/schedule pause <name>                  — pause a schedule
/schedule resume <name>                 — resume a paused schedule
```

Implementation (add to `cmd_schedule` in telegram_bot.py):

```python
async def cmd_schedule(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if await _guard(update) is None:
        return
    args = ctx.args
    if not args:
        await update.message.reply_text(
            "Usage: /schedule {list|add|pause|resume} [args]"
        )
        return

    sub = args[0].lower()
    if sub == "list":
        async with async_session() as s:
            rows = list((await s.execute(select(Schedule).order_by(Schedule.name))).scalars())
        if not rows:
            await update.message.reply_text("No schedules configured.")
            return
        lines = ["*Schedules:*"]
        for sched in rows:
            status = "⏸" if sched.paused else "▶"
            next_run = sched.next_run_at.strftime("%Y-%m-%d %H:%M") if sched.next_run_at else "never"
            lines.append(f"{status} `{sched.name}` ({sched.cron_expression}) next: {next_run}")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    elif sub == "add":
        # Format: /schedule add <name> <cron-5-fields> <kind>: <description>
        # Example: /schedule add weekly-crypto "0 9 * * 1" research_report: weekly crypto summary
        raw = " ".join(args[1:])
        # Parse: <name> "<cron>" <kind>: <desc>   OR   <name> <cron> <kind>: <desc>
        # ... (parser implementation)

    elif sub == "pause":
        name = args[1]
        async with session_scope() as s:
            await s.execute(
                sql_update(Schedule).where(Schedule.name == name).values(paused=True)
            )
        await update.message.reply_text(f"Paused `{name}`.", parse_mode="Markdown")

    elif sub == "resume":
        # similar
```

**Gotchas**:
- Cron parsing: use `croniter` (already imported by runner). Validate the
  expression before committing.
- Name collisions: unique constraint on `schedules.name` handles this; catch
  the IntegrityError and reply with a helpful message.

### `src/gateway/web.py` — add SSE streaming endpoint

```python
from sse_starlette.sse import EventSourceResponse

@app.get("/api/jobs/{job_id}/stream", dependencies=[Depends(_check_auth)])
async def stream_job(job_id: str):
    job = await find_job_by_prefix(job_id)
    if not job:
        raise HTTPException(404)

    async def event_generator():
        # 1. Send everything in the audit log so far
        existing = audit_log.read(job.id, limit=500)
        for evt in existing:
            yield {"event": "audit", "data": json.dumps(evt)}

        # 2. If job is still running, subscribe to Redis streams for new events
        if not JobStatus(job.status).is_terminal:
            pubsub = redis.pubsub()
            await pubsub.subscribe(f"{CHANNEL_JOB_STREAM}:{job.id}")
            try:
                async for msg in pubsub.listen():
                    if msg.get("type") != "message":
                        continue
                    yield {"event": "audit", "data": msg.get("data", "")}
                    # Check terminal state periodically
                    async with async_session() as s:
                        j = await s.get(Job, job.id)
                        if j and JobStatus(j.status).is_terminal:
                            yield {"event": "done", "data": j.status}
                            break
            finally:
                await pubsub.unsubscribe(f"{CHANNEL_JOB_STREAM}:{job.id}")

    return EventSourceResponse(event_generator())
```

**Frontend changes** (in the `_INDEX_HTML` template):

Add a "Live" button on each running job that opens a modal with:

```javascript
const source = new EventSource(`/api/jobs/${id}/stream`);
source.addEventListener("audit", (e) => {
    const event = JSON.parse(e.data);
    appendToModal(event);
});
source.addEventListener("done", (e) => {
    source.close();
});
```

**Gotchas**:
- Auth on SSE: `EventSource` doesn't support custom headers; use a query
  param `?token=` OR set the cookie. Query param is simpler for single-user.
- Backpressure: if Claude emits 500 events/sec the browser falls behind.
  Throttle server-side to max 10 events/sec by batching.
- The runner must publish to `{CHANNEL_JOB_STREAM}:{job.id}` during execution.
  Add to `session.py`'s message handler:
  ```python
  await redis.publish(f"{CHANNEL_JOB_STREAM}:{job_id}", json.dumps(event_dict))
  ```

### `src/runner/retrospective.py` (new) — auto-tuning query module

This is the module `review-and-improve` (Phase 5) imports to fetch its data.

```python
"""
Rollup queries for the auto-tuning retrospective.

Used by:
- The review-and-improve skill (Phase 5) when running its monthly pass
- The dashboard, eventually, for a "performance" tab
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from src.db import async_session
from src.models import Job, JobStatus


@dataclass
class SkillPerformance:
    skill: str
    model: str | None
    effort: str | None
    count: int
    success_rate: float
    avg_latency_s: float | None
    avg_rating: float | None
    review_lgtm_rate: float | None


async def skill_performance(
    since: datetime | None = None,
    until: datetime | None = None,
) -> list[SkillPerformance]:
    """Rollup of jobs by (resolved_skill, resolved_model, resolved_effort)."""
    since = since or (datetime.now(timezone.utc) - timedelta(days=30))
    until = until or datetime.now(timezone.utc)

    async with async_session() as s:
        q = (
            select(
                Job.resolved_skill,
                Job.resolved_model,
                Job.resolved_effort,
                func.count(Job.id).label("total"),
                func.sum(
                    (Job.status == JobStatus.completed.value).cast(func.Integer)
                ).label("completed"),
                func.avg(
                    func.extract("epoch", Job.completed_at - Job.started_at)
                ).label("avg_latency"),
                func.avg(Job.user_rating).label("avg_rating"),
                func.sum(
                    (Job.review_outcome == "LGTM").cast(func.Integer)
                ).label("lgtm_count"),
                func.sum(
                    Job.review_outcome.isnot(None).cast(func.Integer)
                ).label("reviewed_count"),
            )
            .where(Job.created_at >= since, Job.created_at <= until)
            .where(Job.resolved_skill.isnot(None))
            .group_by(Job.resolved_skill, Job.resolved_model, Job.resolved_effort)
        )
        result = await s.execute(q)
        rows = result.all()

    out: list[SkillPerformance] = []
    for r in rows:
        out.append(SkillPerformance(
            skill=r.resolved_skill,
            model=r.resolved_model,
            effort=r.resolved_effort,
            count=r.total,
            success_rate=(r.completed or 0) / r.total if r.total else 0,
            avg_latency_s=float(r.avg_latency) if r.avg_latency else None,
            avg_rating=float(r.avg_rating) if r.avg_rating else None,
            review_lgtm_rate=(r.lgtm_count / r.reviewed_count)
                if r.reviewed_count else None,
        ))
    return out


async def model_effort_comparison() -> list[dict[str, Any]]:
    """For same-skill rows, compare different (model, effort) combos."""
    # Pseudocode — returns rows like:
    # { "skill": "research-report",
    #   "configs": [
    #     {"model": "sonnet-4-6", "effort": "medium", "count": 42, "success": 0.91, "rating": 4.2},
    #     {"model": "opus-4-7", "effort": "high", "count": 5, "success": 1.0, "rating": 4.8},
    #   ],
    #   "recommendation": "opus-4-7/high marginally better (4.8 vs 4.2) but 5x cost; keep sonnet default" }
    ...
```

The `review-and-improve` SKILL.md (Phase 5) consumes this module:

```python
from src.runner.retrospective import skill_performance, model_effort_comparison

perf = await skill_performance()
# Format perf into a markdown table, propose PRs
```

### `scripts/backup.sh` — add optional B2 upload

Extend the Phase 5 backup script:

```bash
#!/usr/bin/env bash
# ... existing backup logic that produces volumes/backups/<date>.tar.gz ...

# Optional: upload to B2 if configured
if [ -n "${B2_ACCOUNT_ID:-}" ] && [ -n "${B2_APPLICATION_KEY:-}" ] \
   && [ -n "${B2_BUCKET:-}" ]; then
    if command -v b2 &>/dev/null; then
        b2 authorize-account "$B2_ACCOUNT_ID" "$B2_APPLICATION_KEY" \
            >/dev/null 2>&1
        b2 upload-file "$B2_BUCKET" \
            "volumes/backups/${DATE}.tar.gz" \
            "backups/${DATE}.tar.gz"
        echo "  ✓ uploaded to B2"
    else
        echo "  ⚠ B2 creds set but 'b2' CLI not installed; skipping upload"
        echo "    install with: pip install --user b2"
    fi
fi
```

Add to `.env.example`:
```
# Optional: Backblaze B2 for offsite backups
# B2_ACCOUNT_ID=
# B2_APPLICATION_KEY=
# B2_BUCKET=ai-server-backups
```

### `.context/modules/hosting/CONTEXT.md` — document SSE streaming

Add a section:
```
### SSE streaming (Phase 6)

The dashboard supports live job tailing via Server-Sent Events. The runner's
session.py publishes every audit event to `jobs:stream:<job_id>`; the web
gateway's `/api/jobs/<id>/stream` endpoint subscribes and re-emits as SSE.

When streaming is enabled, audit log events go to TWO destinations:
1. The JSONL file on disk (authoritative, permanent)
2. The Redis pub/sub channel (ephemeral, for live viewing only)

If Redis is down, streaming fails but the JSONL file is still written. The
runner does NOT block on publish failures.
```

---

## Runbook

Phase 6 is multiple small features; build each as its own commit, test, merge.

### Step 1 — research-deep

```bash
# Build
cd "$HOME/Library/Application Support/ai-server"
mkdir -p skills/research-deep
# Copy research-report's SKILL.md, edit frontmatter + body per plan above
cp skills/research-report/SKILL.md skills/research-deep/SKILL.md
vi skills/research-deep/SKILL.md  # adjust

# Test
/task deep research: the semiconductor export controls and their effect on NVIDIA

# Verify
ls projects/research-deep/
cat projects/research-deep/.context/CHANGELOG.md

# Commit
git add skills/research-deep/
git commit -m "Phase 6: research-deep skill"
git push
```

### Step 2 — idea-generation

```bash
mkdir -p skills/idea-generation projects/ideas/.context
# Build SKILL.md + history.jsonl initial structure
# Test: /task generate ideas for developer tools
# Commit
```

### Step 3 — project-update-poll

```bash
mkdir -p skills/project-update-poll
# Build SKILL.md per plan

# Test with a real project that has on_update:
# Add to projects/market-tracker/manifest.yml:
#   on_update:
#     cron: "*/15 * * * *"
#     command: "pipenv run python scripts/refresh.py"

# Re-run register-project.sh to update the schedule
bash scripts/register-project.sh market-tracker

# Verify schedule appears:
psql assistant -c "SELECT name, cron_expression FROM schedules WHERE job_kind = 'project_update_poll';"

# Force immediate run:
psql assistant -c "UPDATE schedules SET next_run_at = now() WHERE name LIKE 'update:market-tracker%';"

# Watch runner logs
tail -f volumes/logs/runner.log
```

### Step 4 — restore

```bash
mkdir -p skills/restore
# Build SKILL.md per plan

# Test carefully — DON'T run restore in production without a fresh backup
# Create a safe test: make a backup, modify DB trivially, restore, verify

# Example test:
bash scripts/backup.sh                                # creates today's backup
psql assistant -c "UPDATE projects SET slug = 'bogus' WHERE slug = 'bingo';"
/task restore 2026-MM-DD                              # where DD is today
# Answer the AskUserQuestion prompt with 'RESTORE 2026-MM-DD'
psql assistant -c "SELECT slug FROM projects WHERE slug = 'bingo';"  # should be restored
```

### Step 5 — /schedule command

```bash
# Implement in src/gateway/telegram_bot.py
# Update .context/modules/gateway/CONTEXT.md
# Restart bot
bash scripts/run.sh restart

# Test
# Telegram: /schedule list
# Telegram: /schedule add weekly-ideas "0 9 * * 1" idea_generation: weekly dev tool ideas
# Telegram: /schedule pause weekly-ideas
# Telegram: /schedule resume weekly-ideas
```

### Step 6 — SSE streaming

```bash
# Add sse-starlette to pyproject.toml
pipenv install sse-starlette

# Implement endpoint in src/gateway/web.py
# Add publish() calls in src/runner/session.py
# Update dashboard HTML with live button + EventSource handling

# Test: open dashboard, submit a long-running job, click "Live"
# Verify events stream in
```

### Step 7 — retrospective module

```bash
# Create src/runner/retrospective.py

# Test query directly:
pipenv run python -c "
import asyncio
from src.runner.retrospective import skill_performance
async def main():
    rows = await skill_performance()
    for r in rows:
        print(f'{r.skill} {r.model}/{r.effort}: {r.count} runs, {r.success_rate:.0%} success')
asyncio.run(main())
"

# Wire review-and-improve skill (Phase 5) to use it
```

### Step 8 — B2 backup (optional)

```bash
# If you decide to enable:
pip install --user b2
b2 authorize-account <account_id> <app_key>
b2 create-bucket ai-server-backups allPrivate

# Add credentials to .env
vi .env   # fill in B2_ACCOUNT_ID, B2_APPLICATION_KEY, B2_BUCKET

# Update scripts/backup.sh per plan
# Run manually to verify upload:
bash scripts/backup.sh

# Check B2 bucket
b2 ls ai-server-backups
```

### Step 9 — commit + close out

```bash
git add -A
git commit -m "Phase 6: polish (research-deep, idea-generation, project-update-poll, restore, /schedule, SSE, retrospective)"
git push origin main

# Update MISSION.md — mark Phase 6 complete
sed -i 's|Phase 6 — Polish | planned|Phase 6 — Polish | **SHIPPED** |' MISSION.md
git commit -am "MISSION.md: Phase 6 complete"
git push
```

---

## Rollback

Phase 6 additions are low-risk — all new files or isolated additions. Rollback
is granular:

- **Disable a skill**: `mv skills/<n> skills/<n>.disabled`
- **Disable /schedule command**: comment out the handler registration in telegram_bot.py, restart bot
- **Disable SSE**: comment out the route + pub calls in session.py
- **Disable B2 upload**: unset `B2_ACCOUNT_ID` in `.env`

Hard revert: `git reset --hard <phase-5-sha>` and restart services.

---

## NOT in Phase 6

- **Grafana / Prometheus / OpenTelemetry**: overkill for a personal server.
- **Multi-user support**: the system is single-tenant by design. Adding users
  would mean auth on every endpoint, per-user queues, per-user quotas — a
  separate project, not a polish phase.
- **Mobile app**: the web dashboard is mobile-responsive enough.
- **Push notifications via APNs/FCM**: Telegram is the push channel.
- **Voice interface**: no.
- **AutoML / fine-tuning**: we're not training models.
- **A public API for third parties**: stays private to Chris forever.

---

## After Phase 6

Phase 6 is the last planned phase. After it, the system is "done" in the sense
that it serves the original mission. Ongoing work splits into three streams:

### Stream 1: Skill library growth

The system can add new skills via `/task new skill:`. Any capability gap
Chris notices in daily use gets filled by using the system itself. Expected
examples:

- `summarize-git-activity` — weekly summary of what projects changed
- `transcribe-and-notify` — voice note → transcription → Telegram DM
- `email-triage` (if Gmail MCP comes back)
- `crypto-price-alert` — watch for thresholds
- `bracket-optimizer` (resurrected from old system)

Each one is a `/task new skill:` invocation, reviewed, merged. No plan doc
needed per skill — the skill *is* the doc.

### Stream 2: Project additions

Same mechanism (`/task new project:`). Projects accumulate; some are
experimental (let them go stale, eventually `/task remove project:`), others
become load-bearing and get `app-patch`'d over time.

### Stream 3: System improvements via `review-and-improve`

The monthly retrospective is now running with full data. Over time it proposes:

- Default model/effort changes per skill (e.g., "research-report at high
  effort is only 3% better than medium but 2x slower; propose default medium")
- Threshold adjustments (quota pause minutes, healthcheck intervals)
- New skills that would fill observed gaps (e.g., "many tasks are landing in
  the generic-task fallback; propose a new routing rule + skill")
- Deprecation of under-used skills

Each proposal is a PR against `Piserchia/ai-server`. Chris reviews, merges or
closes, and the system learns from the merge rate.

---

**Phase 6 is the last documented phase.** If you're building something that
doesn't fit any phase plan, it belongs in Stream 1/2/3 above. If you're
unsure, the bar for "new phase plan" is high: it needs to represent
architectural change, not just capability addition.

---

## Checklist for Phase 6 complete

- [ ] `research-deep` skill shipped, one sample report created, committed
- [ ] `idea-generation` skill shipped, weekly schedule seeded, one sample batch generated
- [ ] `project-update-poll` skill shipped, at least one project using it end-to-end
- [ ] `restore` skill shipped, tested on a sandbox DB
- [ ] `/schedule` command in Telegram working for list/add/pause/resume
- [ ] SSE streaming endpoint working, dashboard "Live" button working
- [ ] `src/runner/retrospective.py` shipped, `skill_performance()` returns sensible data
- [ ] `review-and-improve` skill (Phase 5) updated to use retrospective module
- [ ] B2 backup target decided + configured (or explicitly skipped)
- [ ] Tests added for new pure functions (e.g., schedule name parsing, retrospective rollup)
- [ ] MISSION.md updated — Phase 6 marked shipped
- [ ] All CHANGELOGs updated per write-back protocol
- [ ] Committed, pushed
