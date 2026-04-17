# Phase 5 — Operations

> **For the Claude Code session executing this**: Phase 5 is the "don't think
> about it for a week" phase. The server maintains itself on a schedule,
> backs itself up, and proposes improvements via PR instead of silently
> editing. Every skill here has a schedule (not user-triggered).

## Goal

Server runs for a week with zero intervention. At the end of the week:
- A nightly backup exists with last 7 days retained
- Daily upkeep has rotated logs, VACUUMed the DB, checked cert expiry,
  notified you of any anomalies
- A monthly retrospective has opened at least one PR proposing a tuning
  change based on actual job data

## Done =

- Nightly `backup` job runs at 04:00, produces `volumes/backups/<date>.tar.gz`
  containing pg_dump + audit_log snapshot + recent logs, keeps last 7
- Daily `server-upkeep` job runs at 03:00, Telegram-DMs you a one-line
  summary (or silent if nothing noteworthy)
- `healthcheck-all` already installed in Phase 3 keeps running
- `review-and-improve` runs monthly, produces a PR against ai-server with
  proposed changes to skills / defaults / thresholds
- `server-patch` skill works: requires `code-review` LGTM + manual merge, no
  auto-merge ever
- Cloudflare Access policy on the dashboard (not the apex, just `dashboard.<domain>`)
  so only you can log in even if the token leaks

## Status

Not started. Phases 1-4 are prerequisites. `server-upkeep` depends on all the
`jobs` table columns Phase 1 created; `review-and-improve` depends on real
data in `jobs` from Phases 2-4 actually running.

## Decisions locked in

1. **Schedules live in the `schedules` table**, not in crontab. The scheduler
   loop in the runner already picks them up.
2. **`server-upkeep` runs Sonnet 4.6 / low** (most days it's a no-op report;
   escalates to medium if it needs to investigate something).
3. **`backup` is a bash script, not an LLM skill**. Backups are
   trivial-and-exact; LLM overhead is pure waste here. Schedule it as a
   launchd StartCalendarInterval plist, not via the `schedules` table.
4. **`server-patch` always requires manual merge** per MISSION INV-4. The
   skill generates the branch + PR + summary; the human hits "Merge".
5. **`review-and-improve` runs Opus 4.7 / max in plan mode** — it analyzes,
   it does not execute. Output is a PR.
6. **Cloudflare Access free plan is enough** — up to 50 users, email-based
   auth, 1 application (we'll protect `dashboard.<domain>` only).

## Open decisions

### 1. Backup retention and destination

- **Local only** (volumes/backups/): simple, fast, but the backup is on the
  same disk as the data it's backing up. If the disk dies, both are gone.
- **Local + cloud** (rclone to a B2 bucket, S3, or iCloud Drive): safer, but
  adds a dependency and a small monthly cost.

**Recommendation**: start local-only (retain 7 days). Phase 6 adds a
`backup-cloud` optional extension if you want it.

### 2. What does `server-upkeep` DM you about?

The risk is alert fatigue. If every quiet day pings you, you ignore the
pings, and then real alerts get missed.

**Recommendation**: silent-by-default. Only DM when something's interesting:
- Disk usage crossed a threshold (80%, 90%)
- A project's `last_healthy_at` is > 24h old
- A cert expiry is < 14 days
- The `_writeback` skill ran more than 20 times in a day (suggests a skill
  author forgot write-back — something to fix)
- Any server process has been restarted > 3 times in a day

If all quiet: one weekly "all quiet" summary on Sunday 10am so you know the
job is alive.

### 3. `review-and-improve` cadence

Monthly is traditional, but the interesting signal accumulates faster when
the system is new (Phases 4-5). Options:

- **Weekly** for the first 2 months, then monthly — aggressive iteration
  while tuning defaults
- **Monthly** from the start — less noise

**Recommendation**: weekly for the first 4 weeks, then switch to monthly. The
`server-upkeep` logic can adjust the cron when it detects > 100 jobs/week
of data (mature enough to slow down cadence).

### 4. Auto-tuning PR merge policy

- **All retrospective-proposed PRs require manual merge** (consistent with
  server-code policy)
- **PRs to skill files only may auto-merge on code-review LGTM** (consistent
  with skill-code policy from Phase 4)

**Recommendation**: the second. The whole point of separating "skills" from
"server code" was to enable this.

---

## Architecture refresher

Phase 5 adds three things to the running system:

### A. Scheduled jobs beyond research reports

Until now, only `research-report` had schedules (manually inserted into the
`schedules` table). Phase 5 adds a set of server-owned schedules:

| Name | Cron | Kind | Purpose |
|---|---|---|---|
| `server-upkeep-daily` | `0 3 * * *` | `server-upkeep` | Daily audit + log rotation + DB vacuum + summary |
| `server-backup-nightly` | `0 4 * * *` | (not via jobs queue — launchd directly) | pg_dump + tarball + retention |
| `review-and-improve-weekly` | `0 0 * * MON` | `review-and-improve` | Weekly proposed-tuning PR (first 4 weeks) |
| `review-and-improve-monthly` | `0 0 1 * *` | `review-and-improve` | Monthly after weekly period |

These are inserted via a `scripts/seed-schedules.sh` that's idempotent.

### B. `server-patch` — the manually-gated server code path

Works like `app-patch` but:
- cwd = server_root (not a project)
- `patch_mode` is always `pr` (branch + PR, no direct commit to main, ever)
- Post-review is always triggered
- Auto-merge is always disabled — the PR stays open until you merge on GitHub
- Logs what the change is and why; includes a rollback commit in the PR description

### C. `review-and-improve` — the auto-tuner

Queries `jobs` table aggregated by `(resolved_skill, resolved_model, resolved_effort, status)`. Looks for:

- A skill where `status='failed'` rate is > 25% → consider escalating default model
- A skill where user `rating` avg is < 3 (when > 5 ratings exist) → investigate
- A `(skill, model, effort)` combo with 3-5 rating avg while a cheaper combo exists with similar avg → recommend downgrade
- Skills with no runs in 30 days → recommend pruning (stale)
- `_writeback` triggered > N times for skill X → skill X's SKILL.md needs tighter write-back instructions

Output: a branch `retrospective-<yyyy-mm-dd>` with SKILL.md edits and a PR body explaining each change with the data that motivated it.

### D. Cloudflare Access on the dashboard

Configure from Cloudflare dashboard (not automatable via this repo).
Documented as a runbook step.

---

## File-by-file plan

### New: `scripts/backup.sh`

```bash
#!/usr/bin/env bash
# scripts/backup.sh — nightly backup of Postgres + audit_log + recent logs.
# Runs via launchd com.assistant.backup.plist at 04:00 daily.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="$PROJECT_DIR/volumes/backups"
mkdir -p "$BACKUP_DIR"

STAMP=$(date -u +%Y-%m-%d)
OUT="$BACKUP_DIR/backup-$STAMP.tar.gz"
TMP=$(mktemp -d)

# 1. Postgres dump (plain text, small, grep-friendly)
pg_dump assistant > "$TMP/db.sql"

# 2. Audit log snapshot (last 30 days only; older is already compressed monthly)
find "$PROJECT_DIR/volumes/audit_log" -name '*.jsonl' -mtime -30 \
     -exec cp {} "$TMP/" \;

# 3. Recent logs (last 7 days)
find "$PROJECT_DIR/volumes/logs" -name '*.log' -mtime -7 \
     -exec cp {} "$TMP/" \;

# 4. Config snapshot — NEVER include .env (secrets!)
cp "$PROJECT_DIR/.env.example" "$TMP/env.example"
cp "$PROJECT_DIR/alembic.ini" "$TMP/"

# 5. Tar it up
tar -czf "$OUT" -C "$TMP" .
rm -rf "$TMP"

# 6. Retention: keep last 7 daily backups
ls -t "$BACKUP_DIR"/backup-*.tar.gz 2>/dev/null | tail -n +8 | xargs rm -f 2>/dev/null || true

echo "$(date -u +%FT%TZ) backup $OUT ($(du -h "$OUT" | cut -f1))" \
    >> "$PROJECT_DIR/volumes/logs/backup.log"
```

### New: `~/Library/LaunchAgents/com.assistant.backup.plist`

(Generated by a bootstrap script, or by hand from this template.)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.assistant.backup</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string><PROJECT_DIR>/scripts/backup.sh</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key><integer>4</integer>
    <key>Minute</key><integer>0</integer>
  </dict>
  <key>StandardOutPath</key><string><PROJECT_DIR>/volumes/logs/backup.out.log</string>
  <key>StandardErrorPath</key><string><PROJECT_DIR>/volumes/logs/backup.err.log</string>
</dict>
</plist>
```

### New: `skills/server-upkeep/SKILL.md`

```markdown
---
name: server-upkeep
description: Daily health audit. Rotate logs, VACUUM DB, check cert/disk/project status, DM anomalies only.
model: claude-sonnet-4-6
effort: low
permission_mode: acceptEdits
required_tools: [Read, Bash, Glob, Grep]
max_turns: 20
escalation:
  on_failure:
    model: claude-sonnet-4-6
    effort: medium
tags: [scheduled, operations, internal]
---

# Server upkeep

You are doing a daily audit of the server. Silent-by-default — only DM the
user when something is actually worth their attention.

## Procedure

### 1. Log rotation

```bash
cd volumes/logs
# Rotate anything over 50MB
for log in *.log; do
    size=$(stat -f%z "$log" 2>/dev/null || stat -c%s "$log")
    if [ "$size" -gt 52428800 ]; then
        mv "$log" "${log%.log}-$(date +%F).log"
        touch "$log"
    fi
done
# Compress anything older than 7 days and not already .gz
find . -name "*.log-*" -mtime +7 ! -name "*.gz" -exec gzip {} \;
# Delete anything older than 60 days
find . -name "*.log-*.gz" -mtime +60 -delete
```

### 2. Audit log rotation (audit_log/)

Summary files older than 30 days: keep. JSONL files older than 30 days:
compress and move to `audit_log/archive/YYYY-MM.jsonl.gz`.

### 3. DB maintenance

```bash
psql assistant -c "VACUUM ANALYZE;"
```

Check table sizes; if `jobs` table > 100k rows, note for the user (doesn't
need action yet; phase 6 handles).

### 4. Cert expiry check

Not applicable for Phase 3's `tls internal` Caddy setup (Caddy rotates its
own local CA). But check the Cloudflare tunnel is still healthy:

```bash
cloudflared tunnel info ai-server 2>&1 | head -5
```

### 5. Project health check

```sql
SELECT slug, last_healthy_at, NOW() - last_healthy_at AS stale_for
FROM projects
WHERE last_healthy_at IS NULL OR last_healthy_at < NOW() - INTERVAL '24 hours';
```

### 6. Process restart frequency

```bash
grep "runner starting\|bot starting\|web starting" volumes/logs/*.log | \
    awk '{print $1, $3}' | sort | uniq -c | sort -rn | head -5
```

If any process restarted > 3 times today, that's noteworthy.

### 7. `_writeback` frequency

```sql
SELECT DATE(created_at), COUNT(*) FROM jobs
WHERE kind = '_writeback' AND created_at > NOW() - INTERVAL '7 days'
GROUP BY 1 ORDER BY 1;
```

If > 20 in a day, flag the skill that caused them.

### 8. Disk usage

```bash
df -h $HOME | tail -1
```

### 9. Summarize

Decide: is anything interesting?

- Disk > 80%? Yes.
- Project stale > 24h? Yes.
- Process restarts > 3/day? Yes.
- `_writeback` > 20/day? Yes.
- Cert expiry < 14 days? Yes.
- Anything else? Your judgment.

If YES to any: write a one-paragraph summary of what's concerning.
If NO to all: final text is exactly the string `SILENT`. The gateway suppresses
DM-ing the user when it sees this exact final text.

On Sundays at 10am specifically: always send a one-line "all quiet" summary
(not `SILENT`) so the user knows the job is alive.

## Gotchas

- Don't DELETE anything automatically. Only rotate/compress/report.
- If cert check fails because cloudflared CLI isn't in PATH, shell out to
  its full path at `/usr/local/bin/cloudflared`.
- Keep the DM under 500 characters. The user skims these.
```

### New: `skills/server-patch/SKILL.md`

```markdown
---
name: server-patch
description: Modify server code (src/, scripts/, alembic/). Always PR-gated, never auto-merged.
model: claude-opus-4-7
effort: xhigh
permission_mode: acceptEdits
required_tools: [Read, Write, Edit, Bash, Glob, Grep]
max_turns: 60
post_review:
  trigger: always
  reviewer_model: claude-opus-4-7
  reviewer_effort: high
tags: [server, maintenance, manual-merge-required]
---

# Server patch

You are modifying ai-server itself. This requires extreme care: you are
changing the system that runs you.

## Hard rules

- Never commit directly to `main`. Always branch: `server-patch/<slug>`.
- Always open a PR via `gh pr create`. Never merge it — the human merges.
- Never touch `.env`. Never print secrets to logs.
- If a change would require running migrations, explicitly note this in the
  PR body — the user must run `alembic upgrade head` after merge.
- If a change affects the runner startup (e.g., new required env var), note
  this in the PR body with the exact .env line they need to add.

## Procedure

### 1. Orient

Read CLAUDE.md, `.context/SYSTEM.md`, and the CONTEXT.md for every module
you'll touch.

### 2. Branch

```bash
git checkout -b server-patch/<short-slug>
```

### 3. Patch

Make minimal changes. Keep unrelated refactoring out.

### 4. Test

```bash
pipenv run pytest tests/ -v
```

Every test must pass. If your change breaks a test, either fix the test
(with justification) or fix the code.

### 5. Write/update CHANGELOG

Per PROTOCOL.md, for each module touched:
```
# .context/modules/<module>/CHANGELOG.md
## YYYY-MM-DD — <patch title>
...
```

### 6. Commit

```bash
git add -A
git commit -m "<subject>

<body explaining what and why>

Requires-migration: yes/no
Requires-env-change: <var name or 'no'>
Rollback: git revert <this-sha>"
```

### 7. Push and PR

```bash
git push -u origin server-patch/<short-slug>
gh pr create --fill --title "<subject>" --body-file <(echo "## Summary
<what changed>

## Why
<reason>

## Testing
- pytest: <N passed>
- manual: <what you verified>

## Breaking changes
<none | specific>

## Rollback
git revert <sha> && git push

/cc @Piserchia  <!-- so it shows up in your notifications -->")
```

### 8. Final summary

Report the PR URL, the summary, and any action the user must take post-merge.

## Gotchas

- If you find yourself wanting to make a "quick fix" outside a PR, stop and
  make it a PR anyway. The gate exists for a reason.
- Don't try to merge your own PR even if gh CLI would let you. Exit with
  the PR URL and let the human decide.
- Running `pipenv install` mid-patch will modify Pipfile.lock; include that
  in the commit.
```

### New: `skills/review-and-improve/SKILL.md`

```markdown
---
name: review-and-improve
description: Analyze recent job data, propose tuning changes as a PR.
model: claude-opus-4-7
effort: max
permission_mode: plan
required_tools: [Read, Bash, Glob, Grep]
max_turns: 30
tags: [scheduled, retrospective, internal]
---

# Review and improve

You are a retrospective auditor. Your output is a PR against ai-server
proposing tuning changes. You run in `plan` mode — you cannot modify files
directly; you propose changes in your final summary, and a separate
follow-up job applies them.

## Procedure

### 1. Gather data

```sql
-- Aggregate success rates by (skill, model, effort)
SELECT resolved_skill, resolved_model, resolved_effort,
       status, COUNT(*), AVG(user_rating) AS avg_rating,
       AVG(EXTRACT(EPOCH FROM (completed_at - started_at))) AS avg_seconds
FROM jobs
WHERE created_at > NOW() - INTERVAL '<period>'
  AND resolved_skill IS NOT NULL
GROUP BY 1, 2, 3, 4;

-- `_writeback` triggers per skill (suggests SKILL.md improvements)
SELECT description, COUNT(*)
FROM jobs
WHERE kind = '_writeback' AND created_at > NOW() - INTERVAL '<period>'
GROUP BY 1 ORDER BY 2 DESC LIMIT 20;

-- Escalations per skill (suggests default model upgrade)
SELECT description, COUNT(*)
FROM jobs
WHERE created_by LIKE 'escalation:%' AND created_at > NOW() - INTERVAL '<period>'
GROUP BY 1 ORDER BY 2 DESC;

-- code-review outcomes per skill
SELECT resolved_skill, review_outcome, COUNT(*)
FROM jobs
WHERE review_outcome IS NOT NULL AND created_at > NOW() - INTERVAL '<period>'
GROUP BY 1, 2;
```

### 2. Identify candidate changes

For each signal:

- **High failure rate** (>25%): recommend upgrading default model or effort
- **Low user rating** (<3 avg, >5 ratings): dig into failure modes; may need
  skill body rewrite
- **Frequent escalation that succeeds**: make the escalated model the default
- **Frequent `_writeback` for skill X**: patch skill X's SKILL.md to be
  explicit about write-back steps
- **Frequent `code-review: blocker` on skill X**: review reveals a pattern;
  note it as a GOTCHAS entry for skill X
- **Unused skills (0 jobs in 30 days)**: mark for pruning in next retro

### 3. Propose changes

For each concrete change, write:

```markdown
### Change N: <title>

**Problem**: <what the data shows>
**Proposal**: <specific edit to skills/<name>/SKILL.md>
**Expected effect**: <what should improve>
**Data snapshot**:

| metric | before | target |
|---|---|---|
| ... | ... | ... |
```

### 4. Dispatch

Since you're in plan mode, you can't write files. Instead, use the
`dispatch` MCP tool to enqueue a follow-up `server-patch` job that
implements your proposals:

```
dispatch.enqueue_job(
  kind="server-patch",
  description="Apply review-and-improve proposals from <this job ID>",
  payload={
    "proposals": [<list of proposed changes as structured data>],
    "parent_job_id": "<this job ID>",
  }
)
```

That job will open the actual PR.

### 5. Final summary

- Period analyzed
- Number of jobs reviewed
- Number of proposals made
- PR (will be linked in your follow-up when the server-patch job opens it)

## Gotchas

- Don't propose changes for skills with < 5 runs — not enough data.
- Don't propose the same change twice; check `.context/modules/runner/CHANGELOG.md`
  (or git log for skills/) to see if a prior retro already tried it.
- Skip any proposal that would touch .env, secrets, or auth.
- If no meaningful proposals: final summary is "No changes recommended
  this period. Reviewed N jobs, all within expected parameters."
```

### New: `scripts/seed-schedules.sh`

Idempotent. Inserts the Phase 5 schedules if not present.

```bash
#!/usr/bin/env bash
# scripts/seed-schedules.sh — insert canonical schedules. Safe to re-run.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

upsert() {
    local name="$1" cron="$2" kind="$3" desc="$4"
    psql assistant -v ON_ERROR_STOP=1 <<SQL
INSERT INTO schedules (id, name, cron_expression, job_kind, job_description, paused, next_run_at, created_at)
VALUES (gen_random_uuid(), '$name', '$cron', '$kind', '$desc', false,
        NOW(),  -- will be recalculated to proper next_run on first tick
        NOW())
ON CONFLICT (name) DO UPDATE SET
    cron_expression = EXCLUDED.cron_expression,
    job_kind = EXCLUDED.job_kind,
    job_description = EXCLUDED.job_description;
SQL
}

upsert 'server-upkeep-daily' '0 3 * * *' 'server-upkeep' 'Daily server audit and upkeep'
upsert 'review-and-improve-weekly' '0 0 * * MON' 'review-and-improve' 'Weekly retrospective on recent job data'

echo "Schedules seeded. View with:"
echo "  psql assistant -c \"SELECT name, cron_expression, paused FROM schedules;\""
```

### New: `src/runner/retention.py`

A small helper called from `server-upkeep` for audit log rotation (heavier
logic than you'd want in a SKILL.md's Bash loop):

```python
"""Audit log retention: compress and archive JSONL files older than 30 days."""
from __future__ import annotations

import gzip
import shutil
from datetime import datetime, timedelta
from pathlib import Path


def rotate_audit_logs(audit_dir: Path, archive_after_days: int = 30) -> int:
    """Compress and move old JSONL files to archive/YYYY-MM.jsonl.gz.
    Returns number of files processed."""
    if not audit_dir.exists():
        return 0
    archive_dir = audit_dir / "archive"
    archive_dir.mkdir(exist_ok=True)

    cutoff = datetime.now().timestamp() - archive_after_days * 86400
    processed = 0
    month_bundles: dict[str, list[Path]] = {}

    for jsonl in audit_dir.glob("*.jsonl"):
        if jsonl.stat().st_mtime >= cutoff:
            continue
        mtime = datetime.fromtimestamp(jsonl.stat().st_mtime)
        key = mtime.strftime("%Y-%m")
        month_bundles.setdefault(key, []).append(jsonl)

    for month, files in month_bundles.items():
        bundle = archive_dir / f"{month}.jsonl.gz"
        with gzip.open(bundle, "at") as out:
            for f in files:
                out.write(f.read_text())
                f.unlink()
                processed += 1

    return processed
```

---

## Runbook

### Step 1 — Backup infrastructure

```bash
bash scripts/backup.sh     # manual test run
ls volumes/backups/        # should show today's file
```

Install launchd:
```bash
cat > ~/Library/LaunchAgents/com.assistant.backup.plist <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.assistant.backup</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>$HOME/Library/Application Support/ai-server/scripts/backup.sh</string>
  </array>
  <key>StartCalendarInterval</key><dict>
    <key>Hour</key><integer>4</integer><key>Minute</key><integer>0</integer>
  </dict>
  <key>StandardOutPath</key><string>$HOME/Library/Application Support/ai-server/volumes/logs/backup.out.log</string>
  <key>StandardErrorPath</key><string>$HOME/Library/Application Support/ai-server/volumes/logs/backup.err.log</string>
</dict>
</plist>
PLIST
launchctl load -w ~/Library/LaunchAgents/com.assistant.backup.plist
```

**Checkpoint**: `launchctl list | grep com.assistant.backup` shows the job; wait until 04:00 or `launchctl start com.assistant.backup`; verify `volumes/backups/backup-<date>.tar.gz` exists.

### Step 2 — server-upkeep skill

Write `skills/server-upkeep/SKILL.md`. Commit to ai-server.

Seed the schedule:
```bash
bash scripts/seed-schedules.sh
```

**Checkpoint**: `psql assistant -c "SELECT name, next_run_at FROM schedules WHERE name = 'server-upkeep-daily';"` — shows tomorrow 03:00 UTC.

Manual test:
```bash
# Trigger immediately via enqueue (bypassing the scheduler)
psql assistant -c "INSERT INTO jobs (id, kind, description, status, created_by, created_at)
                   VALUES (gen_random_uuid(), 'server-upkeep', 'manual test',
                           'queued', 'manual-test', NOW());"
# Observe in dashboard + audit log
```

### Step 3 — server-patch skill

Write `skills/server-patch/SKILL.md`. Test on a trivial change (e.g., add a
docstring to a function):

```
/task server: add a docstring to _resolve_cwd in src/runner/session.py
```

**Checkpoint**: a new PR exists on GitHub against ai-server. It does NOT
auto-merge. The PR body has the exact structure specified in the skill.

### Step 4 — review-and-improve skill

Write `skills/review-and-improve/SKILL.md`. Seed its schedule:

```sql
INSERT INTO schedules (name, cron_expression, job_kind, job_description)
VALUES ('review-and-improve-weekly', '0 0 * * MON', 'review-and-improve',
        'Weekly retrospective on recent job data');
```

**Checkpoint**: on next Monday 00:00 UTC, the job runs. Output (via its
dispatched server-patch follow-up) is a PR against ai-server. Alternatively,
manually trigger now by inserting a queued job.

### Step 5 — Cloudflare Access on dashboard

This is NOT automatable via this repo — it's Cloudflare dashboard configuration.

1. Go to https://one.dash.cloudflare.com/ (Cloudflare Zero Trust dashboard)
2. Access → Applications → Add an application
3. Self-hosted
4. Application name: `ai-server dashboard`
5. Application domain: `dashboard.<yourdomain>`
6. Session duration: 24 hours
7. Identity providers: One-time PIN (email)
8. Policies → Add policy:
   - Name: `Chris only`
   - Action: Allow
   - Include: Emails → your email
9. Save

**Checkpoint**: open an incognito window, visit `https://dashboard.<yourdomain>/`. You should be prompted for email → get a code → enter → access dashboard. If you visit from a different email, you should be blocked.

### Step 6 — Scheduled retention tests

Wait one week. Verify:
- 7 backup files in `volumes/backups/` (not 8 — retention works)
- audit_log/archive/YYYY-MM.jsonl.gz exists for files older than 30 days
- logs older than 7 days are compressed in place
- `review-and-improve` has run at least once (weekly cadence)

### Step 7 — Commit and push

```bash
cd "$HOME/Library/Application Support/ai-server"
git add -A
git commit -m "Phase 5: operations (server-upkeep, backup, server-patch, review-and-improve)"
git push origin main
```

---

## Rollback

- Disable a scheduled skill: `UPDATE schedules SET paused = true WHERE name = '<name>';`
- Disable backup: `launchctl unload ~/Library/LaunchAgents/com.assistant.backup.plist`
- Revert Phase 5 commit: `git reset --hard <pre-phase-5-sha>`

---

## NOT in Phase 5

- **Cloud backup destination** (B2/S3/iCloud): optional Phase 6+.
- **Auto-tuning of `MAX_CONCURRENT_JOBS`** based on actual throughput: skip.
  Manual for now.
- **Email alerts** for critical failures: Telegram is the alert channel; if
  Telegram breaks, you'll notice.
- **Grafana / Prometheus**: overkill. Psql queries and the dashboard are
  sufficient.
- **PagerDuty integration**: personal assistant; pager-duty would be comical.

---

## After Phase 5

Phase 6: polish — remaining skills + nice-to-haves. See `docs/PHASE_6_PLAN.md`.
