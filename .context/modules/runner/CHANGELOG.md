# Changelog: runner

<!-- Newest entries at top. Every session that modifies src/runner/ appends here. -->

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
