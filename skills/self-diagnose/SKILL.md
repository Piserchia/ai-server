---
name: self-diagnose
description: Investigate failures and propose or apply fixes based on risk classification
model: claude-opus-4-7
effort: high
permission_mode: acceptEdits
required_tools: [Read, Bash, Glob, Grep]
max_turns: 30
escalation:
  on_failure:
    model: claude-opus-4-7
    effort: xhigh
context_files: ["docs/Troubleshooting.md"]
tags: [meta, recovery, event-triggered, needs-projects-mcp, needs-dispatch-mcp]
---

# Self-Diagnose

You are investigating a failure in the assistant server or one of its hosted projects.
Your goal is to identify the root cause, classify the risk of the fix, and either apply
the fix directly or delegate it to the appropriate skill.

This skill is triggered in two ways:
1. **Manually**: `/task diagnose: <description>` or `/task why did market-tracker crash?`
2. **Automatically**: The event trigger fires when a skill fails 2+ times in 10 minutes
   or a project stays unhealthy for 20+ minutes.

## Inputs

From the job description and/or payload:
- **target**: what to diagnose (a skill name, project slug, job ID, or free-form description)
- `payload.target_kind`: "skill" | "project" | "job" | "general"
- `payload.target_id`: specific identifier (skill name, project slug, or job UUID prefix)
- `payload.recent_failures`: list of recent failure summaries (if event-triggered)

If the target is unclear, infer from the description. Do NOT use `AskUserQuestion` — this
skill often runs unattended (event-triggered). Make your best determination and document
your reasoning.

## Procedure

### 1. Gather evidence

Collect information systematically. Read at least 3 of these sources:

**For project issues:**
- Use `read_project_logs` MCP tool to get the last 100 lines of the project's error log
- Read the project's manifest.yml for port/healthcheck/start_command
- Check healthcheck: `curl -sf http://localhost:<port>/health`
- Read the project's `.context/CONTEXT.md` for architecture context

**For skill/job issues:**
- Check the audit log index first for similar past failures:
  ```bash
  python3 -c "from src.runner.audit_index import search_index; from pathlib import Path; [print(e) for e in search_index(Path('volumes/audit_log/INDEX.jsonl'), status='failed', skill='<skill_name>')]"
  ```
  Or search by keyword: `search_index(path, keyword='<error_keyword>')`
- Read the audit log: `volumes/audit_log/<job_id>.jsonl` (if job ID available)
- Query recent failures: `psql assistant -c "SELECT id, kind, error_message, created_at FROM jobs WHERE status = 'failed' ORDER BY created_at DESC LIMIT 10;"`
- Read `volumes/logs/runner.log` and `volumes/logs/runner.err.log` (last 50 lines)
- Read the skill's SKILL.md if the failure is skill-specific

**For server issues:**
- Read `volumes/logs/runner.err.log`, `volumes/logs/web.err.log`, `volumes/logs/bot.err.log`
- Check process status: `launchctl list | grep com.assistant`
- Check DB connectivity: `psql assistant -c "SELECT 1;"`
- Check Redis: `redis-cli ping`
- Read `docs/Troubleshooting.md` for known failure patterns

### 2. Identify root cause

Be specific. "Something went wrong" is not a root cause. State:
- **What** failed (exact error message or symptom)
- **Where** it failed (file, line, function)
- **Why** it failed (the actual cause, not the symptom)
- **When** it started (first occurrence timestamp)

### 3. Classify risk

Classify the fix into one of these risk tiers:

| Risk | Criteria | Action |
|------|----------|--------|
| **Very low** | Restart service, clear lock file, truncate log, retry job | Auto-apply directly |
| **Low** | Change config value, adjust timeout, fix a typo | Auto-apply + log |
| **Medium (project)** | Patch project code | Delegate to `app-patch` via dispatch MCP |
| **Medium (server)** | Patch server code | Output diagnosis only — `server-patch` (Phase 5) needed |
| **High** | Schema change, auth change, multi-file refactor | Output diagnosis only |

### 4. Act based on risk

**Very low risk — auto-apply:**
- Use `restart_project` MCP tool for service restarts
- Use Bash for clearing locks, truncating logs
- Verify the fix worked (re-check healthcheck, re-run failing command)
- Update the relevant `.context/` docs with what happened

**Low risk — auto-apply + log:**
- Make the change directly
- Verify it worked
- Update `.context/` docs
- Note the change in your summary (so the user sees it in Telegram)

**Medium risk (project code) — delegate to app-patch:**
- Use `enqueue_job` MCP tool to dispatch an `app-patch` job:
  ```
  enqueue_job(
    kind="app-patch",
    description="fix <project>: <specific issue and proposed solution>",
    payload={"project_slug": "<slug>"}
  )
  ```
- `app-patch` will push the fix directly (no PR gate, per user decision)

**Medium risk (server code) — diagnosis only:**
- Output a clear diagnosis with the proposed fix
- Specify exactly which file(s) and line(s) to change
- Note: "This requires a `server-patch` job. That skill ships in Phase 5.
  Manual action needed for now."

**High risk — diagnosis only:**
- Output diagnosis + recommendation
- Do NOT attempt the fix

### 5. Record findings

If you discovered something non-obvious, append to the relevant file:
- Server issues → `docs/Troubleshooting.md` (new symptom section)
- Project issues → `projects/<slug>/.context/skills/GOTCHAS.md` (create if needed)
- Skill issues → `skills/<name>/SKILL.md` Gotchas section (append)

### 6. Summary

Write a structured final message:

```
Root cause: <one sentence>
Risk: <very-low | low | medium | high>
Action taken: <what you did or delegated>
Verified: <yes/no — did the fix work?>
Follow-up: <any remaining work>
```

## Quality gate

- [ ] Root cause is specific (not "something failed")
- [ ] Risk classification is justified
- [ ] Auto-applied fixes were verified (healthcheck, process status, etc.)
- [ ] Delegated fixes have clear descriptions in the dispatched job
- [ ] Findings recorded in appropriate docs
- [ ] No server code was modified directly (medium+ risk delegates)

## Gotchas

- Event-triggered runs have no user in the loop. Don't use `AskUserQuestion`.
- `restart_project` MCP tool uses `launchctl kickstart -k`. It kills the process
  first, so brief downtime is expected.
- Audit log files may not exist for jobs that crashed before the first `audit_log.append`.
  Check `volumes/logs/runner.err.log` for those cases.
- Multi-service projects (like market-tracker) have separate launchd labels per sub-service:
  `com.assistant.project.<slug>-<service-name>`.
- `server-patch` doesn't exist yet (Phase 5). For server code issues, output the diagnosis
  and proposed fix clearly — the user can apply it manually or wait for Phase 5.
