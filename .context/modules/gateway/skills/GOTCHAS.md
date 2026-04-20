# Gotchas

> **What this file is for**: Non-obvious traps, unexpected behaviors, and things that look like they should work but don't.
>
> **When to add an entry here**: When a session hit a trap — something implicit, an ordering requirement, a race condition, an environment-specific behavior — that a future session should know about before making similar changes.
>
> Append entries newest-first. Each entry should include a date header,
> the symptom or pattern, the fix or approach, and (when possible) a
> reference to the audit log that led to the finding.
>
> This file is seeded empty. Claude sessions working in this module should
> append here when they learn something reusable (see `.context/PROTOCOL.md`).

<!-- Append entries below this marker. Do not delete the marker. -->
<!-- APPEND_ENTRIES_BELOW -->

## 2026-04-20 — Telegram Markdown escaping required for all interpolated DB strings

Any string value read from the database (job titles, project names, user input) that is interpolated into a Telegram `parse_mode="MarkdownV2"` message must be escaped with `telegram.helpers.escape_markdown(value, version=2)` before insertion. Unescaped characters like `.`, `-`, `(`, `)`, `!` trigger a `BadRequest: Can't parse entities` error from Telegram's API. This is especially easy to miss when the field looks like plain text in the DB but contains punctuation at runtime.

_Evidence: job `523e25fc`_

## 2026-04-20 — Telegram done-listener mapping lost on bot restart

**Symptom**: Job completes but user never receives the Telegram DM with results.

**Root cause**: The `_job_to_chat` mapping is in-process memory. If the bot restarts between job submission and completion, the mapping is lost and the done-listener can't find the chat to DM.

**Workaround**: User checks via `/status <prefix>` or the web dashboard. A proper fix would persist the mapping in Redis with a TTL.

## 2026-04-20 — Dashboard 404 for ambiguous UUID prefix

**Symptom**: `/api/jobs/<id>` returns 404 even though the job exists.

**Root cause**: `find_job_by_prefix()` in `gateway/jobs.py` requires a *unique* prefix. If two jobs share the first 8 hex chars (rare but possible), it returns None.

**Fix**: Use a longer prefix (10+ chars) or the full UUID.
