---
name: atlas-value-monitor
description: Daily value-advisor lifecycle sweep — run python3 -m value.monitor over OPEN theses (invalidations, 50% profit targets, 21-DTE checkpoints, expiry/assignment booking, shadow-curve upsert) and alert the owner ONLY on state changes. Quiet days report quiet in one line. Dispatch for the atlas-value-monitor schedule.
model: claude-sonnet-4-6
effort: medium
permission_mode: bypassPermissions
required_tools: [Read, Bash, Glob, Grep]
max_turns: 20
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

## Procedure

1. Workspace clone, rebase, bootstrap value venv (as in atlas-value-theses,
   incl. sitecustomize script).
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
- Crash → fail the job with the traceback.

## Gotchas

Pre-loaded from `skills/atlas-value-monitor/GOTCHAS.md` — the load-bearing
ones: alerts fire on STATE CHANGES only (21-DTE notes itself exactly once);
zero open theses is a normal day and still upserts the shadow-curve point;
the shadow ledger is append-only (a bad number is a governor finding, not a
fix); single cron row — there is no DST sibling for this skill;
'{"project_slug":"atlas"}' payload is mandatory.
