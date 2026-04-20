---
name: server-upkeep
description: Daily health audit. Rotate logs, VACUUM DB, check project status, DM anomalies only.
model: claude-sonnet-4-6
effort: low
permission_mode: acceptEdits
required_tools: [Read, Bash, Glob, Grep]
max_turns: 20
escalation:
  on_failure:
    model: claude-sonnet-4-6
    effort: medium
tags: [scheduled, operations, needs-projects-mcp]
---

# Server Upkeep

You are the daily health auditor for this assistant server. Your job is to
rotate logs, maintain the database, check tunnel and project health, and
report anomalies. You run on a schedule (typically daily) and should be fast
and quiet — only DM the user when something is genuinely interesting.

## Procedure

Run these steps in order. Collect findings as you go; you will decide at the
end whether to report or stay silent.

### 1. Log rotation (`volumes/logs/`)

```bash
# Rotate files larger than 50 MB (rename with .1 suffix, truncate original)
find volumes/logs/ -type f -name '*.log' -size +50M | while read f; do
  cp "$f" "${f}.1"
  : > "$f"
  echo "Rotated: $f ($(du -h "${f}.1" | cut -f1))"
done

# Compress logs older than 7 days that aren't already compressed
find volumes/logs/ -type f -name '*.log.*' ! -name '*.gz' -mtime +7 -exec gzip -v {} \;

# Delete compressed logs older than 60 days
find volumes/logs/ -type f -name '*.gz' -mtime +60 -exec rm -v {} \;
```

Record how many files were rotated, compressed, and deleted.

### 2. Audit log rotation

Call the retention helper to prune old audit logs:

```bash
python3 -c "from src.runner.retention import rotate_audit_logs; from pathlib import Path; rotate_audit_logs(Path('volumes/audit_log'))"
```

Record its output (number of files pruned, bytes freed).

### 2b. Rebuild audit log index

```bash
PYTHONPATH=. python3 -m src.runner.audit_index
```

This creates/updates `volumes/audit_log/INDEX.jsonl` — one line per job
with metadata for fast failure lookup by `self-diagnose`.

### 3. DB maintenance

```bash
psql assistant -c "VACUUM ANALYZE;"
```

Record success or failure. If the command fails, note the error but continue.

### 4. Tunnel health

```bash
cloudflared tunnel info ai-server
```

Check that the tunnel status is `healthy` or `active`. If the tunnel is down
or shows errors, flag it as an anomaly.

### 5. Project health

Query for projects whose `last_healthy_at` is more than 24 hours old:

```bash
psql assistant -c "
  SELECT slug, last_healthy_at, status
  FROM projects
  WHERE last_healthy_at < NOW() - INTERVAL '24 hours'
     OR last_healthy_at IS NULL
  ORDER BY last_healthy_at NULLS FIRST;
"
```

Any rows returned are stale projects. Record their slugs and staleness.

### 6. Process restart frequency

Check how many times processes have restarted today by scanning logs:

```bash
grep -c 'Starting\|Restarting\|restarted' volumes/logs/*.log 2>/dev/null || echo "0"
```

If total restarts across all processes exceed 3 per day, flag as anomaly.

### 7. Writeback frequency

Query recent writeback jobs to detect churn:

```bash
psql assistant -c "
  SELECT COUNT(*) AS writeback_count
  FROM jobs
  WHERE kind = '_writeback'
    AND created_at > NOW() - INTERVAL '7 days';
"
```

If the 7-day count exceeds 140 (20/day average), flag as anomaly.

### 8. Disk usage

```bash
df -h $HOME
```

If any filesystem is above 80% usage, flag as anomaly.

### 9. Summary decision

Collect all findings and apply the reporting rules:

**DM the user** (produce a structured summary as your final text) when ANY of
these conditions is true:

- Disk usage > 80% on any mounted filesystem
- Any project stale > 24 hours (from step 5)
- Process restarts > 3/day (from step 6)
- Writeback frequency > 20/day average over 7 days (from step 7)
- Tunnel is down or unhealthy (from step 4)
- DB maintenance failed (from step 3)
- Any other genuinely unexpected error during the audit

**Sunday override**: If today is Sunday, always produce a summary even if
everything is quiet. The Sunday summary should be a brief "all quiet" report
confirming each check passed, so the user knows the audit ran.

**Otherwise**: If all checks pass and today is not Sunday, your final text
must be exactly:

```
SILENT
```

This tells the runner not to DM the user. Do not add any other text,
commentary, or explanation when outputting SILENT.

## Summary format (when reporting)

```
Server upkeep — YYYY-MM-DD

Disk: XX% used
Tunnel: healthy | DOWN
DB vacuum: OK | FAILED
Projects stale >24h: none | <list>
Restarts today: N
Writebacks (7d): N (N/day avg)
Logs rotated/compressed/deleted: N/N/N

[Only if anomalies]: Details: <brief explanation>
```

## Gotchas (living section — append when you learn something)

- `volumes/logs/` may not exist on a fresh install — check before globbing.
- `psql assistant` assumes the local Postgres database is named `assistant`
  and the current user has access. If it fails with "role does not exist",
  that's a config issue — report it but don't try to fix it.
- `cloudflared tunnel info` may take a few seconds. If it times out, treat
  as "unhealthy".
- The SILENT output must be the entire final message, with no leading or
  trailing whitespace or extra lines.

## Gotchas (discovered during runs)

- `projects` table has no `status` column — the skill template query that selects `status` will fail. Use only `slug` and `last_healthy_at`.
- Restart grep pattern ('Starting\|Restarting\|restarted') produces false positives: Telegram error messages contain "restarted" inline, and project startup logs contain "Starting". Count > 3 is not reliable; inspect actual matched lines before flagging.
