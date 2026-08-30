# atlas-value-monitor GOTCHAS

- Alerts fire on STATE CHANGES only; re-running on a quiet day must not
  re-alert (the 21-DTE checkpoint notes itself exactly once).
- The shadow ledger is append-only: never "correct" an event; a bad-looking
  number is a finding for the governor, not something to fix.
- Sandbox data host until the swing funding gate flips settings; marks are
  delayed accordingly — say so if a mark looks stale.
- Payload must carry '{"project_slug":"atlas"}'.
