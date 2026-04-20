# Changelog: runner

<!-- Newest entries at top. Every session that modifies this module appends here. -->

## 2026-04-20 — Multi-turn task interaction with approval flow

**Files changed**:
- `src/runner/session.py` — Added `format_task_turns()` pure helper and
  `_build_task_context()` which loads prior turns from DB and injects a
  "Task conversation" section into the system prompt for continuation jobs.
  Added `_fetch_task_turns()` async helper.
- `src/runner/main.py` — Added `_update_task_after_job()` which runs after
  task-linked jobs complete. Records assistant turns, detects `task_question`
  and `task_complete` audit events, updates task status, and publishes
  notifications via `tasks:notify` Redis channel.

**Why**: Jobs were one-shot with no way to respond to output or approve
completion. Tasks now wrap jobs into multi-turn conversations where the
user can reply and the system continues with full context.

**Side effects**: Every task-linked job now triggers `_update_task_after_job`
after completion (non-fatal). Jobs without `task_id` are unaffected.

## 2026-04-20 — Skill consistency: sections lint, post_review standardization, template

**Files changed**:
- `scripts/lint_docs.py` — New `check_skill_sections()` (8th lint check).
  Non-internal skills must have `## Gotchas` section and body >= 10 lines.
- `skills/TEMPLATE.md` (NEW) — Reference template for skill authors.
  Documents required frontmatter fields, required body sections (Inputs,
  Procedure, Quality gate, Gotchas), optional sections, and conventions.
- `skills/new-skill/SKILL.md` — References TEMPLATE.md as first step.
- `skills/app-patch/SKILL.md`, `skills/new-project/SKILL.md`,
  `skills/new-skill/SKILL.md`, `skills/project-evaluate/SKILL.md` —
  Added explicit `reviewer_model` + `reviewer_effort` to post_review config.
- `skills/code-review/SKILL.md` — Added `## Gotchas` section (was missing).

**Why**: Skill bodies were structurally inconsistent. No template for new
skill authors. Post-review config was implicit except for server-patch.
New lint check catches structural gaps early.

**Side effects**: New lint check (8th) runs on every invocation. Skills
missing Gotchas will be flagged — code-review was the only one.

## 2026-04-20 — Debugging: error categorization, incremental index, failure correlation

**Files changed**:
- `src/runner/audit_index.py` — Added `categorize_error()` pure function
  that classifies error messages into categories (quota, auth, timeout,
  tool_error, network, import_error, schema, unknown). Added
  `error_category` field to `IndexEntry`. Added `append_to_index()` for
  incremental index updates without full rebuild.
- `src/runner/main.py` — `job_failed` audit events now include
  `error_category`. `_finish_job()` calls `append_to_index()` after every
  job completion/failure for real-time index freshness.
- `src/runner/events.py` — Multi-skill failure correlation: if 3+ different
  skills fail within 5 minutes, enqueues a single combined self-diagnose
  with `target_kind: multi-skill` instead of N separate diagnoses.
- `.context/SYSTEM.md` — Added `runner.audit_index` to runner.main deps.

**Why**: Error messages were unstructured text — no aggregation possible.
Audit index was stale between nightly rebuilds. Multi-skill failures
triggered redundant diagnoses instead of surfacing shared root cause.

**Side effects**: Every finished job now appends to INDEX.jsonl (~1ms).
New `error_category` field in audit events and index entries.

## 2026-04-20 — Feedback loops: unified MCP tags, escalation, parent tracking

**Files changed**:
- `src/runner/session.py` — Removed `_NEEDS_PROJECTS_MCP` and
  `_NEEDS_DISPATCH_MCP` hardcoded sets. MCP injection now uses frontmatter
  tags as sole source of truth. Added `parent_job_id` field to `job_started`
  audit log events for child jobs (enables cross-job tracing without DB).
- `skills/review-and-improve/SKILL.md` — Added `needs-projects-mcp` tag
  (was hardcoded only).
- `skills/server-upkeep/SKILL.md` — Added `needs-projects-mcp` tag.
- `skills/server-patch/SKILL.md` — Added `needs-projects-mcp` tag.
- `skills/app-patch/SKILL.md` — Added `escalation.on_failure` (Opus 4.7 / xhigh).
- `skills/new-skill/SKILL.md` — Added `escalation.on_failure` (Opus 4.7 / max).

**Why**: MCP opt-in had a dual source of truth (hardcoded sets + tags).
Now tags-only — single source, auditable in each SKILL.md. app-patch and
new-skill previously hard-failed with no retry; now escalate on failure.
Parent_job_id in audit events enables log-only causality tracing.

**Side effects**: Skills that relied on the hardcoded sets but lacked tags
would break — all 4 have been updated with the correct tags.

## 2026-04-20 — Knowledge surfacing: seed module skills + auto-inject + context_files validation

**Files changed**:
- `.context/modules/runner/skills/GOTCHAS.md` — Seeded with 5 entries from
  Troubleshooting.md and CHANGELOG gotchas (audit_log.append collision,
  _writeback false positives, stuck jobs, SDK version mismatch, import lint).
- `.context/modules/runner/skills/DEBUG.md` — Seeded with 2 entries (8-step
  failure triage order, quota false positive detection).
- `.context/modules/gateway/skills/GOTCHAS.md` — Seeded with 2 entries
  (Telegram done-listener mapping, dashboard 404).
- `.context/modules/hosting/skills/GOTCHAS.md` — Seeded with 5 entries
  (cloudflared TLS, config location, plist args, Python modules, TCC).
- `.context/modules/hosting/skills/DEBUG.md` — Seeded with 2 entries
  (runner restart checklist, cloudflared no connections).
- `.context/modules/db/skills/GOTCHAS.md` — Seeded with 2 entries
  (sqlalchemy.update collision, never edit migrations).
- `src/runner/session.py` — Added `parse_skill_file_entries()` pure helper
  and `_module_knowledge_context()` function. Server-scoped sessions now
  get a "Known issues" section with GOTCHAS/DEBUG entry titles for
  detected modules.
- `src/registry/skills.py` — Added context_files validation at load time.
  Logs warning for missing files.
- `scripts/lint_docs.py` — New `check_context_files_exist()` (7th check).
  Validates all skills' context_files reference real files.
- `skills/idea-generation/SKILL.md` — Removed nonexistent
  `projects/ideas/README.md` from context_files (caught by new lint check).

**Why**: Module skill files were empty stubs — zero institutional knowledge
visible to sessions. Now seeded from Troubleshooting.md + CHANGELOG
gotchas, auto-injected into directives, and context_files are validated.

**Side effects**: Server-scoped sessions mentioning specific modules now
get a slightly larger directive (entry titles only — compact). New lint
check (7th) runs on every lint invocation.

## 2026-04-19 — Tool-use audit in code review (Rec 15)

**Files changed**:
- `src/runner/review.py` — Added `_summarize_tool_usage()` helper that
  reads the parent job's audit log and produces a compact tool-count
  summary (Read: N files, Edit: N, etc.). `run_code_review()` now appends
  this summary to the review prompt. Updated `REVIEW_SYSTEM_PROMPT` to
  include an "Approach" section in the output format.
- `skills/code-review/SKILL.md` — Added Approach section to output format
  description.

**Why**: Per § 7 Rec 15. Code review previously only evaluated the diff.
Now the reviewer also sees how the session arrived at the diff (tool usage
patterns), enabling process quality feedback.

**Side effects**: Every code review that has a parent job ID now reads
the parent's audit log (~1ms overhead). The review prompt is slightly
longer.

## 2026-04-19 — Audit log index (Rec 9)

**Files changed**:
- `src/runner/audit_index.py` (NEW) — `rebuild_index()` builds
  `volumes/audit_log/INDEX.jsonl` from all JSONL audit logs. One line
  per job: `{job_id, skill, model, effort, status, error_first_line,
  keywords}`. `search_index()` queries the index by skill, status, or
  keyword. `build_index_entry()` and `_extract_keywords()` are pure
  and unit-tested.
- `skills/self-diagnose/SKILL.md` — Added audit log index search step
  before drilling into individual logs.
- `skills/server-upkeep/SKILL.md` — Added step 2b to rebuild the index
  during daily upkeep.

**Why**: Per § 7 Rec 9. Self-diagnose previously had to scan individual
audit logs to find similar past failures. The index provides O(1) lookup
by skill/status/keyword.

**Side effects**: `volumes/audit_log/INDEX.jsonl` is created/overwritten
on each rebuild. Not append-only — safe to delete and rebuild.

## 2026-04-19 — Context budget accounting (Rec 8)

**Files changed**:
- `src/runner/session.py` — Added `estimate_context_tokens()`,
  `context_budget_fraction()` pure helpers and `_MODEL_BUDGETS` map.
  `run_session()` now emits `context_budget_used` audit log event with
  estimated tokens, model budget, and fraction before starting the session.
- `src/runner/retrospective.py` — Added `ContextBudget` dataclass,
  `parse_budget_events()` and `aggregate_context_budgets()` pure helpers,
  and `context_budget_report()` function. Walks audit logs for
  `context_budget_used` events and aggregates by skill.
- `src/audit_log.py` — Documented `context_budget_used` event kind.

**Why**: Per § 7 Rec 8. Skills with oversized static context waste tokens
on every run. Now measurable: review-and-improve flags skills using >30%
of the model's context window.

**Side effects**: Every job now emits one extra audit log event
(`context_budget_used`) before the session starts. ~1ms overhead.

## 2026-04-19 — Stale-context warnings in retrospective (Rec 7)

**Files changed**:
- `src/runner/retrospective.py` — Added `StaleContextWarning` dataclass,
  `_newest_mtime()`, `_days_since()` pure helpers, and
  `stale_context_warnings()` function. Checks for CONTEXT.md files >30d
  older than newest source, and CHANGELOG.md files with no updates in 60d
  despite git commits. Synchronous (filesystem + git only).

**Why**: Per § 7 Rec 7. Documentation decay was invisible — now it's a
measurable finding that review-and-improve can propose to fix.

**Side effects**: None on runner execution. Called by review-and-improve
skill during retrospective analysis.

## 2026-04-19 — Project-level protocol reference in directive (Rec 6)

**Files changed**:
- `src/runner/session.py` — `_build_server_directive()` now references
  `.context/PROJECT_PROTOCOL.md` for project-scoped sessions and directs
  to project's `skills/GOTCHAS.md` for non-obvious learnings.

**Why**: Per § 7 Rec 6. Project-scoped sessions lacked a protocol document
analogous to PROTOCOL.md. The new PROJECT_PROTOCOL.md gives them write-back
rules, and the directive now points there.

**Side effects**: None on runner execution — just adds a line to the
project-scoped directive string.

## 2026-04-19 — Graph-walked context injection + import lint (Rec 4)

**Files changed**:
- `src/context/module_graph.py` (NEW) — Pure functions: `parse_module_graph()`
  parses the SYSTEM.md markdown table into a forward dependency map,
  `reverse_graph()` builds the reverse map, `extract_imports()` AST-parses
  Python source for `from src.*` imports, `detect_modules_in_text()` finds
  module references in free-form text, `module_path_to_shorthand()` converts
  file paths to graph shorthands.
- `src/runner/session.py` — `_build_server_directive()` now accepts
  `job_description` and calls `_module_dependency_context()` for server-scoped
  sessions. When the description mentions known modules, the directive includes
  "Module dependencies" section listing dependents and advising to read their
  CONTEXT.md before API changes.
- `scripts/lint_docs.py` — New `check_module_graph_imports()` lint check.
  AST-parses every Python file under `src/`, compares actual imports against
  declared dependencies in SYSTEM.md module graph. Warns on undeclared deps.
- `.context/SYSTEM.md` — Fixed undeclared deps for runner.main, runner.session,
  gateway.web, gateway.telegram_bot, runner.retrospective. Added
  context.module_graph row.
- `tests/test_module_graph.py` (NEW, 23 tests) — Pure-function coverage for
  graph parser, import extractor, module detector, path shorthand conversion.
- `tests/test_doc_lint.py` — Added `test_module_graph_imports` test.

**Why**: Per § 7 Rec 4. Sessions modifying server modules now get automatic
dependency context, and the lint check catches undeclared cross-module imports
before they accumulate.

**Side effects**: The new lint check (6th) runs on every `python3 scripts/lint_docs.py`
invocation. It caught 12 real undeclared deps from prior phases, now fixed.

## 2026-04-19 — Added context consumption rollup (Rec 2)

**Files changed**:
- `src/runner/retrospective.py` — Added `ContextUsage` dataclass,
  `parse_read_events()` pure helper, `_normalize_path()` pure helper,
  and `context_consumption()` async rollup function. Walks audit log
  JSONL files for Read tool_use events, joins against jobs table for
  skill/status/rating, returns per-(skill, file_path) usage metrics.

**Why**: Teaches `review-and-improve` what files are actually useful to
skills by measuring actual Read tool usage from audit logs. Files read in
>50% of a skill's runs should be in `context_files`; files read <10% can
be removed. Per § 7 Rec 2.

**Side effects**: None on runner execution — this module is imported by
the gateway web route and by the review-and-improve skill.

## 2026-04-18 — Added proposals.py helper module (Rec 10)

**Files changed**:
- `src/runner/proposals.py` (NEW, ~230 lines) — pure helpers + async DB
  ops for proposal tracking table. Public interface: `extract_proposal_id`,
  `is_valid_change_type`, `is_valid_outcome`, `format_proposal_line`,
  `find_recent_duplicate`, `insert_proposal`, `mark_proposal_merged`,
  `list_pending_proposals`, `list_recent_proposals`, `get_proposal_by_id_prefix`.

**Why**: Supports the `/proposals` Telegram command + dedup/merge-stamping
in the review-and-improve and server-patch skills per § 7 Rec 10.

**Side effects**: None on runner execution — this module is imported lazily
by the Telegram handler and by skills that need it.

## 2026-04-18 — Added learning extractor post-session hook (Rec 1)

**Files changed**:
- `src/runner/learning.py` (NEW, ~280 lines) — Haiku classifier that runs after each successful non-chat, non-internal job. Pure helpers (`should_extract`, `parse_learning_response`, `format_audit_excerpt`, `list_installed_modules`) + async `extract_learning` (one-turn Haiku call, returns `LearningProposal`) + `maybe_extract_and_enqueue` (full pipeline entry point).
- `src/runner/main.py` — Added import of `maybe_extract_and_enqueue`. Added hook call in `_process_job` after writeback verification. Conditions: skip chat kind, skip any kind starting with `_`, skip internal skills (resolved_skill starts with `_`), skip escalation retries (`escalated_from` flag in payload).
- `skills/_learning_apply/SKILL.md` (NEW, internal skill) — Sonnet 4.6 / low, leading-underscore kind, takes payload from the classifier and appends to `.context/modules/<module>/skills/<CATEGORY>.md` using the `APPEND_ENTRIES_BELOW` marker. Dedup check by title grep before append. Commits locally; does not push.
- `.context/SKILLS_REGISTRY.md` — registered `_learning_apply` as internal skill.
- `.context/SYSTEM.md` — added `src/runner/learning.py` row to module graph.
- `.context/modules/runner/CONTEXT.md` — added `learning.py` to Paths, documented `maybe_extract_and_enqueue` in public interface.
- `tests/test_learning.py` (NEW) — 4 test classes / 27 pure-function tests covering should_extract, parse_learning_response, format_audit_excerpt, list_installed_modules.

**Why**: Closes the F1 feedback loop per `docs/EVALUATION_2026-04-18.md` § 7 Rec 1. Before this, institutional learnings were supposed to be written back by the primary session per PROTOCOL.md, but in practice only 1 PATTERNS.md existed across 5 modules. The classifier runs on every code-touching job and proposes a learning when appropriate; the internal skill applies it. Token-efficient: the `should_extract` gate avoids Haiku calls on read-only/chat jobs.

**Side effects**: Every successful non-chat, non-internal, non-escalation job now runs a ~5s Haiku classification after the existing writeback + review hooks. Classifier failures are logged and swallowed (non-fatal for the primary job). New audit log event kinds: `learning_extraction_done`, `learning_apply_enqueued`. New `_learning_apply` child job kind can appear in the queue.

**Gotchas discovered**: None yet; will accumulate as the loop runs in production. Likely candidates: classifier over-proposing (too lax) or under-proposing (too strict), `_learning_apply` concurrent-write conflicts on the same file.

## 2026-04-18 — Seeded skills/ subdirectory per Rec 3 (§ 7 Seed module skills/ dirs)

**Change**: This module now has `.context/modules/runner/skills/` containing stub `GOTCHAS.md`, `PATTERNS.md`, and `DEBUG.md` files. Stubs were created via `scripts/seed-module-skills.sh`; no source code modified.

**Why**: PROTOCOL.md directs sessions to append learnings to these files, but four of five modules had no skills/ directory at all, discouraging write-backs. Creating the directories with format-header stubs removes the friction and gives future sessions a template to append to. See `docs/EVALUATION_2026-04-18.md` § 7 Rec 3.

**Side effects**: None on module behavior. New lint check `check_module_skills_dirs` in `scripts/lint_docs.py` verifies these files continue to exist.


<!-- Newest entries at top. Every session that modifies src/runner/ appends here. -->

## 2026-04-18 — Context-aware SERVER_DIRECTIVE + context_files frontmatter

**Files changed**:
- `src/runner/session.py` — Replaced static `SERVER_DIRECTIVE` string with `_build_server_directive(skill_cfg, cwd)` function. Three code paths: chat (minimal), project-scoped (targeted), server-scoped (full). Appends `context_files` reading list when declared in skill frontmatter.
- `src/registry/skills.py` — Added `context_files: list[str]` field to `SkillConfig` dataclass. Parsed from SKILL.md frontmatter in `load()`.

**Why**: Reduces wasted tokens. Chat sessions no longer get instructions to read SYSTEM.md. Project-scoped sessions get targeted instructions about the project's CLAUDE.md. Skills can declare which docs their sessions should read first.

## 2026-04-17 — Phase 6: research-deep, idea-generation, project-update-poll, restore skills

**Files created**:
- `skills/research-deep/SKILL.md` — Deep-dive research skill. Opus 4.7 / high, 80 max turns, escalation to xhigh on failure. 10-20 sources, 2000-5000 words, mandatory "Where sources disagree" and "How I researched this" sections. Output to `projects/research-deep/`.
- `skills/idea-generation/SKILL.md` — Idea generation skill. Sonnet 4.6 / medium, 20 max turns. Generates 3-5 novel ideas, deduped against `projects/ideas/history.jsonl`. Supports actionable/speculative/technical-only/product-only styles.
- `skills/project-update-poll/SKILL.md` — Project update polling skill. Haiku 4.5 / low, 4 max turns. Runs a project's `on_update` command from manifest.yml. One retry on failure, no diagnosis.
- `skills/restore/SKILL.md` — Restore from backup skill. Sonnet 4.6 / medium, 30 max turns. Destructive: requires "RESTORE <date>" confirmation, second confirmation for >30 day old backups. Stops services, restores pg_dump + audit logs, restarts.

**Files changed**:
- `src/runner/router.py` — Added routing rule for `restore` skill (pattern: `\brestore\b`). Verified `research-deep` and `idea-generation` rules already exist; no duplicates added.
- `.context/SKILLS_REGISTRY.md` — Moved `research-deep`, `idea-generation`, `project-update-poll`, `restore` from Planned to Installed.

**Scaffolded**:
- `projects/ideas/` — Private ideas storage with CLAUDE.md, .context/CONTEXT.md, .context/CHANGELOG.md, empty history.jsonl. Not git-initialized (skill bootstraps on first run).

**Why**: Phase 6 adds four utility skills. `research-deep` is the heavyweight research path (vs `research-report`'s standard path). `idea-generation` provides creative brainstorming with dedup. `project-update-poll` enables cheap scheduled polling of project update commands. `restore` is the disaster recovery path paired with the `backup` script (Phase 5 planned).

**Side effects**: The `restore` router rule is broad (`\brestore\b`) — any message containing "restore" will route there. This is intentional since restore is a rare, deliberate action. `project-update-poll` has no router rule (triggered only via schedules/payload).

## 2026-04-17 — Phase 5: server-upkeep, server-patch, review-and-improve skills

**Files created**:
- `skills/server-upkeep/SKILL.md` — Daily health audit skill. Sonnet 4.6 / low, 20 max turns. Rotates logs, VACUUMs DB, checks tunnel/project/process health, reports anomalies only (outputs SILENT when all quiet, always reports on Sundays). Tags: scheduled, operations.
- `skills/server-patch/SKILL.md` — Server code modification skill. Opus 4.7 / xhigh, 60 max turns. Always PR-gated via `gh pr create`, never auto-merged. Post-review trigger always (Opus 4.7 / high reviewer). Commit metadata includes Requires-migration, Requires-env-change, Rollback. Tags: server, maintenance, manual-merge-required.
- `skills/review-and-improve/SKILL.md` — Retrospective auditor skill. Opus 4.7 / max, plan mode, 30 max turns. Queries job success rates, ratings, escalation/writeback frequency, code-review outcomes. Proposes structured changes for skills with >25% failure, <3 avg rating, frequent escalation, or 0 runs in 30 days. Dispatches server-patch via enqueue_job MCP. Tags: retrospective, needs-dispatch-mcp.

**Files changed**:
- `.context/SKILLS_REGISTRY.md` — Moved `server-upkeep`, `server-patch`, `review-and-improve` from Planned to Installed.

**Why**: Phase 5 completes the operational autonomy layer. `server-upkeep` handles daily housekeeping without human attention (SILENT output suppresses DMs). `server-patch` is the only path for modifying server code, enforcing branch + PR + human-merge. `review-and-improve` closes the feedback loop by analyzing job data and dispatching improvement patches.

**Side effects**: No `src/` files modified. These are skill definitions only — the runner already supports all required features (post_review, escalation, MCP dispatch, SILENT output).

## 2026-04-17 — Phase 4F: self-diagnose skill + event trigger loop

**Files created**:
- `skills/self-diagnose/SKILL.md` — Diagnose failures with risk classification. Auto-applies very-low/low risk fixes, delegates medium to app-patch (direct push) or server-patch (Phase 5, manual only for now), outputs diagnosis only for high risk. Tags: needs-projects-mcp, needs-dispatch-mcp.
- `src/runner/events.py` — Fourth async task. Polls every 60s. Rule 1: skill failed >= 2x in 10 min → enqueue self-diagnose. Rule 2: project unhealthy > 20 min → enqueue self-diagnose. Deduplication via recent job query.
- `tests/test_events.py` — 14 pure-function tests for `_should_trigger_skill_diagnose` and `_should_trigger_project_diagnose`.

**Files changed**:
- `src/runner/main.py` — Added `event_loop` as fourth async task in `main()`.

**Why**: Automated failure recovery. The event loop detects repeated failures and unhealthy projects, then enqueues self-diagnose jobs without user intervention. Per user decision: app-patch pushes freely, server code changes require Telegram Y/N (delegated to server-patch when it ships in Phase 5).

## 2026-04-17 — Phase 4G: project-evaluate skill + router rule

**Agent task**: Build Module G of Phase 4 -- the `project-evaluate` skill that automates producing manifest.yml + .context/CONTEXT.md for existing projects.

**Files created**:
- `skills/project-evaluate/SKILL.md` -- Skill definition with full procedure for analyzing a project codebase, generating manifest.yml, .context/CONTEXT.md, CLAUDE.md, and .context/CHANGELOG.md. Includes non-destructive overwrite checks via AskUserQuestion.

**Files changed**:
- `src/runner/router.py` -- Added routing rule for `project-evaluate` skill. Pattern matches "evaluate/assess/document/onboard project/app". Placed before the "new project" rules so "evaluate project X" does not fall through.
- `.context/SKILLS_REGISTRY.md` -- Added `project-evaluate` to the Installed table.

**Why**: Projects in `projects/` need standardized documentation (manifest.yml, .context/CONTEXT.md) to be registerable for hosting via `register-project.sh`. This skill automates producing that documentation by analyzing the project's codebase.

**Side effects**: The new router rule introduces four new trigger words (evaluate, assess, document, onboard) followed by "project" or "app". These are distinct from existing triggers and placed before the "new project" rules to avoid conflicts.

## 2026-04-17 — Phase 4E: new-skill meta-skill

**Agent task**: Create Module E of Phase 4 -- the `new-skill` meta-skill that authors new skills from natural-language descriptions.

**Files created**:
- `skills/new-skill/SKILL.md` -- Meta-skill system prompt. Opus 4.7 / high, acceptEdits mode, 30 max turns, post_review always. 10-step procedure covering analysis, overlap check, structural reference, drafting, support files, router rules, registry updates, scheduling, commit, and summary.

**Files changed**:
- `.context/SKILLS_REGISTRY.md` -- Moved `new-skill` from Planned to Installed table.

**Why**: `new-skill` is the self-expansion mechanism: once installed, the server can author additional skills from plain-language descriptions without manual SKILL.md authoring. This completes the meta-skill layer of Phase 4.

**Side effects**: None. No `src/` files were modified -- the router already had `new-skill` rules from a prior session (lines 42-43 in router.py). The skill is purely additive.

## 2026-04-17 — Phase 4D: app-patch skill

**Files created**: `skills/app-patch/SKILL.md`
**Why**: Lets the system patch existing projects via `/task fix <project>: <issue>`. Direct commit + push to main per user decision (no PR gate for project repos). Code review sub-agent runs after every patch via `post_review: { trigger: always }`.

## 2026-04-17 — Phase 4B: in-process MCP servers for projects + dispatch

**Agent task**: Build Module B of Phase 4 — two in-process MCP servers that give skills structured access to the projects registry and job dispatch.

**Files created**:
- `src/runner/mcp_projects.py` — MCP server with four tools: `list_projects`, `get_project`, `read_project_logs`, `restart_project`. Uses `create_sdk_mcp_server()` from the Claude Agent SDK. Pure helpers `_format_project()` and `_read_log_tail()` are separated for testability.
- `src/runner/mcp_dispatch.py` — MCP server with one tool: `enqueue_job`. Wraps `src.gateway.jobs.enqueue_job()` with `created_by="dispatch-mcp"`. Pure helper `_validate_enqueue_args()` separated for testability.
- `tests/test_mcp_tools.py` — 21 pure-function tests covering `_format_project`, `_read_log_tail`, and `_validate_enqueue_args`. No DB, no Redis, no SDK.

**Files changed**:
- `src/runner/session.py` — added MCP server injection in `_build_options()`. Skills opt in via `_NEEDS_PROJECTS_MCP` / `_NEEDS_DISPATCH_MCP` name sets (module-level) or `"needs-projects-mcp"` / `"needs-dispatch-mcp"` tags in SKILL.md frontmatter. MCP servers are passed as a dict to `ClaudeAgentOptions(mcp_servers=...)`.

**Why**: Skills like `self-diagnose` and `review-and-improve` need structured project introspection and the ability to spawn child jobs. MCP servers provide this via typed tool calls rather than ad-hoc Bash/file reads, making skill prompts simpler and more reliable.

**Side effects**:
- Skills in the opt-in sets now receive extra MCP tools in their sessions. These tools are additive and do not affect existing tool access.
- The `enqueue_job` MCP tool creates jobs with `created_by="dispatch-mcp"` for audit trail visibility.

**Gotchas discovered**:
- `ClaudeAgentOptions.mcp_servers` is a `dict[str, McpSdkServerConfig]`, not a list. The server name key must match the name passed to `create_sdk_mcp_server()`.
- The `@tool` decorator's function receives a single `args: dict` parameter with all input fields, not keyword arguments.

## 2026-04-17 — Phase 4 Module A: Code review sub-agent infrastructure

**Agent task**: Add synchronous code-review sub-agent that evaluates diffs after code-touching sessions.

**Files created**:
- `src/runner/review.py` — `run_code_review()` spins up an Opus 4.7 / plan-mode session to review a diff. `_parse_outcome()` extracts LGTM/CHANGES/BLOCKER from the reviewer's first line. `get_git_diff()` helper for extracting diffs. Diff truncated at 50K chars.
- `skills/code-review/SKILL.md` — User-triggerable code review. Plan mode, read-only tools, max 5 turns.
- `tests/test_review.py` — 16 pure-function tests for `_parse_outcome` and `get_git_diff`.

**Files changed**:
- `src/runner/main.py` — Added `_maybe_review()` post-session hook. Runs after successful sessions for skills with `post_review.trigger` set in frontmatter. Gets git diff, runs review, stamps `review_outcome` on the job. If BLOCKER, changes job status to `awaiting_user`.
- `src/runner/router.py` — Added routing rule for `code-review` skill.

**Why**: The code-review sub-agent is the quality gate for all Phase 4 coding skills (`new-project`, `app-patch`, `new-skill`). Skills opt in via `post_review: { trigger: always }` in their frontmatter.

**Side effects**: No existing skills have `post_review` set, so this hook is inert until Phase 4 skills are added. Zero impact on existing behavior.

**Design decisions**:
- Synchronous (blocks parent job), not async child job — because the parent's final status depends on the review outcome.
- Skills must opt in via `post_review.trigger: always` (default is `never`). Keeps the review surface explicit.
- Escalated jobs skip review (prevents reviewing the same diff twice after a failure retry).

## 2026-04-17 — Fix: audit_log.append `kind` argument collision

**Agent task**: Diagnose why all jobs fail immediately with `TypeError: append() got multiple values for argument 'kind'`.

**Files changed**:
- `src/runner/session.py` — renamed `kind=job.kind` keyword argument to `job_kind=job.kind` in the `audit_log.append(job_id, "job_started", ...)` call at line 182. The positional `"job_started"` already fills the `kind` parameter in `audit_log.append(job_id, kind, **fields)`, so passing `kind=` as a keyword collided.

**Why**: This bug broke INV-2 (every job must write `job_started` + terminal event). The crash happened before the audit log file was created, so `volumes/audit_log/` was empty — no jobs could run at all.

**Side effects**: The audit log field name for the job's kind changes from `kind` to `job_kind` in `job_started` events. No downstream code reads this field yet, so no migration needed.

**Gotchas discovered**:
- `audit_log.append(job_id, kind, **fields)` uses `kind` as a positional param name. Never pass `kind=` as a keyword in `**fields` — it collides. Use `job_kind` instead.

## 2026-04-17 — Phase 2: write-back verification + failure escalation + tests

**Agent task**: Complete Phase 2 — ship the `research-report` skill end-to-end with write-back enforcement and model escalation on failure.

**Files changed**:
- `src/runner/writeback.py` (new) — pure-function classifier: given a cwd, returns (needs_writeback, list_of_modified_files). Uses `git status --porcelain --untracked-files=all` so individual files are visible, not just parent directories.
- `src/runner/main.py` — added `_verify_writeback()` called after every successful job (except `chat` and `_writeback` itself); if the session left non-doc changes without touching a CHANGELOG, enqueues a child `_writeback` job linked via `parent_job_id`. Added `_maybe_escalate()` called after job failure: if the skill's frontmatter declares `escalation.on_failure`, enqueues a retry with the escalated model/effort (guarded by `escalated_from` payload to prevent loops).
- `src/runner/session.py` — fixed skill-name resolution: leading underscores preserved (`_writeback` stays `_writeback`), other underscores still become dashes (`research_report` → `research-report`).
- `src/runner/router.py` — reordered rules: `new-skill` pattern now matches before `research-report` so "new skill: daily BTC summary" doesn't route to research via the "summary" keyword.
- `tests/test_pure_functions.py` (new) — 52 tests covering router keyword matching, telegram flag parsing (model aliases, effort/permission validation, unknown flags), and writeback classification (doc vs non-doc paths, git status with and without changelog updates).

**Why**: The write-back protocol is the core mechanism that makes "pick up a project 3 months later" work — but only if it's enforced. Primary sessions may skip it under Opus 4.7's stricter instruction following or because a skill author forgot to include it. The `_verify_writeback` hook spawns a cheap Sonnet-low follow-up exclusively for the CHANGELOG update. Similarly, `on_failure` escalation catches the "Sonnet tried and couldn't; Opus 4.7 / high should" case without over-provisioning on every job.

**Side effects**:
- Every successful non-`chat`, non-`_writeback` job now incurs a ~1-second git-status check. Negligible.
- Failed jobs with a skill that declares `on_failure` will retry automatically — doubling cost for persistent failures. This is the intended trade: one extra escalated attempt is cheaper than the user re-running with flags manually.

**Gotchas discovered**:
- `git status --porcelain` without `--untracked-files=all` collapses new directories to their parent name (`src/` instead of `src/thing.py`). Writeback classification needs file-level visibility.
- Router rule order matters: earlier rules win. When adding a new rule, place it above anything it might conflict with.
- `kind.replace("_", "-")` converts `_writeback` to `-writeback` (bad). Internal skills (leading underscore) need to be preserved as-is.
- Top-level markdown files (README.md, MISSION.md, SERVER.md, CLAUDE.md) must be classified as docs — otherwise editing them would trigger false writeback spawns.

## 2026-04-16 — Initial bootstrap (Phase 1)

**Agent task**: Create the runner module from scratch.

**Files created**:
- `src/runner/main.py` — entry point with 3 async loops (job, scheduler, cancel)
- `src/runner/session.py` — one ClaudeSDKClient session per job; streams to audit log
- `src/runner/router.py` — rule-based keyword → skill matcher (no LLM)
- `src/runner/quota.py` — subscription-quota detection and pause/resume

**Why**: Replace the old `worker.py` (94KB, 9 loops, monolithic) with a thin,
skill-driven runner that delegates all agent logic to the Claude Agent SDK.

**Side effects**: None — this is a new module.

**Gotchas discovered**:
- `update` from SQLAlchemy collides with Telegram's `Update` type. Import as
  `sql_update` in files that handle telegram updates.
- The SDK's Python hooks are partially shell-only in the current version; we
  capture audit events via message-iteration instead, which is robust across versions.
- `ANTHROPIC_API_KEY` silently flips the SDK to API billing — the runner's startup
  check aborts if it's set.
