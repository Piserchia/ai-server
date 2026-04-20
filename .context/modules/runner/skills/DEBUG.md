# Debug shortcuts

> **What this file is for**: Fast paths for diagnosing failures in this module.
>
> **When to add an entry here**: When a session debugged a failure and found a useful diagnostic command, a log location that was non-obvious, or an error message whose real meaning differs from its text.
>
> Append entries newest-first. Each entry should include a date header,
> the symptom or pattern, the fix or approach, and (when possible) a
> reference to the audit log that led to the finding.
>
> This file is seeded empty. Claude sessions working in this module should
> append here when they learn something reusable (see `.context/PROTOCOL.md`).

<!-- Append entries below this marker. Do not delete the marker. -->
<!-- APPEND_ENTRIES_BELOW -->

## 2026-04-20 — Quick triage: 8-step failure lookup order

When something breaks, check these sources in order:

1. `volumes/audit_log/<job_id>.jsonl` — ground truth of what the agent did
2. `volumes/audit_log/<job_id>.summary.md` — Claude's own post-hoc summary
3. `volumes/logs/runner.log` — runner-level events around the job
4. `volumes/logs/runner.err.log` — crashes and stack traces
5. `volumes/logs/bot.log` / `volumes/logs/web.log` — the gateway that submitted it
6. `psql assistant` queries on `jobs` table — state at DB level
7. `redis-cli keys "quota:*"` — quota pause state
8. `launchctl list | grep com.assistant` — process supervisor state

## 2026-04-20 — Quota false positive detection

**Symptom**: Queue pauses but the reason string isn't actually a quota issue (e.g., network error, bad tool call).

**Diagnostic**:
```bash
redis-cli get quota:paused_until
redis-cli get quota:last_reason
grep "quota exhausted" volumes/logs/runner.log | tail -5
```

**Fix**: Clear via `/resume` in Telegram or `redis-cli del quota:paused_until quota:last_reason`. Then improve `quota.py:detect_quota_error` to exclude the false-positive string, and add a regression test.
