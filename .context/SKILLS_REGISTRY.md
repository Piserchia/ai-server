# Skills registry

> Master index of all skills. Auto-generated target; for now maintained by hand.
> When you add a skill via `new-skill`, it appends to this file.

## Installed

| Skill | Model / Effort | Purpose | Phase |
|---|---|---|---|
| `chat` | Sonnet 4.6 / low | One-shot conversation, no tools | 1 |
| `research-report` | Sonnet 4.6 / medium (→ Opus 4.7 / high on failure) | Web research + dated markdown report under `projects/research/` | 2 |
| `_writeback` | Sonnet 4.6 / low | **Internal.** Follow-up session that updates CHANGELOGs when the primary session skipped the write-back. Not user-triggerable. | 2 |
| `code-review` | Opus 4.7 / high (plan mode) | Review code diffs for correctness, security, style. Used as post-session sub-agent and standalone. | 4 |
| `app-patch` | Opus 4.7 / high | Patch existing projects — direct commit + push to main | 4 |
| `new-skill` | Opus 4.7 / high (workspace; autonomous-merge lane) | Meta-skill: author new skills from natural-language descriptions. Lands autonomously on gate-green + code-review LGTM + owner notification; a new skill declaring prod-operator/break-glass privilege or host isolation is ALWAYS owner-approval | 4 |
| `project-evaluate` | Opus 4.7 / high | Read a project codebase and produce manifest.yml + standard .context/CONTEXT.md | 4 |
| `new-project` | Opus 4.7 / high (two-phase: plan arch then implement) | Scaffold, document, deploy, and register a new project | 4 |
| `self-diagnose` | Opus 4.7 / high | Investigate failures + apply fixes based on risk classification | 4 |
| `server-upkeep` | Sonnet 4.6 / low (→ Sonnet 4.6 / medium on failure) | Daily health audit: rotate logs, VACUUM DB, check project status, DM anomalies only | 5 |
| `server-patch` | Opus 4.7 / xhigh (post-review always; autonomous-merge lane) | Modify server code (src/, scripts/, alembic/). Merges autonomously on gate-green + in-session code-review LGTM + owner notification (MISSION §M, 2026-07-31); protected paths always stop at a PR for owner approval | 5 |
| `review-and-improve` | Opus 4.7 / max (acceptEdits; hook-enforced read-only, INV-20 — plan mode had silently blocked its dispatch for weeks) | Analyze recent job data, propose tuning changes. Dispatches server-patch follow-up | 5 |
| `research-deep` | Opus 4.7 / high (-> Opus 4.7 / xhigh on failure) | Deep-dive research: 10-20 sources, 2000-5000 words, conflicting-evidence treatment | 6 |
| `idea-generation` | Sonnet 4.6 / medium | Generate 3-5 novel ideas, deduped against prior ideas in history.jsonl | 6 |
| `project-update-poll` | Haiku 4.5 / low | Run a project's configured `on_update` command. Cheap, fast, fail-silent | 6 |
| `restore` | Sonnet 4.6 / medium | Restore from backup tarball. DESTRUCTIVE -- requires explicit user confirmation | 6 |
| `_learning_apply` | Sonnet 4.6 / low | **Internal.** Appends learning proposals from the learning extractor hook to `.context/modules/<x>/skills/<CATEGORY>.md`. Not user-triggerable. | Rec 1 |
| `god` | Opus 4.7 / max (bypassPermissions, 200 turns) | Full-context, full-permission admin session. Equivalent to a human at the terminal. **Host-native by design** (isolation: host) — the break-glass fix-anything-from-Telegram lane. | — |
| `server-deploy` | Opus 4.7 / high (→ max on failure) | **Self-healing** deploy operator for the ai-server: sync learnings, ff-only pull, migrate (validated+snapshotted), pytest gate, seed schedules (idempotent), restart web/bot + detached runner. On failure it fixes on the go — operational autonomously; code fixes born in the dev repo, re-gated + `code-review`-LGTM'd + owner-notified before deploy (owner-authorized narrowing of INV-4, deploy path only). The gate is never bypassed. Trigger: `/task deploy server` | P0 |
| `project-redeploy` | Sonnet 4.6 / low (→ Opus 4.7 / high on failure) | Contract-driven deploy for any project: ff-only pull into the runtime clone, run the manifest's declared gates (test/build/healthcheck) in order, restart only affected services. Red gate = old code keeps running. Generic engine `atlas-redeploy` is a special case of. Trigger: `redeploy <slug>` | Segregation |
| `plan` | Opus 4.7 / high | Decompose a complex ask into a structured plan (goal, acceptance criteria, subtask DAG) emitted as a `task_plan` event; runner spawns dependency-ordered subtask jobs. Auto-approved by default (`PLAN_AUTO_APPROVE`). | P2 |
| `system-manager` | Opus 4.7 / high (acceptEdits; hook-enforced read-only + dispatch, INV-20) | **CEO agent.** Monthly: reconciles every division's report against MISSION, finds cross-division gaps/misalignments, owns the org structure. Directs + may dispatch gated workers (`new_skill`/`server_patch`); never edits/merges itself. See `.context/org/ORG.md`. | Mgmt |
| `ops-manager` | Opus 4.7 / high (acceptEdits; hook-enforced read-only + dispatch, INV-20) | **Platform Ops department manager.** Weekly: evaluates its division's health/deploy/DR state → report with prioritized recommendations; may dispatch gated workers for them. Exemplar for the manager-hierarchy pattern. | Mgmt |
| `gap-auditor` | Opus 4.7 / high (plan mode, read-only) | **The negative-space auditor.** Finds what's MISSING — capability gaps within a division (as a manager's subagent) and unowned domains/seams org-wide (for the CEO). Recurring version of the manual system evaluation. Finds + routes; never builds. | Mgmt |
| `delivery-manager` | Opus 4.7 / high (acceptEdits; hook-enforced read-only + dispatch, INV-20) | **Delivery department manager.** Weekly: evaluates the project lifecycle (create→host→deploy→verify→update) across its roster + delivery-contract adoption + dev-repo coherence → report with prioritized recommendations. Proposes; never executes. | Mgmt |
| `knowledge-manager` | Opus 4.7 / high (acceptEdits; hook-enforced read-only + dispatch, INV-20) | **Knowledge department manager.** Weekly: evaluates research/ideas cadence, content dedup, off-site backup state → report with prioritized recommendations. Proposes; never executes. | Mgmt |
| `atlas-manager` | Opus 4.7 / high (acceptEdits; hook-enforced read-only + dispatch, INV-20) | **Atlas department manager.** Weekly: evaluates the atlas product sub-org (reports/scout/brief/portfolio/deploys) + its standing standards (single-writer, `ANTHROPIC_API_KEY` boundary) → report with prioritized recommendations. Proposes; never executes. | Mgmt |
| `delivery-ops-reconciler` | Opus 4.7 / high (plan mode, read-only) | **Cross-division connector (Delivery→Ops).** Weekly: reconciles shipped-vs-operated (registration, healthcheck coverage incl. what healthcheck-all silently skips, supervision, backup/DR) → drift report with routed proposed fixes. Proposes; never executes. | Mgmt |
| `insight-router` | Opus 4.7 / high (plan mode, read-only) | **Cross-division connector (Knowledge/Atlas→all).** Weekly: reads the week's research/ideas/atlas output, extracts insights actionable OUTSIDE their origin division, routes each with evidence + a named gated worker skill. Routes; never executes. | Mgmt |
| `deploy-director` | Opus 4.7 / high (→ max on failure; acceptEdits — plan mode blocks dispatch-MCP; hook-enforced read-only, INV-20) | **Deployment director.** Dispatched per re-deployment (`deploy-director: server` or `<slug>`; `verify <target>` mode): derives the what's-deploying summary from the actual pending range, preflights (divergence, in-flight jobs, substrate, backup age), risk-classifies, dispatches the gated executor (`server-deploy`/`project-redeploy`/`atlas-redeploy`) with the summary attached, and independently verifies post-conditions. Directs + verifies; never executes a deploy itself. | Ops |
| `_evaluate` | Sonnet 4.6 / medium | **Internal.** Post-`task_complete` acceptance evaluator: checks plan/ask criteria against evidence (diff, tests, healthchecks), emits `eval_pass`/`eval_fail`. Pass auto-closes the task with evidence; fail re-opens with feedback (max 2 rounds). | P3 |
| `atlas-report` | Sonnet 4.6 / medium (→ Opus 4.7 / high on failure) | Author one Atlas expert report (asset / sector / portfolio) on subscription auth; persisted + evaluated via `atlas-dash save-report`; evaluator lessons feed the expert's knowledge file (`atlas-dash learn`) | — |
| `atlas-report-sweep` | Sonnet 4.6 / medium (→ Opus 4.7 / high on failure) | Weekly full pass: refresh data, enumerate targets, one report per holding + sector + the portfolio (fan-out via enqueue_job, sequential fallback). Scheduled Sunday evenings | — |
| `atlas-scout` | Sonnet 4.6 / medium (→ Opus 4.7 / high on failure) | Screen stocks on technical+fundamental combos from a deterministic snapshot; validated picks (2% citation gate, thesis/combo/risk) land as watchlist suggestions with price-at-suggestion for future performance scoring. Trigger: `/task scout stocks` or the stocks page button | — |
| `atlas-daily-brief` | Sonnet 4.6 / medium (→ Opus 4.7 / high on failure) | Pre-open synthesis: market regime + book + signal flips + crypto cycle + on-deck items, ≤250 words; delivered via job summary (Telegram) and pinned into the /indicators market chat. Schedule: daily 12:00 UTC | — |
| `atlas-chat` | Sonnet 4.6 / medium (→ Opus 4.7 / high on failure) | Answer an owner question about one Atlas report, inline on the report page — as the authoring sector expert, grounded in the report's own packet/charter/knowledge/glossary; persists via `atlas-dash chat-save`. Trigger: web enqueues `atlas-chat: report <uuid>` | — |
| `atlas-redeploy` | Sonnet 4.6 / low (→ Opus 4.7 / high on failure) | Deploy pipeline for projects/atlas: ff-only pull, migrate, test gates (red = no restart), build, restart, healthcheck. Trigger: `/task redeploy atlas` after dev-repo commits | — |
| `atlas-portfolio` | Sonnet 4.6 / medium (→ Opus 4.7 / high on failure) | Portfolio manager: answers book questions AND records owner-stated transactions ("sold 0.5 BTC at 64k") via engine CLI sell/set-position/add-holding — idempotency check before writes, ambiguity asks instead of guessing, replies via `chat-save --portfolio`. Trigger: web enqueues `atlas-portfolio: <text>` | — |
| `atlas-evaluate` | Opus 5 / high (→ Opus 5 / xhigh on failure) | Weekly living-loop GOVERNOR (atlas dev clone; contracts in atlas `evaluation/LOOP.md`): adopts the project-evaluator charter, scores the rubric with evidence, triages `data_gaps`, grades shipped builds via `Loop-Item:` commit footers, promotes `built→live` with landed-rows evidence, runs stuck-state + schedule-liveness sweeps, re-routes `evaluation/BACKLOG.md` with builder-eligibility marking. Judges and routes; never builds or deploys. Schedule: Mon 11:00; staged from atlas `integrations/ai-server/` | — |
| `atlas-build` | Opus 4.8 / high (→ Opus 5 / xhigh on failure; workspace isolation; post-review always) | Twice-weekly loop BUILDER: top eligible S/M backlog item (specced pipeline / UI / glossary / tests) → engineer charter in a per-job workspace clone (shared dev clone never dirties) → manifest test gates + verify skill + in-session `code-review` LGTM → ONE commit with `Loop-Item:`/`Gap:`/`Job:` footers → push GitHub master → `gaps-set built` → dispatches `deploy_director` (gated by the in-session code-review LGTM before push + `atlas_redeploy`'s pytest gates where red = old code keeps serving). Never deploys itself (launchctl guard-denied). post_review is a second belt that flags after the fact. Schedule: Tue+Fri 10:00, payload `project_slug: atlas`; staged from atlas `integrations/ai-server/` | — |
| `atlas-gap-scout` | Opus 4.8 / medium (→ Opus 5 / high on failure) | Weekly gap-scout (atlas dev clone): adopts the pipeline-scout charter, takes the top triaged data gap, researches a FREE source, runs the live probe from the Mini, writes the engineer-ready spec ending in a **builder acceptance** row (`knowledge/<sector>/pipelines.md`), marks the gap SPECCED, pushes. Ceiling FEED_SPECCED; never builds. Schedule: Wed 11:00; staged from atlas `integrations/ai-server/` | — |
| `atlas-momo-research` | Opus 5 / high (→ Opus 5 / xhigh on failure; workspace isolation; post-review always) | Weekly Momentum-Lab research cycle (Thu 13:00, payload `project_slug: atlas`): one governed hypothesis cycle in a per-job workspace clone of the atlas repo — analyst cards → single budgeted TRAIN experiment → adversarial validation → risk review → append-only ledger close-out, under atlas `momentum/evaluation/PROTOCOL.md` (binding) via the six `.claude/agents/momo-*` charters. Mechanics/IEX-observe mode until the owner approves the SIP data gap; paid data, live money, and validation-window fetches are owner-only ceilings it may recommend but never execute. Staged from atlas `integrations/ai-server/` | — |
| `atlas-refresh-knowledge` | Sonnet 4.6 / medium (→ Opus 4.8 / high on failure) | Monthly knowledge maintenance (atlas dev clone): curator condensation of `knowledge/*/CLAUDE.md` to 150-line budgets, re-verification of stale (>90d) load-bearing claims with fresh sources, `gaps-sync` ledger reconciliation, glossary guard, pushes. Schedule: 1st 11:30; staged from atlas `integrations/ai-server/` | — |

## Deferred

| Skill | Reason |
|---|---|
| `notify` (no-LLM MCP tool) | Originally planned for Phase 4. MCP dispatch via `enqueue_job` covers the primary use case (spawning child jobs). A dedicated no-LLM notify tool can be added if Telegram DM-on-demand is needed outside job completion. |

## Scripts (non-skill, no LLM)

| Script | Path | Phase |
|--------|------|-------|
| `backup` | `scripts/backup.sh` (launchd timer at 04:00) | 5 |
| `healthcheck-all` | `scripts/healthcheck-all.sh` (launchd timer every 5 min) | 3 |

## Conventions

- Skill directories with a leading underscore (`_writeback`) are **internal** —
  spawned by the runner, not user-triggerable via `/task`.
- Skill directory name follows the job `kind` with two rules:
  - Leading underscore preserved: `_writeback` → `skills/_writeback/`
  - Other underscores → dashes: `research_report` → `skills/research-report/`
- Each skill's YAML frontmatter is the machine contract; the markdown body
  becomes the system prompt.
- Supported frontmatter fields: `name`, `description`, `model`, `effort`,
  `permission_mode`, `required_tools`, `max_turns`, `escalation`, `post_review`,
  `tags`, `context_files`, `no_llm`. See `src/registry/skills.py:SkillConfig`.
- `context_files`: list of documentation files the session should read first.
  Injected into the server directive by `session.py:_build_server_directive()`.
