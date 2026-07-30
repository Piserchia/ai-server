# Charter — Knowledge division

**Manager:** `knowledge-manager`
**Charter (goal):** produce research, ideas, and content that compound over time
(MISSION objectives B/E and § L "documentation that compounds"). Keep the content
stores useful, deduplicated, and backed up.

## Roster

| Agent | Role | Privilege | Purpose |
|---|---|---|---|
| `knowledge-manager` | manager | read-only | Weekly knowledge review: content/quality gaps → proposals (Wed 06:00) |
| `research-report` | worker | content | Web research → dated markdown report in `projects/research/` |
| `research-deep` | worker | content | Deep dive: 10–20 sources, 2000–5000 words |
| `idea-generation` | worker | content | Generate + dedup ideas into `projects/ideas/` |

## Standards

- Content agents write ONLY inside their division's content repo (write-scope
  guard — design doc P4).
- Content repos need an off-site remote (EVALUATION X4: `research-deep`/`ideas`
  have none today — a top enhancement target).
- Dedup against history (idea-generation `history.jsonl`); no duplicate reports.

## Cadence

Weekly (knowledge review). Plus the content agents' own research schedules.

## Feedback / reports

Reads division-scoped job outcomes + the content repos; writes `REPORT.md`.
