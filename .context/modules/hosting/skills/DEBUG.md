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

## 2026-04-20 — Runner keeps restarting (launchd throttling)

Check `launchctl list | grep com.assistant` for non-zero exit status, then `tail -100 volumes/logs/runner.err.log`.

**Common causes** (check in order):
1. Postgres/Redis not running → `brew services start postgresql@15 redis`
2. Migration not applied → `pipenv run alembic upgrade head`
3. Python imports failing → `pipenv install`
4. `ANTHROPIC_API_KEY` set → remove from shell rc files
5. `claude` CLI missing → `curl -fsSL https://claude.ai/install.sh | bash`

If launchd backs off, uninstall+reinstall after fixing: `bash scripts/install-launchd.sh uninstall` then `bash scripts/install-launchd.sh`.

## 2026-04-20 — cloudflared has no active connections

```bash
cloudflared tunnel info ai-server
tail -20 /Library/Logs/com.cloudflare.cloudflared.err.log
```

**Checklist**: (1) Config at `/etc/cloudflared/`? (2) Credentials JSON there too? (3) Plist has `tunnel run` args? (4) Service started with `sudo launchctl bootstrap system`?
