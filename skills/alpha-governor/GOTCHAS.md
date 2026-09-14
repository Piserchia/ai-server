# alpha-governor gotchas

- (2026-09-14, design) Workspace-isolated ON PURPOSE, unlike the weekly
  vertical governors (atlas-trader-evaluate et al. run in the shared
  dev clone): this governor writes only ledger AUDIT appends and
  dispatches, and the clone posture avoids adding it to
  UNISOLATED_WRITER_ALLOWLIST in scripts/lint_docs.py (protected path).
  Do not "normalize" it to the shared-clone posture.
- (2026-09-14, design) jobs.payload is queried with `->>` — if the
  column were ever migrated from JSON, revisit the liveness queries.
