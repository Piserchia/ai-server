# Self-Managing Agent Hierarchy — Design + Rollout (2026-07-28)

> **STATUS: P1–P3 SHIPPED** (P1 foundation + gap-auditor 2026-07-28; P2
> remaining managers + P3 first connector 2026-07-30). Open rollout phases:
> privilege guardrails (P4) and management surfaces (P5).

**Goal (owner, 2026-07-28):** build a *hierarchy of manager agents* so the
system manages itself. A top-level CEO agent dictates what the system should be
as a whole (anchored to MISSION.md); specialized department managers manage
their divisions via **evaluation, enforcement, and refactoring**, each
continuously asking *"given my department's goal, what needs enhancing across
documentation, tools, skills, and agents?"* Departments own agents specific to
them; cross-department connectors move information where it needs to flow.

## The core principle — managers propose, workers execute

The hierarchy is self-**directing**, not self-modifying-with-full-power. This is
already MISSION's stance ("Not a continuous silent self-improver — batched,
proposed, reviewed"). So:

- **Every manager agent is `privilege_class: read-only`** (`permission_mode:
  plan`). It reads, evaluates, and files **proposals** — it never edits code,
  deploys, or restarts.
- Proposals are executed by the existing, already-gated worker skills
  (`server-patch` with `code-review` LGTM + human merge per INV-4; `new-skill`;
  `app-patch`; etc.). The gates don't move; the *direction* becomes hierarchical
  and continuous instead of a single monthly `review-and-improve`.

This keeps a self-managing loop from becoming a self-escalating one.

## The org (divisions, managers, rosters)

Every skill belongs to exactly ONE division, declared in that division's
`CHARTER.md` (lint-enforced). Divisions:

| Division | Manager (CEO/mgr) | Worker agents | Owns |
|---|---|---|---|
| **Executive** | `system-manager` (CEO) | `new-skill`, `review-and-improve`, `_writeback`, `_learning_apply`; dispatch/UX: `chat`, `plan` | MISSION alignment, the org itself, cross-division arbitration, platform evolution, institutional-memory integrity |
| **Delivery** | `delivery-manager` | `new-project`, `app-patch`, `project-evaluate`, `project-redeploy`, `project-update-poll`, `code-review`, `_evaluate` | Project lifecycle: create → host → deploy → verify → update → retire |
| **Platform Ops** | `ops-manager` | `server-patch`, `server-deploy`, `server-upkeep`, `restore`, `self-diagnose` | Server health, deploy safety, DR, incident response |
| **Knowledge** | `knowledge-manager` | `research-report`, `research-deep`, `idea-generation` | Research, ideation, compounding content |
| **Atlas** | `atlas-manager` | `atlas-report`, `atlas-report-sweep`, `atlas-scout`, `atlas-daily-brief`, `atlas-portfolio`, `atlas-chat`, `atlas-redeploy` | The atlas product sub-org |
| (Break-glass) | — | `god` | Owner-at-terminal; outside the hierarchy by design |

## Privilege classes (SoD — Q2: define now, guardrails next)

Each agent is one class; the intended guardrail is documented now, enforced as a
scoped follow-up (do NOT bolt hooks onto live ops skills mid-stream):

| Class | Agents | Intended guardrail (follow-up) |
|---|---|---|
| `read-only` | all managers + CEO, `chat`, `plan`, `code-review`, `_evaluate` | `permission_mode: plan`; propose-only |
| `content` | `research-*`, `idea-generation`, `atlas-report/scout/brief/report-sweep` | write-scope guard: writes confined to the division's content repo |
| `guarded-writer` | `app-patch`, `server-patch`, `project-evaluate`, `_writeback`, `_learning_apply` | workspace clone + PreToolUse guard hooks (already enforced) |
| `prod-operator` | `server-deploy`, `server-upkeep`, `restore`, `project-redeploy`, `atlas-redeploy`, `project-update-poll`, `self-diagnose`, `new-project` | **the gap** — currently bypassPermissions + no guards. Follow-up: an allowlist guard (permit only declared `launchctl`/`git`/build/`psql` verbs against declared targets) |
| `break-glass` | `god` | none by design (INV-18) |

## How a department manager runs (the repeatable pattern)

A manager skill, scheduled (weekly) + event-triggered (repeated division
failures), does:

1. **Load the charter** — its division's goal, roster, standards.
2. **Evaluate** — division-scoped rollups: recent jobs where `resolved_skill ∈
   roster` (outcomes, `review_outcome`, `eval_pass/fail`, `user_rating`,
   failures, escalations) via `runner.retrospective`; read its division's docs +
   skills; check its standards.
3. **Diagnose** — the recurring question across four axes: **documentation**
   (stale/missing?), **tools** (a capability gap?), **skills** (a role missing,
   or one underperforming?), **agents** (does the division need a new agent, or
   is one miscast?).
4. **Act by proposing** — file `Proposal` rows (via the dispatch MCP / the
   proposals table) tagged with the division; big changes become `server-patch`
   / `new-skill` / `app-patch` follow-up jobs (all gated).
5. **Report up** — write `.context/org/divisions/<div>/REPORT.md` (dated,
   overwrite-latest) the CEO consumes.

The CEO runs monthly: reads MISSION + all charters + all latest REPORTs, finds
cross-division gaps + misalignments, files org-level proposals, and updates
charters (via `server-patch`, gated).

## Substrate mapping (this is organization of what exists, not a new engine)

- Manager = a `SKILL.md` (`role: manager`/`ceo`, `division`, `privilege_class:
  read-only`).
- Cadence = `schedules` rows (cron → enqueue), like `server-upkeep` already.
- Evaluation data = jobs/tasks DB + `runner.retrospective` (division-scoped) +
  audit logs + the division's docs.
- Enforcement = `lint_docs` (structural) + the manager's semantic review →
  proposals.
- Refactoring = the existing `proposals` → `server-patch`/`new-skill` gated flow.
- Reporting = `.context/org/` docs (charters + reports).

## Rollout phases

- **P1 (this pass): foundation.** This doc; `.context/org/ORG.md` (operating
  model + chart); all five `divisions/<div>/CHARTER.md` (goal, roster, standards,
  privilege, cadence, feedback); `lint_docs.check_org_charters` (every skill in
  exactly one charter; charters well-formed); the **`system-manager` (CEO)** +
  **`ops-manager`** skills as the proven pattern; `role`/`division`/
  `privilege_class` fields in `SkillConfig`.
- **P2 (SHIPPED 2026-07-30): complete the managers.** `delivery-manager`,
  `knowledge-manager`, `atlas-manager` (replicate the ops-manager pattern) +
  weekly schedules staggered Tue/Wed/Thu 06:00.
- **P3 (first connector SHIPPED 2026-07-30): connectors.** `delivery→ops`
  handoff built as `delivery-ops-reconciler` (weekly Fri 06:00: reconciles
  shipped-vs-operated — registration, healthcheck coverage, supervision,
  backup/DR — and routes drift as proposals; mechanism documented in ORG.md
  § Connectors). The `insight-router` (Knowledge/Atlas findings → other
  divisions) remains planned — lower priority.
- **P4: privilege guardrails.** Implement the `prod-operator` allowlist guard;
  the `content` write-scope guard. Fix atlas `ANTHROPIC_API_KEY` boundary.
- **P5: management surfaces.** `/proposals` view; a division-scoped
  quality/rating rollup on the dashboard so the feedback loops are visible.

## NOT in scope

- No physical reorg of skills into subdirs, no split of the runner by division
  (a risky refactor of a just-stabilized live system).
- Managers never gain execute privilege — the propose→gate→execute path is the
  safety contract.
