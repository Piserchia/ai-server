# atlas-trader-paper — gotchas

Seeded 2026-08-26 at commissioning. Append mechanical lessons here (any
loop may append — LOOP.md §7 exemption); never rewrite old entries.

- 2026-08-26: The executor's "halted"/"breaker_tripped" statuses are
  DESIGNED outcomes that exit 0 — supervise, report, do not retry the run
  or clear halts. Halt clearing is reconciliation-success or owner action,
  never this skill.
