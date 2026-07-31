# Charter — Executive division

**Manager:** `system-manager` (CEO)
**Charter (goal):** the whole system serves MISSION.md. Keep every division
aligned to it, own the org structure itself, and evolve the platform's
capabilities. When divisions conflict or a gap spans them, the CEO decides.

## Roster

| Agent | Role | Privilege | Purpose |
|---|---|---|---|
| `system-manager` | ceo | read-only | Monthly org review: reconcile division reports + MISSION → org proposals + charter updates |
| `gap-auditor` | auditor | read-only | Finds what's MISSING — capability gaps within a division (as a manager's subagent) and unowned domains/seams org-wide (for the CEO). The recurring version of the manual system evaluation. Finds + routes; never builds |
| `delivery-ops-reconciler` | connector | read-only | Weekly Delivery→Ops seam reconciler: shipped-vs-operated drift (registration, healthcheck, supervision, DR) → routed proposals (Fri 06:00). Connectors close seams no single division owns — Executive claims them |
| `insight-router` | connector | read-only | Weekly Knowledge/Atlas→everyone router: extracts insights actionable outside their origin division (ideas → Delivery, tooling findings → Ops, product signals → Atlas) → routed digest with evidence + gated skill per item (Sat 06:00) |
| `review-and-improve` | worker | read-only | Retrospective analytics over job outcomes (the CEO's data arm — TUNES what exists; complements gap-auditor which finds what's absent) |
| `new-skill` | worker | guarded-writer | Author new agents proposed by any division |
| `_writeback` | worker | guarded-writer | Institutional-memory integrity: CHANGELOG follow-ups |
| `_learning_apply` | worker | guarded-writer | Institutional memory: append extracted learnings |
| `chat` | worker | read-only | Intake: one-shot conversation |
| `plan` | worker | read-only | Intake: decompose complex asks into a subtask DAG |
| `god` | break-glass | break-glass | Owner-at-terminal; outside the hierarchy by design (INV-18) |

## Standards

- MISSION.md is the north star; a division charter that stops serving an
  objective is a finding.
- The org may only self-**direct** (propose), never self-modify with full power.
- Every division has a manager, a charter, and a cadence.

## Cadence

Monthly (CEO org review). Event: a division REPORT flags a cross-division issue.

## Feedback / reports

CEO reads `../*/REPORT.md`; writes `REPORT.md` here (state-of-the-org + directives).
