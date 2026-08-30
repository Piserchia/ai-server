# atlas-advisors-panel — gotchas

Seeded 2026-08-30 at commissioning. Append mechanical lessons here; never
rewrite old entries.

- 2026-08-30: The emissions commit+push MUST land before simulate() runs —
  commit-before-pricing IS the no-look-ahead seal for tier-2 books
  (advisors/CLAUDE.md rule 2). Push rejected → stop and report; never
  price uncommitted weights.
- 2026-08-30: Persona-mind subagents get dossier + market snapshot ONLY.
  Leaking the scoreboard into their context lets the mind fit the judge
  (rule 8) and invalidates the tier-2 evidence stream.
- 2026-08-30: `replace_positions` wholesale-rebuilds derived rows from git
  evidence; a "weird number" is debugged in claims/emissions/bars, never by
  editing advisors.* rows.
- 2026-08-30 (commissioning review): `AdvisorsDB.replace_positions` is one
  psql call per row, NOT one transaction — a mid-rebuild crash can leave a
  book with partial derived rows until the next panel run rebuilds it.
  Self-healing by design; don't "fix" partial rows by hand, re-run the
  rebuild.
- 2026-08-30 (commissioning review): `ensure_book` relies on the migration
  default (100000) matching book_rules.yaml `start_equity`. If a v2 rules
  file ever changes start_equity, the DB write must be made explicit first.
