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

## Standards

- Single-writer: commits are born in the atlas dev repo, deployed via
  `atlas-redeploy`; the runtime clone is pull-only (incident 2026-07-09).
- **Open item (owner):** the atlas manifest lists `ANTHROPIC_API_KEY` in
  `env_required`; the server's rule is "never require an API key." Make atlas's
  key boundary explicit / remove the requirement (EVALUATION X2).
- `atlas-redeploy` should migrate onto the generic `project-redeploy` contract
  once atlas's manifest carries a `delivery` block.

## Cadence

Weekly (atlas review). Plus scheduled reports (daily brief 12:00, sweep Sun 18:00).

## Feedback / reports

Reads division-scoped job outcomes + `projects/atlas` docs; writes `REPORT.md`.
