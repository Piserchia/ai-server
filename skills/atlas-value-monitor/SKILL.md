---
name: atlas-value-monitor
description: Daily value-advisor lifecycle sweep — run python3 -m value.monitor over OPEN theses (invalidations, 50% profit targets, 21-DTE checkpoints, expiry/assignment booking, shadow-curve upsert) and alert the owner ONLY on state changes. Quiet days report quiet in one line. Dispatch for the atlas-value-monitor schedule.
model: claude-sonnet-4-6
effort: medium
permission_mode: bypassPermissions
required_tools: [Read, Bash, Glob, Grep]
max_turns: 50
isolation: workspace
role: worker
division: atlas
privilege_class: guarded-writer
context_files: ["skills/atlas-value-monitor/GOTCHAS.md"]
tags: [atlas, value, advisor, scheduled-capable]
---

# atlas-value-monitor — sweep open theses, alert on change only

You run the deterministic monitor and relay its alerts. No orders exist in
this vertical (value/CLAUDE.md rule 1); no repo writes, no fixes.

**This is a NO-WRITE monitor. The server-wide "update CHANGELOG.md for every
module you touched" rule does NOT apply — this skill touches no code and
modifies no repo. Do not `Edit` or `Write` any file (including
`CHANGELOG.md`, `GOTCHAS.md`, `.env`, or anything under `value/` or
`tradingcore/`). If you find yourself reaching for `Edit`, stop: you have
already left the skill's scope.**

## Procedure

1. Workspace clone, rebase, bootstrap:
   `cd value && python3.12 -m venv .venv && .venv/bin/pip install -q -e '.[dev]' -e ../tradingcore`
   then `bash ../scripts/install-venv-sitecustomize.sh`.
2. `cd value && .venv/bin/python -m pytest -q -x` — red → stop, report.
3. `.venv/bin/python -m value.monitor` and read the JSON.

## Report (final message = Telegram summary)

- `alerts` empty → ONE line: "value monitor: N open theses, no state
  changes, shadow index X". Nothing more.
- Otherwise, one line per alert with owner-action framing:
  invalidated → "🔴 SYM thesis invalidated at $P — if you acted on this
  card, the stated plan says exit"; profit_take → "🟢 SYM put reached the
  50% buyback target"; manage_21dte → "🟡 SYM put at 21 DTE — close or
  roll per the card"; assigned → "🟦 SYM shadow-assigned at effective
  basis $B"; expired_otm → "🟢 SYM put expired worthless".

## When value.monitor crashes

Any non-zero exit from step 3 (traceback, `RuntimeError`, missing
credential, HTTP failure, unreadable JSON — anything) is a **terminal
condition for this job**, not a debug entry point. Follow this exactly:

1. **Do NOT diagnose.** In particular, do NOT:
   - `Read` or `grep` `.env` files (workspace, atlas, or otherwise) —
     credentials are not a monitor concern.
   - `Read` or `grep` `tradingcore/*.py` or `value/*.py` searching for env
     var names, RuntimeError origins, or fallback paths.
   - `Read` `pyproject.toml`, sitecustomize scripts, or dependency configs
     to "understand" the crash.
   - Re-run `value.monitor` with different working directories, env vars,
     or flags to try to make it succeed.
2. **Do NOT `Edit` or `Write` anything.** Not `SKILL.md`, not
   `CHANGELOG.md`, not `GOTCHAS.md`, not a `.env`, not a Python file.
   This monitor has no code changes to log — the server "update
   CHANGELOG.md" rule does not apply (see top of file). Reaching for
   `Edit` after a crash is the debug-spiral failure mode; do not do it.
3. **Emit the traceback verbatim** in your final text message, prefixed
   with `value monitor crashed:` and one line naming the apparent cause
   from the traceback (e.g. `TRADIER_SANDBOX_TOKEN missing`,
   `sqlite locked`, `HTTP 502 from Tradier`). Then stop.
4. **Let the job fail.** Missing broker credentials, sandbox outages, and
   environment provisioning gaps are **owner/ops issues** for the
   atlas-value-monitor environment, resolved by the owner (Tradier
   dashboard, `.env` provisioning) or a dedicated fix job. The daily
   lifecycle sweep neither creates credentials nor patches around their
   absence — a failed monitor day is a signal, not a task.

Budget check: this skill runs in ≤ 10 tool calls on the happy path
(bootstrap + pytest + monitor + final message). If you are past turn 15
and still investigating, you are almost certainly in the forbidden
debug-spiral above — stop and report the last traceback you saw.

## Gotchas

Pre-loaded from `skills/atlas-value-monitor/GOTCHAS.md` — the load-bearing
ones: alerts fire on STATE CHANGES only (21-DTE notes itself exactly once);
zero open theses is a normal day and still upserts the shadow-curve point;
the shadow ledger is append-only (a bad number is a governor finding, not a
fix); single cron row — there is no DST sibling for this skill;
'{"project_slug":"atlas"}' payload is mandatory.
