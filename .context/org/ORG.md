# ORG.md — the management hierarchy

> The org chart for the agent workforce. A manager (human or CEO agent) reads
> this to understand who does what, who oversees whom, what talks to what, and
> where feedback flows. Design + rationale: `docs/superpowers/plans/
> 2026-07-28-management-hierarchy.md`. Source of truth for division membership is
> each division's `CHARTER.md` (lint-enforced: every skill in exactly one).

## Operating model

The system is an organization that manages itself by **directing**, not by
self-modifying with full power (MISSION: "batched, proposed, reviewed").

- **CEO agent** (`system-manager`, division: executive) — charter is MISSION.md.
  Monthly: reads every division charter + latest report, finds cross-division
  gaps/misalignments, arbitrates, files org-level proposals, and owns the org
  structure (charter new divisions/managers/agents). Read-only; proposes only.
- **Department managers** (one per division) — weekly + event-triggered. Each
  asks *"given my department's goal, what needs enhancing across docs, tools,
  skills, agents?"* and answers by **evaluating** (division-scoped job outcomes +
  its docs/skills), **enforcing** (drift vs its standards), and **refactoring**
  (filing proposals). Read-only; proposes only.
- **Worker agents** — the skills that do the actual work, each owned by one
  division's charter.
- **Auditor** — `gap-auditor` (Executive), read-only, finds what's MISSING:
  capability gaps within a division (as a manager's subagent) and unowned
  domains/seams org-wide (for the CEO). The complement to a manager (which
  improves what it owns) and to `review-and-improve` (which tunes what exists) —
  the auditor finds what *no one* owns. Independent of the managers it audits.
- **Connectors** (P3) — agents that move information across divisions.
- **Proposals → gated execution** — every manager change goes through the
  existing gates: `server-patch` (code-review LGTM + human merge, INV-4),
  `new-skill`, `app-patch`. Managers never execute directly.

## Division index

| Division | Manager | Charter | Cadence |
|---|---|---|---|
| Executive | `system-manager` (CEO) | [executive](divisions/executive/CHARTER.md) | monthly |
| Delivery | `delivery-manager` | [delivery](divisions/delivery/CHARTER.md) | weekly |
| Platform Ops | `ops-manager` | [platform-ops](divisions/platform-ops/CHARTER.md) | weekly |
| Knowledge | `knowledge-manager` | [knowledge](divisions/knowledge/CHARTER.md) | weekly |
| Atlas | `atlas-manager` | [atlas](divisions/atlas/CHARTER.md) | weekly |

`god` is intentionally outside the hierarchy (break-glass, INV-18).

## Feedback flow (who learns what)

```
worker jobs → audit logs + review_outcome/eval_pass/user_rating (per-job quality)
            → runner.retrospective (division-scoped rollups)
            → DEPARTMENT MANAGER (weekly evaluate → diagnose → propose → REPORT.md)
            → CEO (monthly: reconcile REPORTs + MISSION → org proposals + charter updates)
            → proposals → server-patch/new-skill/app-patch (gated execution)
            → back into workers (better skills/docs/tools)
```

Per-job feedback loops already in place feed this: `code-review` (code quality),
`_evaluate` (acceptance), the learning extractor → `_learning_apply`
(institutional memory), the escalation chain (fail → higher model →
self-diagnose).

## Privilege classes (segregation of duties)

`read-only` · `content` · `guarded-writer` · `prod-operator` · `break-glass` —
defined with intended guardrails in the design doc. Each charter tags its agents.
Managers are always `read-only`.

## How to extend the org

A division needs a new capability → its manager files a proposal → `new-skill`
authors the agent → the division CHARTER adds it to its roster (same PR) → lint
confirms it's claimed. The CEO charters a whole new *division* the same way.
