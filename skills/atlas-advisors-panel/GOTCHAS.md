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
