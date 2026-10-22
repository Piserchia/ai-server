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
    notify/   CONTEXT.md, CHANGELOG.md  ← notifications outbox (Observability Phase 1, 2026-10-21)
docs/
  EVALUATION_2026-04-18.md          ← Full system evaluation + rec status table
  EVALUATION_2026-07-10.md          ← Runtime audit: loop defects, cleanup, subagent suite + task table
  EVALUATION_2026-07-10-atlas.md    ← Atlas deep-dive (doc verdicts, contract check, ops)
  EVALUATION_2026-08-30.md          ← LATEST: third-party grokbot audit + 2026-08-31 remediation disposition
  superpowers/plans/                ← Executable implementation plans (incl. 2026-07-10 remediation)
  superpowers/specs/                ← Specs behind shipped plans
  research/llm-landscape-2026-09/   ← LLM vendor/runtime research set (2026-09-24); 00-comparison-matrix.md is the index
    design-panel/                    ← the six architecture proposals + synthesis + current-state map the multi-model spec cites ("state map §n", "interface-first §n", …)
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
| Add, alias or retire a model id / provider (`[provider/]model_id`) | `models.yml` (repo root), `src/registry/models.py`, `.context/modules/registry/CONTEXT.md` § models; enable a provider via `ROUTER_PROVIDERS_ENABLED` (owner) |
| Check routing precision / task-event markers | audit events `routing_decision`, `task_plan`, `eval_pass`/`eval_fail` in `volumes/audit_log/` |
| Read the audit that motivated all of this | `docs/AUDIT_2026-07-12.md` |
| Understand the management hierarchy (agents-as-org) | `.context/org/ORG.md` (chart + operating model), `.context/org/divisions/<div>/CHARTER.md` (per-division), `docs/superpowers/plans/2026-07-28-management-hierarchy.md` (design + rollout) |
| Understand the autonomous execution lane (no-approval merge/deploy, read-only+dispatch tier, breaker, autopilot) | `docs/superpowers/plans/2026-07-31-autonomous-execution.md` (design + safety inventory), MISSION.md § M, SYSTEM.md INV-4/INV-20 |
| Understand the multi-provider model-router plan (Codex/Gemini/OpenRouter/local lanes, INV-21) | `docs/superpowers/plans/2026-08-10-model-router.md` (APPROVED 2026-08-17 — MISSION non-goals amended, free-tiers-only; never started; **superseded in scope by `docs/superpowers/specs/2026-09-25-multi-model-platform-design.md`**, see Additions 2026-09-25) |

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

## Additions 2026-09-01 (atlas firm layer — BUILT same day)

| I need to... | Read these |
|---|---|
| Understand the firm program (cross-vertical risk book/P&L, advisory CIO + graduation gates, schedule-adherence monitor, role handbooks, dashboard Firm section) | `docs/superpowers/specs/2026-09-01-atlas-firm-org-design.md`; plans `docs/superpowers/plans/2026-09-01-firm-ws1-schedule-monitor.md` + `2026-09-01-firm-ws2a-spine.md` |
| Understand the schedule-adherence monitor (missing-run axis, DARK/NEVER_RAN/STUCK/FAILURE_STREAK/DEFERRED) | `src/runner/schedule_adherence.py` docstrings; `.context/modules/runner/CONTEXT.md`; `scripts/schedule-monitor.sh` header |
| Find out why a schedule row stopped running and DMed `⏸ <name> deferred — <file> lacks <KEY>` (the scheduler `provisioning_gap` pre-check, D1 2026-10-21: which `.env` is checked, the INV-3 exemptions, `job_payload.env_required`, `/status` + Sunday `DEFERRED`, how to provision or un-declare) | `docs/TROUBLESHOOTING.md` "schedule deferred (provisioning_gap)"; `.context/modules/runner/CONTEXT.md` (D1 bullet); `.context/modules/registry/CONTEXT.md` (`Manifest.env_required`); `volumes/audit_log/schedules/<schedule_id>.jsonl`; `scripts/seed-schedules.sh` (the four swing rows) |
| Understand the notifications outbox, or find out why a job/task DM never arrived (row status, `NOTIFY_OUTBOX`, `[Details]`, the out-of-band `python -m src.notify send` path of the launchd alerters) | `.context/modules/notify/CONTEXT.md`; `.context/modules/gateway/CONTEXT.md` § Notifications back to user; `docs/TROUBLESHOOTING.md` "no completion/failure DM"; `scripts/healthcheck-all.sh` / `scripts/schedule-monitor.sh` headers; `tests/test_scripts_syntax.py` (timer-script invariants) |
| Work on the firm loop skills | `skills/atlas-{cio,firm-rollup}/SKILL.md` (staged byte-identical from atlas `integrations/ai-server/`); atlas `firm/CLAUDE.md` + `firm/charters/` |
| Understand how firm authority is gated | atlas `firm/FIRM_AUTHORITY.md` + `firm/CLAUDE.md` Rule 1 + atlas `evaluation/LOOP.md` §6 |

## Additions 2026-09-09 (pickem league dashboard — LIVE 2026-09-10)

| I need to... | Read these |
|---|---|
| Understand the pick'em league dashboard (CBS GraphQL ingest, prize/leaderboard engine, AI analysis lane) — **live** at pickem.chrispiserchia.com since 2026-09-10: site, `pickem-sync`/`pickem-analysis` skills and the 4×/week sync schedule (Sun/Mon/Tue/Fri 09:00 UTC) all shipped | `docs/superpowers/specs/2026-09-09-pickem-league-design.md`; project `~/Documents/repos/pickem` (its `.context/CONTEXT.md` + `CHANGELOG.md`); `.context/SKILLS_REGISTRY.md` |

## Additions 2026-09-14 (alpha-lab — owner-idea triage vertical, DESIGN approved)

| I need to... | Read these |
|---|---|
| Understand the alpha-lab vertical (owner submits an alpha idea → autonomous triage/backtest chain → GO / NO-GO / BLOCKED-ON-DATA verdict memo; verdicts only, no build, no order path) — spec approved 2026-09-14 (see its Amendments section), implemented same day | `docs/superpowers/specs/2026-09-14-alpha-lab-design.md`; plan `docs/superpowers/plans/2026-09-14-alpha-lab-implementation.md`; atlas `alpha-lab/CLAUDE.md` |
| Work on the alpha-lab loop skills | `skills/alpha-{intake,research,governor}/SKILL.md`; atlas `alpha-lab/evaluation/PROTOCOL.md` (binding) |


## Additions 2026-09-23 (alpha flywheel — continuous generate→evaluate→learn loop)

| I need to... | Read these |
|---|---|
| Understand the flywheel (alpha-scout generator fenced by FAMILIES.md + LESSONS.md, near-miss refinement depth ≤ 2, distinct-pair lifetime N resolving D-0001, quantlab as alpha-lab's daily-bar harness engine, idle-queue governor drainer, 12/day + 4-active budgets, GO = memo + graduation offer) | `docs/superpowers/specs/2026-09-23-alpha-flywheel-design.md`; plan `docs/superpowers/plans/2026-09-23-alpha-flywheel-implementation.md`; atlas `alpha-lab/evaluation/{PROTOCOL.md,FAMILIES.md,LESSONS.md}` |
| Work on the flywheel skills | `skills/alpha-scout/SKILL.md` (new), `skills/alpha-{research,governor}/SKILL.md` (amended via LOOP.md §7 front door) |
| Understand the idle drainer | `src/runner/events.py` `_should_trigger_idle_alpha` + `.context/modules/runner/CHANGELOG.md` |

## Additions 2026-09-16 (quant stack — validation-desk vertical)

| I need to... | Read these |
|---|---|
| Understand the quant validation desk (the "$200K quant stack": pure-stdlib backtest engine with the shift(1) law + turnover costs, Sharpe/MDD/Calmar metrics, Bailey–López de Prado Deflated Sharpe vs lifetime trial N, walk-forward judged on the worst fold, 8-check leakage critic, sizing + pre-committed kill conditions, weekly automated reports at atlas /quant; three-layer turn-on switch; no order path ever) | `docs/superpowers/specs/2026-09-16-quant-stack-design.md`; plan `docs/superpowers/plans/2026-09-16-quant-stack-implementation.md`; atlas `quant/CLAUDE.md` + `quant/evaluation/PROTOCOL.md` |
| Work on the quant loop skills | `skills/atlas-quant-{validate,governor}/SKILL.md` (staged byte-identical from atlas `integrations/ai-server/`) |
| See the adversarial execution review of the build (findings register F1–F7, incl. the open D-0001 DSR-ratchet owner decision) | `docs/QUANT_STACK_ADVERSARIAL_2026-09-16.md` |

## Additions 2026-09-16 (pickem trash-talk board — LIVE same day)

| I need to... | Read these |
|---|---|
| Understand the pickem trash-talk board (free-name UGC threads/comments, commissioner moderation, rate-limited public writes) | `docs/superpowers/specs/2026-09-16-pickem-trash-board-design.md` |

## Additions 2026-10-08 (pickem natural-language charts — PROPOSED, plan written)

| I need to... | Read these |
|---|---|
| Understand the per-player "ask for a chart" feature (prompt → gateway job → Opus-5/low builder + tool-less checker subagent → sandboxed SQL + chart spec stored on the player's page, re-run live on every view; capability-key ownership, caps, owner decisions D1–D6) | `docs/superpowers/specs/2026-10-08-pickem-charts-design.md` |
| Build it task-by-task (11 tasks: pickem migration v3 / sandbox / spec / service / routes / SPA / docs, then ai-server helper script + two skills + golden eval, then ordered rollout) | `docs/superpowers/plans/2026-10-08-pickem-charts.md` |
| Build or change the chart-request builder skill (parse → fetch → process → build → check → complete/fail, schema + glossary + golden prompts) | `skills/pickem-chart/SKILL.md` (+ `SCHEMA.md`, `GLOSSARY.md`, `EVAL.md`) |
| Build or change the independent chart checker subagent (tool-less, grades SQL + spec against the glossary and the player's stat totals) | `skills/pickem-chart-check/SKILL.md` |

## Update this file

When you add a new documentation file, add it to this index.

## Additions 2026-09-25 (multi-model platform — research, spec, P0 plan; all PROPOSED)

| I need to... | Read these |
|---|---|
| Know what every major LLM vendor/runtime offers, costs, permits (terms), and is best at — as of 2026-09-24 | `docs/research/llm-landscape-2026-09/00-comparison-matrix.md` (start here; §5 resolves 31 cross-doc contradictions), then the per-vendor doc (`claude-anthropic.md`, `chatgpt-openai.md`, `grok-xai.md`, `gemini-google.md`, …) |
| Know whether a consumer subscription may be scripted from this server | `docs/research/llm-landscape-2026-09/crosscut-subscription-automation-tos.md` §3.7 (vendor × surface allowed/grey/banned matrix) |
| Know what the 2026 evidence says about LLMs and trading | `docs/research/llm-landscape-2026-09/crosscut-finance-trading-ai.md` §5, §8 |
| Read the superseded-in-scope multi-model platform spec (the vendor-research synthesis, the three applied review rounds, and the full design of every deferred cross-vendor item — Codex executor, free utility lanes, grading belts, provider registry/quota/qualification, executor seam + replay gate, sensitivity labels, remote MCP doors) | `docs/superpowers/specs/2026-09-25-multi-model-platform-design.md` — **SUPERSEDED IN SCOPE 2026-10-05** by `docs/superpowers/specs/2026-10-05-observability-and-trading-unblock-design.md` (owner took the D0 branch "keep the money rules"; the cross-vendor machinery is deferred, not planned — **partly reopened 2026-10-21**: the Codex executor, the dispatch branch and per-provider quota keys shipped as `docs/superpowers/plans/2026-10-21-cross-vendor-writer-slice.md`, see Additions 2026-10-21 below). Still the reference its successor's §14 cites by §-number (§0 decision summary; §0a/§0b amendments to the 2026-08-10 plan; §12 decisions; Appendix A provenance) |
| Execute the first slice (migration 007, ResultMessage capture, notify outbox + origin, ghost commands, Haiku swap, canary, cost reconcile, alembic manifest, ops hygiene) | `docs/superpowers/plans/2026-09-25-multi-model-platform-p0.md` — re-pointed 2026-10-05 at `docs/superpowers/specs/2026-10-05-observability-and-trading-unblock-design.md` §9 **Phase 1**; 20 tasks (the `SDK_RECORD` recorder left with the cut) |
| Read the design panel behind the multi-model spec (six proposals, synthesis, code-level current-state map with the C1–C26 constraints table) | `docs/research/llm-landscape-2026-09/design-panel/` (`current-state-map.md`, `design-synthesis.md`, `design-*.md`) |

## Additions 2026-10-05 (the cut spec — observability, control and the trading unblock; PROPOSED)

| I need to... | Read these |
|---|---|
| Understand the project of record: make the server observable, give the owner a control plane that answers on the phone, define done-ness the runner itself checks, unblock the trading verticals within INV-22, and cut existing spend — Anthropic-only, four phases (**only Phase 1 is planned**), eight owner decisions | `docs/superpowers/specs/2026-10-05-observability-and-trading-unblock-design.md` (§9 phases with entry/exit/kill switches; §10 deleted-rewritten-kept; §12 the eight decisions; §14 what is deferred and what would reopen it; §15 provenance) |
| Know why the 2026-09-25 multi-model spec was cut rather than phased, and what is deferred with its reopening trigger | the cut spec's §0 (three reasons) and §14 (**fifteen** deferred items, each pointing back into `docs/superpowers/specs/2026-09-25-multi-model-platform-design.md`) |
| Execute Phase 1 of the cut spec (observability and hygiene) | `docs/superpowers/plans/2026-09-25-multi-model-platform-p0.md` — the executable form of its §9 Phase-1 row, 20 tasks, execution order in Global Constraints |

## Additions 2026-10-21 (cross-vendor writer slice — Codex as the first non-Anthropic executor; BUILT, merge/deploy pending)

| I need to... | Read these |
|---|---|
| Understand what "use other agents to change this repo / schedule routines on other agents" delivers today: `codex/<id>` jobs run `codex exec --json` in a per-job clone under Seatbelt with a scrubbed env, every diff is reviewed by Anthropic BEFORE the runner commits/pushes, Codex rate limits pause only the Codex lane, and `ROUTER_PROVIDERS_ENABLED=anthropic` (default) refuses every non-Anthropic job fail-closed | `docs/superpowers/plans/2026-10-21-cross-vendor-writer-slice.md` (§1 aggregated state, §2 what ships, §3 decisions D-A..D-D, §4 design deltas, §5 tasks T0–T10 with per-task implementation + review notes, §6 containment, **§7 owner runbook**, §8 gates) |
| Flip the switch / provision Codex (enable the provider, dedicated `CODEX_HOME` stream, tier, `code-server`, protected bundle, deploy) | the plan's §7 (owner actions — auth config and policy, never done by a job); settings in `.context/modules/runner/CONTEXT.md` § Configuration |
| Debug a Codex-lane job (`provider_refused` reasons, `review_blocked`, `codex not found`, `codex exec` hang, `auth_expired`, `job_held`) | `docs/TROUBLESHOOTING.md` (symptoms dated 2026-10-21), then `volumes/audit_log/<job_id>.jsonl` kinds `provider_selected` / `provider_refused` / `executor_started` / `turn_completed` / `executor_error` / `merge_gate_*` / `workspace_published` (shapes in `src/audit_log.py`) |
| Change the executor, the dispatch branch, the pre-push gate or the lane pause | `.context/modules/runner/CONTEXT.md` (`executors.codex_cli`, Provider dispatch, Pre-push gate, `quota.*_provider`), `src/runner/executors/codex_cli.py`, `src/runner/session.py`, `src/runner/review.py`, `src/runner/quota.py`; tests `tests/test_codex_executor.py`, `tests/test_provider_dispatch.py`, `tests/test_pre_push_gate.py`, `tests/test_quota.py`; fixtures `tests/fixtures/codex/` (recorded truth — never a live `codex`) |
| Know what the slice did NOT build and what reopens it (graders/critics, provider ladder, free HTTP lanes, `ExecSpec` seam, `_aicodex` read-side containment, `code-server` routing) | the plan's §6 residual + §9; the cut spec's §14 items 1/9/10 now carry "reopened 2026-10-21" annotations, the rest stay deferred |
| Know which edits the slice could NOT make (protected paths: `scripts/lint_docs.py` rules, `src/runner/guards.py` deny names, SYSTEM.md INV-21 row) | the plan's T8 — a separate owner-merged branch `multi-model/protected-bundle`; until then the slice's own tests enforce the same rules |
| Read or run the weekly cost reconcile (both windows, the §2.8 per-kind step, computed-vs-SDK within 1 % or the implied cache-write rate, the `--db` leg against `jobs.cost_usd_list` / `sdk_cost_usd`, the lane-budget seed; why the Monday DM said "5-minute cache writes present") | `scripts/cost-reconcile.py` header (`--help`), `scripts/cost-reconcile-run.sh` header, `.context/modules/hosting/CONTEXT.md` (timer bullet), `.context/modules/runner/CONTEXT.md` (B1 `pricing` bullet), `docs/TROUBLESHOOTING.md` "cost-reconcile DM"; the measurements go in the re-cut plan's §8 |
| Execute Observability Phase 1 as re-cut against the landed Codex slice (migration **008**, notify outbox + persisted origin, token/cost columns + `cost-reconcile`, ops hygiene incl. atlas dump + R2 retention, the scheduler `provisioning_gap` pre-check; Tier B = the rest of the spec's Phase-1 row) | `docs/superpowers/plans/2026-10-21-observability-phase1-recut.md` — **IN PROGRESS: owner "go" for Tier A 2026-10-21 (branch `observability/phase-1`; A1–A7 = migration 008, origin, quota label, `src/notify/`, runner + bot outbox, alerters landed; B1–B4 = `pricing.py`, `result_capture.py`, both-lane token/cost stamps, `scripts/cost-reconcile.py` + the weekly `com.assistant.cost-reconcile` timer landed; C1 = `backup.sh` atlas dump + sealed secrets + 60-d retention, `restore-drill.sh`, installer timer env block + `timers-only` + plist escaping, the ops-hygiene runbook landed; D1 next)**; §0 lists every delta the slice forced on the 2026-09-25 P0 plan (which stays the detailed design of record per task), §3 the D-P1 defaults, §7 the owner runbook, §8 the exit criteria and the measurements to record |
| Do the by-hand ops steps Phase 1 needs (entry probes, `pmset`, the R2 bucket + `rclone` remote `r2`, the backup seal key, the restore drill, `install-launchd.sh timers-only` / the full install, the Ollama prune, the D4 confirmations, bingo's hook) and know what to write back | `docs/runbooks/2026-10-21-phase1-ops-hygiene.md` (C1, 2026-10-21; §0–§9 in order, each with its verification line); `scripts/backup.sh` + `scripts/restore-drill.sh` headers; `.context/modules/hosting/CONTEXT.md` (the backup / drill / installer bullets); `docs/TROUBLESHOOTING.md` symptom "`offsite SKIP` / `seal SKIP` / drill `WARN`" |

## Additions 2026-10-21 (MoneyMachine Company — bucketed self-running agent company; BUILT, armed phase 0)

| I need to... | Read these |
|---|---|
| Understand the company (four buckets `etf` / `longterm` / `shortterm` / `crypto`, one shared six-officer hierarchy as nine `mm-*` skills, arbitrage-first hypothesis families, the one-stage-per-job loop, weekly owner memo; reports only — INV-22: no order path) | `docs/superpowers/specs/2026-10-21-moneymachine-company-design.md` §0–§4; repo `~/Documents/repos/moneymachine` (GitHub `alfredbot-ai-butler/moneymachine`, canonical): `company/{COMPANY,LOOP,PROTOCOL,MM_AUTHORITY}.md` |
| Work on the skills | `skills/mm-*/SKILL.md` (frontmatter = contract; each reads the repo's `company/officers/<role>.md` handbook first), `tests/test_mm_skills.py`, `.context/org/divisions/moneymachine/CHARTER.md` |
| Operate it (read the memo, pause/resume, manual CEO trigger, stop in-flight chains, apply an approved `[system]` item, refresh the prod clone) | repo `docs/OWNER.md`; the three schedule rows in `scripts/seed-schedules.sh` — `mm-ceo-weekly` (Sat 17:00 UTC), `mm-report-weekly` (Sat 19:30 UTC), `mm-resume-daily` (daily 10:30 UTC); kill switch `/schedule pause mm-ceo-weekly` (plus `company/config/settings.yaml` `enabled: false`, fail-closed) |
| Build it task-by-task | `docs/superpowers/plans/2026-10-21-moneymachine-company.md` (Tasks 1–15: repo + constitution + `mmcore` + adapters + buckets, then skills, tests, charter, registries, schedules, gates, provisioning) |
