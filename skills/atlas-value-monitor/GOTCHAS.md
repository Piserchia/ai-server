# atlas-value-monitor GOTCHAS

- Alerts fire on STATE CHANGES only; re-running on a quiet day must not
  re-alert (the 21-DTE checkpoint notes itself exactly once).
- The shadow ledger is append-only: never "correct" an event; a bad-looking
  number is a finding for the governor, not something to fix.
- Sandbox data host until the swing funding gate flips settings; marks are
  delayed accordingly — say so if a mark looks stale.
- Payload must carry '{"project_slug":"atlas"}'.
- Monitor may return `status: "provisioning_gap"` (third status alongside
  alerts-empty and crash). SKILL.md's Report section does not list a
  branch for it — until it does, treat provisioning_gap as a ONE-LINE
  quiet report echoing the note and EXIT. Do NOT read production `.env`,
  do NOT diagnose the missing credential, do NOT open a CHANGELOG entry.
  Provisioning is owner action (Atlas CHANGELOG `DR-0002` item 3,
  2026-09-08 — `TRADIER_SANDBOX_TOKEN` is intentionally un-provisioned
  while the earnings feed is dark). Recurrence: `b1f8cf18` (2026-09-09)
  burned all 30 turns on this and hit `error_max_turns`. See
  `docs/TROUBLESHOOTING.md` "provisioning_gap monitor output".
