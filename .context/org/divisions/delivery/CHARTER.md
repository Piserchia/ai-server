# Charter — Delivery division

**Manager:** `delivery-manager`
**Charter (goal):** turn a natural-language ask into a live, documented, deployed
project, and keep hosted projects healthy across their lifecycle
(create → host → deploy → verify → update → retire). MISSION objectives C/D:
"`/task new project: …` → live public project in <10 min, no further input."

## Roster

| Agent | Role | Privilege | Purpose |
|---|---|---|---|
| `delivery-manager` | manager | read-only | Weekly delivery review: lifecycle gaps → proposals (Tue 06:00) |
| `new-project` | worker | prod-operator | Scaffold → host → register a new project (dev-repo topology) |
| `app-patch` | worker | guarded-writer | Modify an existing project (workspace clone + guards) |
| `project-evaluate` | worker | guarded-writer | Read a project, produce manifest + standard CONTEXT.md |
| `project-redeploy` | worker | prod-operator | Contract-driven deploy of any project (gates, restart) |
| `project-update-poll` | worker | prod-operator | Run a project's `on_update` command (scheduled, cheap) |
| `code-review` | worker | read-only | Review diffs for correctness/security/style (QA) |
| `_evaluate` | worker | read-only | Acceptance QA: verify work against criteria → pass/fail |

## Standards

- Dev-repo topology is the default; the runtime clone is pull-only (guards deny
  writes). Consumers stay coherent with it (EVALUATION Batch 3).
- **Registration is owned by `new-project`** — both at creation (scaffold→host
  runs `register-project.sh`) and as drift-repair: "register existing project
  <slug>" dispatches `new-project` in register-only mode (validate manifest →
  register → verify healthcheck). The reconciler routes registration drift here.
- "and deploy" is a real subtask (`project-redeploy`), not implied.
- Every project carries a valid `delivery` contract (lint-enforced).
- "Done" means evidence-checked by `_evaluate`, not claimed.

## Cadence

Weekly (delivery review). Event: repeated `app-patch`/`project-redeploy` failures.

## Feedback / reports

Reads division-scoped job outcomes + `.context/PROJECTS_REGISTRY.md`; writes `REPORT.md`.
