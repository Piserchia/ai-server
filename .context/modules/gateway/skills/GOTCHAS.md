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

## 2026-10-21 — `parse_flags` raises on an unknown `--model`; handlers must use `_parse_flags_or_reply`

**Symptom**: a new command handler that calls `parse_flags(raw)` directly and
is wrapped in `_error_safe` will, on `/cmd --model=typo …`, reply "Retrying…
(ModelFlagRefused)", retry, then dispatch a self-diagnose job — because since
T7 `parse_flags` resolves `--model` through the models registry and raises
`ModelFlagRefused` instead of passing an unknown id through.

**Fix**: handlers call `parsed = await _parse_flags_or_reply(update, raw)` and
return on `None`. It catches the parse-time refusal AND the
`ROUTER_PROVIDERS_ENABLED` refusal (`resolve_enabled`), replies with the
reason in plain text (never Markdown — the raw value is user input) and
creates nothing. Loud-on-misuse is deliberate: a bare unknown id must never
reach `job.payload` for the session to fail later.

## 2026-04-20 — Telegram Markdown escaping required for all interpolated DB strings

Any string value read from the database (job titles, project names, user input) that is interpolated into a Telegram `parse_mode="MarkdownV2"` message must be escaped with `telegram.helpers.escape_markdown(value, version=2)` before insertion. Unescaped characters like `.`, `-`, `(`, `)`, `!` trigger a `BadRequest: Can't parse entities` error from Telegram's API. This is especially easy to miss when the field looks like plain text in the DB but contains punctuation at runtime.

_Evidence: job `523e25fc`_

## 2026-10-21 — A DM that never arrived is a `notifications` row question first, not a `_job_to_chat` question

**Symptom**: a job finished (or a task card should have been sent) and nothing reached the phone.

**Root cause (since A5/A6, 2026-10-21)**: the runner writes a `notifications` row for every job terminal and task card and the bot's `_outbox_listener` delivers it on the `notify:outbox` nudge or its 30 s poll — a bot restart no longer loses the DM. So the row's `status` tells the story: no row (the runner's insert failed — `notice_queued` absent from the job's audit log), `pending` and ageing (bot down / listener dead), `failed` at `attempts=5` (`last_error`, token-free), `skipped` + `legacy_mode` (switch OFF — the legacy renderer below was responsible), `sent` to the wrong `target`. Checklist with the queries: `docs/TROUBLESHOOTING.md` "no completion/failure DM".

**Still true only with `NOTIFY_OUTBOX=0`**: the legacy `jobs:done` renderer keys on the in-process `_job_to_chat` map (next entry), so a restart between submit and finish loses the DM there — `/status <prefix>` is the workaround, and the ops kinds (`ops_alert`, `quota_*`, `schedule_deferred`, …) are still delivered by the listener in that mode.

**Out-of-band alerts never pass through the bot**: `healthcheck-all.sh` / `schedule-monitor.sh` call `python -m src.notify send` (direct HTTP + a `sent`/`failed` row) and fall back to raw curl; a `WARN … alerts fall back to curl` line in their log means the DM may have arrived with no history row.

## 2026-04-20 — Telegram done-listener mapping lost on bot restart (legacy renderer only since 2026-10-21)

**Symptom**: Job completes but user never receives the Telegram DM with results.

**Root cause**: The `_job_to_chat` mapping is in-process memory. If the bot restarts between job submission and completion, the mapping is lost and the done-listener can't find the chat to DM.

**Workaround**: User checks via `/status <prefix>` or the web dashboard. Resolved for the default path by the notifications outbox (entry above); applies only while `NOTIFY_OUTBOX=0`.

## 2026-04-20 — Dashboard 404 for ambiguous UUID prefix

**Symptom**: `/api/jobs/<id>` returns 404 even though the job exists.

**Root cause**: `find_job_by_prefix()` in `gateway/jobs.py` requires a *unique* prefix. If two jobs share the first 8 hex chars (rare but possible), it returns None.

**Fix**: Use a longer prefix (10+ chars) or the full UUID.
