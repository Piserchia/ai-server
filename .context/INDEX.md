# Documentation Index

> For any new Claude session: read this file to know what exists and where to look.
> Last updated: 2026-07-27

## Quick navigation

| I need to... | Read these |
|---|---|
| Understand the overall system | `SERVER.md`, `.context/SYSTEM.md` |
| Work on server code (src/) | `.context/modules/<module>/CONTEXT.md`, `.context/PROTOCOL.md` |
| Work on a specific project | `projects/<slug>/CLAUDE.md`, `.context/PROJECT_PROTOCOL.md` |
| Add a new project | `.context/PROJECTS_REGISTRY.md`, `skills/new-project/SKILL.md` |
| Add a new skill | `.context/SKILLS_REGISTRY.md`, `skills/new-skill/SKILL.md` |
| Patch a project | `skills/app-patch/SKILL.md` (reads project's own CLAUDE.md) |
| Patch server code | `skills/server-patch/SKILL.md` (INV-4 lane: autonomous merge on gate-green + code-review LGTM + owner notification; protected paths owner-approved) |
| Debug a failure | `docs/TROUBLESHOOTING.md`, `volumes/audit_log/<job_id>.jsonl` |
| Understand a skill | `skills/<name>/SKILL.md` (frontmatter = config, body = system prompt) |
| Check what's hosted | `.context/PROJECTS_REGISTRY.md` |
| Check what skills exist | `.context/SKILLS_REGISTRY.md` |
| Review system performance | `src/runner/retrospective.py`, `skills/review-and-improve/SKILL.md` |
| Regression-test a skill's behaviour | `evals/README.md`, `evals/run.py`, `evals/cases/<skill>.yml` |
| See evaluation status | `docs/EVALUATION_2026-08-30.md` (**latest** — grokbot audit + 2026-08-31 remediation disposition), `docs/EVALUATION_2026-07-28.md` (historical tracker), `docs/EVALUATION_2026-07-10.md` (runtime audit), `docs/EVALUATION_2026-04-18.md` (architecture) |
| Fix a defect found in the July audit | `docs/superpowers/plans/2026-07-10-eval-remediation.md` (task-by-task plan T1–T17) |
| Segregate project delivery (dev-repo split + deploy contract) | `docs/superpowers/plans/2026-07-27-project-delivery-segregation.md` (Phases A–E) |
| Understand the atlas project | `docs/EVALUATION_2026-07-10-atlas.md`, `projects/atlas/CLAUDE.md` |
| Create a new skill | `skills/TEMPLATE.md` (structure reference), `skills/new-skill/SKILL.md` |
| Read module institutional knowledge | `.context/modules/<x>/skills/GOTCHAS.md`, `DEBUG.md`, `PATTERNS.md` |
| Understand hosting setup | `.context/modules/hosting/CONTEXT.md`, `Caddyfile` |
| Understand external monitoring | `ops/heartbeat-worker/README.md`, `.context/modules/hosting/CONTEXT.md` (External monitoring) |

## Documentation hierarchy

```
CLAUDE.md                           ← Root session directive (auto-loaded)
SERVER.md                           ← Architecture overview for humans
.context/
  INDEX.md                          ← This file (navigation map)
  SYSTEM.md                         ← Module graph, conventions, invariants
  PROTOCOL.md                       ← Write-back protocol (server-scoped, mandatory)
  PROJECT_PROTOCOL.md               ← Write-back protocol (project-scoped)
  PROJECTS_REGISTRY.md              ← Index of hosted projects
  SKILLS_REGISTRY.md                ← Index of installed skills
  modules/
    runner/   CONTEXT.md, CHANGELOG.md, skills/PATTERNS.md
    gateway/  CONTEXT.md, CHANGELOG.md
    db/       CONTEXT.md, CHANGELOG.md
    registry/ CONTEXT.md, CHANGELOG.md
    hosting/  CONTEXT.md, CHANGELOG.md
docs/
  EVALUATION_2026-04-18.md          ← Full system evaluation + rec status table
  EVALUATION_2026-07-10.md          ← Runtime audit: loop defects, cleanup, subagent suite + task table
  EVALUATION_2026-07-10-atlas.md    ← Atlas deep-dive (doc verdicts, contract check, ops)
  EVALUATION_2026-08-30.md          ← LATEST: third-party grokbot audit + 2026-08-31 remediation disposition
  superpowers/plans/                ← Executable implementation plans (incl. 2026-07-10 remediation)
  superpowers/specs/                ← Specs behind shipped plans
  TROUBLESHOOTING.md                ← Failure modes + fixes
  PHASE_3_PLAN.md through PHASE_6_PLAN.md  ← Historical (all shipped)
  README.md                         ← Reading order guide
evals/
  README.md                         ← Behavioural skill-eval harness (regression net for skills)
  harness.py / run.py               ← Pure logic (tested) + on-demand orchestrator
  cases/<skill>.yml                 ← Eval cases: input + rubric + baseline_score
ops/
  heartbeat-worker/                 ← Cloudflare Worker: external dead-man's-switch (polls /health, alerts Telegram)
skills/
  TEMPLATE.md                         ← Reference template for new skills
  <name>/SKILL.md                     ← Frontmatter (config) + body (system prompt)
projects/<slug>/
  CLAUDE.md                         ← Project session directive
  manifest.yml                      ← Machine-readable hosting config
  .context/CONTEXT.md               ← Standard format: Mission, Platforms, Web Serving, Architecture, Status
  .context/CHANGELOG.md             ← Project-level change history
```

## Key conventions

- **SKILL.md frontmatter is the machine contract** — model, effort, tools, post_review, isolation settings
- **SKILL.md body is the system prompt** — instructions to Claude, not documentation
- **CHANGELOG.md is institutional memory** — every code-touching session appends
- **PROTOCOL.md is immutable** — never modify without explicit human request
- **Phase plans are historical** — all 6 phases shipped; plans document what was planned vs what happened
- **Single-writer topology** — code is born in the dev repo (`~/Documents/repos/ai-server`); production (`~/Library/Application Support/ai-server`) is a pull-only deploy target that births only runtime doc learnings (auto-published hourly by `scripts/sync-learnings.sh`). See CLAUDE.md.
- **Isolation tiers** — skills declare `isolation: none|workspace|host`; code-writing skills run in per-job clones with enforced PreToolUse guard hooks (`src/runner/guards.py`), `god` is the only host-tier skill. The docker `container` tier was retired 2026-07-27 (`docs/SDK_MIGRATION_2026-07-27.md`; `docs/CONTAINERS.md` is historical).
- **In-session subagents** — skills declare `subagents: [code-review, ...]` in frontmatter; the runner compiles those skills into SDK AgentDefinitions (`src/runner/agents.py`) for Task-tool delegation inside the session.

## Additions 2026-07-12 (P0–P3)

| I need to... | Read these |
|---|---|
| Deploy the server (dev → prod) | `skills/server-deploy/SKILL.md`, CLAUDE.md § Single-writer topology |
| Understand runtime-learning sync | `scripts/sync-learnings.sh` (header comment) |
| Understand workspace isolation + guard hooks | `src/runner/workspaces.py` + `src/runner/guards.py` docstrings, SYSTEM.md INV-16..18 |
| Understand the plan → DAG → evaluate pipeline | `skills/plan/SKILL.md`, `skills/_evaluate/SKILL.md`, `src/runner/plans.py`, SYSTEM.md § Data flow |
| Understand routing (rules + LLM fallback) | `src/runner/router.py`, `src/runner/llm_router.py` |
| Check routing precision / task-event markers | audit events `routing_decision`, `task_plan`, `eval_pass`/`eval_fail` in `volumes/audit_log/` |
| Read the audit that motivated all of this | `docs/AUDIT_2026-07-12.md` |
| Understand the management hierarchy (agents-as-org) | `.context/org/ORG.md` (chart + operating model), `.context/org/divisions/<div>/CHARTER.md` (per-division), `docs/superpowers/plans/2026-07-28-management-hierarchy.md` (design + rollout) |
| Understand the autonomous execution lane (no-approval merge/deploy, read-only+dispatch tier, breaker, autopilot) | `docs/superpowers/plans/2026-07-31-autonomous-execution.md` (design + safety inventory), MISSION.md § M, SYSTEM.md INV-4/INV-20 |
| Understand the multi-provider model-router plan (Codex/Gemini/OpenRouter/local lanes, INV-21) | `docs/superpowers/plans/2026-08-10-model-router.md` (APPROVED 2026-08-17 — MISSION non-goals amended, free-tiers-only; implementation R0 not started) |

## Additions 2026-07-27 (SDK-native overhaul)

| I need to... | Read these |
|---|---|
| Understand the SDK migration (why containers left, what replaced them) | `docs/SDK_MIGRATION_2026-07-27.md` |
| Understand guard hooks (INV-17 enforcement) | `src/runner/guards.py` docstring, `tests/test_guards.py` |
| Expose a skill as an in-session subagent | `skills/TEMPLATE.md` (frontmatter `subagents:`), `src/runner/agents.py` |
| See why `docs/CONTAINERS.md` is historical | its header note + git history |

## Additions 2026-08-26 (autonomous trading vertical)

| I need to... | Read these |
|---|---|
| Understand the autonomous trading design (evidence base, risk kernel, learning loop, owner ignition) | `docs/superpowers/plans/2026-08-26-autonomous-trading.md`, atlas `plans/trader/DESIGN.md`, atlas `trader/CLAUDE.md` |
| Work on the trader loop skills | `skills/atlas-trader-{paper,research,evaluate}/SKILL.md` (staged in atlas `integrations/ai-server/`) |
| Understand how live money would ever be enabled (owner-only) | atlas `trader/GO_LIVE.md` + `trader/CLAUDE.md` rule 1 |

## Additions 2026-08-27 (trading bot verticals — BUILT 2026-08-30, v3)

| I need to... | Read these |
|---|---|
| Understand the swing auto-trader (Tradier, live-small-day-1 + scale ladder) and the value ADVISOR (theses + shadow ledger for the owner's own portfolio — no order path) | `docs/superpowers/specs/2026-08-27-two-trading-bots-design.md`; implementation plan `docs/superpowers/plans/2026-08-30-trading-bots-implementation.md` |
| Work on the swing/value loop skills | `skills/atlas-{swing-supervise,swing-trade,swing-research,swing-evaluate,value-theses,value-monitor,value-research,value-evaluate}/SKILL.md` (staged byte-identical from atlas `integrations/ai-server/`) |
| Understand how swing live money is gated | atlas `swing/LADDER.md` + `swing/CLAUDE.md` rule 1 (sandbox pin + R22 cap, owner hand-edits only) |

## Additions 2026-08-30 (atlas advisors — YouTuber persona shadow scoreboard)

| I need to... | Read these |
|---|---|
| Understand the advisors vertical (persona minds, shadow books, consensus, digest) | `docs/superpowers/specs/2026-08-30-atlas-advisors-design.md`; atlas `advisors/CLAUDE.md` |
| Work on the advisors loop skills | `skills/atlas-advisors-{ingest,panel}/SKILL.md` (staged in atlas `integrations/ai-server/`) |

## Update this file

When you add a new documentation file, add it to this index.
