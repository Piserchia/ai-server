# atlas-trader-evaluate — gotchas

Seeded 2026-08-26 at commissioning. Append mechanical lessons here; never
rewrite old entries.

- 2026-08-26: `atlas-dash` requires DATABASE_URL passed explicitly (no
  .env autoload) and runs from the dashboard venv:
  `set -a; source .env; set +a; dashboard/.venv/bin/atlas-dash ...`
  (pattern from skills/atlas-evaluate/GOTCHAS.md).
