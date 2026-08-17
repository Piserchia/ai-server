# Charter — Atlas division

**Manager:** `atlas-manager`
**Charter (goal):** run the atlas product (private financials/trading dashboard +
agent platform) — its reports, scouting, briefs, portfolio interaction, and
deploys. Atlas is a product sub-org with its own dev-repo topology
(`~/Documents/repos/atlas`).

## Roster

| Agent | Role | Privilege | Purpose |
|---|---|---|---|
| `atlas-manager` | manager | read-only | Weekly atlas review: product/quality/ops gaps → proposals (Thu 06:00) |
| `atlas-report` | worker | content | Single expert report |
| `atlas-report-sweep` | worker | content | Weekly full report pass |
| `atlas-scout` | worker | content | Prediction-market / opportunity scan |
| `atlas-daily-brief` | worker | content | Daily portfolio brief |
| `atlas-portfolio` | worker | content | Portfolio interaction / Q&A |
| `atlas-chat` | worker | content | Atlas conversational interface |
| `atlas-redeploy` | worker | prod-operator | Deploy atlas (bespoke pipeline; `project-redeploy` generalizes it) |
| `atlas-evaluate` | worker | content | Weekly loop governor: scorecard + data_gaps triage + build grading + built→live promotion + backlog re-route (Mon 11:00) |
| `atlas-build` | worker | guarded-writer | Twice-weekly loop builder: top eligible S/M item → workspace-isolated build → gates + code-review LGTM → push → deploy dispatch (Tue+Fri 10:00) |
| `atlas-gap-scout` | worker | content | Weekly top-gap free-source spec + live probe + builder-acceptance row (Wed 11:00) |
| `atlas-refresh-knowledge` | worker | content | Monthly knowledge curation + stale-claim re-verify (1st 11:30) |
| `atlas-momo-research` | worker | guarded-writer | Weekly Momentum-Lab research cycle: one governed hypothesis cycle in a workspace clone under momentum/evaluation/PROTOCOL.md; mechanics/IEX-observe until SIP approved (Thu 13:00) |
| `atlas-momo-drift` | worker | guarded-writer | Monthly Momentum-Lab retention-drift point (E-0028): anchored probe in a workspace clone, one dated JSON committed, data-only; monitoring not experiment (1st 13:30) |

## Standards

- Single-writer: commits are born in the atlas dev repo (or the builder's
  per-job workspace clone, which pushes to the same GitHub master), deployed
  via `atlas-redeploy`; the runtime clone is pull-only (incident 2026-07-09).
- The closed improvement loop's binding contracts live in the atlas repo:
  `evaluation/LOOP.md` (state machine, single-writer-per-artifact, recovery
  matrix, human ceilings). Owner decision 2026-08-04: S/M builds + deploys
  are autonomous through the gated chain; `[system]`, paid sources,
  event-map pairs, auth/infra, destructive migrations, new deps stay human.
- **Open item (owner):** the atlas manifest lists `ANTHROPIC_API_KEY` in
  `env_required`; the server's rule is "never require an API key." Make atlas's
  key boundary explicit / remove the requirement (EVALUATION X2).
- `atlas-redeploy` should migrate onto the generic `project-redeploy` contract
  once atlas's manifest carries a `delivery` block.

## Cadence

Weekly (atlas review). Plus scheduled reports (daily brief 12:00, sweep Sun 18:00).

## Feedback / reports

Reads division-scoped job outcomes + `projects/atlas` docs; writes `REPORT.md`.
