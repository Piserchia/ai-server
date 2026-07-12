# Runner module

**Paths:** `src/runner/main.py`, `src/runner/session.py`, `src/runner/router.py`, `src/runner/quota.py`, `src/runner/writeback.py`, `src/runner/review.py`, `src/runner/events.py`, `src/runner/mcp_projects.py`, `src/runner/mcp_dispatch.py`, `src/runner/retention.py`, `src/runner/retrospective.py`, `src/runner/learning.py`, `src/runner/proposals.py`, `src/runner/audit_index.py`, `src/runner/reconcile.py`, `src/runner/workspaces.py`, `src/runner/executors.py`, `src/runner/plans.py`, `src/runner/llm_router.py`

## Purpose

The runner is the execution engine. It pops jobs off `jobs:queue`, resolves each
to a skill and a Claude Agent SDK session, streams the session's messages to the
audit log, and updates the Job row with the result.

Four async tasks running in one process:
1. `_job_loop` — BLPOPs from `jobs:queue`, respects `quota.is_paused()`, runs sessions under a semaphore gated by `MAX_CONCURRENT_JOBS`.
2. `_scheduler_loop` — every 30s, picks schedules with `next_run_at <= now` and enqueues jobs from their templates.
3. `_cancel_listener` — subscribes to `jobs:cancel` channel, calls `session.interrupt(job_id)` for matches.
4. `event_loop` — every 60s, checks skill-failure + project-unhealthy + idle-queue rules, auto-enqueues self-diagnose or review-and-improve.

## Public interface

- `src.runner.main.main()` — entry point (via `python -m src.runner.main`).
- `src.runner.session.run_session(job) -> dict` — runs one job; raises `QuotaExhausted` or generic `Exception` on failure.
- `src.runner.session.interrupt(job_id)` — signal a running session to stop.
- `src.runner.quota.is_paused()` / `pause_queue(...)` / `clear()` — queue pause state.
- `src.runner.router.route(description)` — rule-based skill matcher; returns a skill name or `None`.
- `src.runner.mcp_projects.create_server()` — returns an `McpSdkServerConfig` for the projects MCP server (tools: `list_projects`, `get_project`, `read_project_logs`, `restart_project`).
- `src.runner.mcp_dispatch.create_server()` — returns an `McpSdkServerConfig` for the dispatch MCP server (tool: `enqueue_job`).
- `review.run_code_review()` — sub-agent that evaluates diffs post-session for code-touching skills.
- `events.event_loop()` — rules engine that checks for repeated failures and unhealthy projects, auto-enqueuing follow-up jobs.
- `retention.rotate_audit_logs()` — compresses and archives old JSONL audit log files (called by server-upkeep skill).
- `retrospective.skill_performance()` — rollup queries for the auto-tuning retrospective (consumed by review-and-improve skill).
- `retrospective.context_consumption(since)` — walks audit logs for Read tool_use events, groups by (skill, file_path), joins jobs for success_rate + avg_rating. Returns `list[ContextUsage]`. Used by review-and-improve to propose context_files additions/removals.
- `retrospective.parse_read_events(lines)` — pure helper: parses JSONL lines, returns deduplicated `(job_id, file_path)` pairs for Read events.
- `retrospective.stale_context_warnings()` — synchronous. Checks for CONTEXT.md files >30d older than newest source file, and CHANGELOG.md with no updates in 60d despite git commits. Returns `list[StaleContextWarning]`.
- `retrospective.context_budget_report(since)` — synchronous. Walks audit logs for `context_budget_used` events, aggregates by skill. Returns `list[ContextBudget]` with avg/max fraction of model budget used by static context.
- `session.format_task_turns(turns)` — pure helper: formats task turn dicts into a compact conversation summary for system prompt injection.
- `session.build_task_context(turns_data, task_id)` — pure: formats pre-fetched turns into the "Task conversation" markdown section. Turns are fetched async in `run_session` (replaced the old nested-event-loop `_build_task_context(task_id)` hack; load failures are now audited as `task_context_load_failed` instead of silently dropping the conversation).
- `workspaces.resolve_isolation(skill_iso, payload_iso, container_available, needs_mcp)` — pure: effective isolation tier (`none | workspace | container | host`). Payload > frontmatter > none; `container` downgrades to `workspace` without a runtime/token or when the skill needs in-process MCP.
- `workspaces.create_workspace(job_id, canonical, base_dir)` — per-job git clone under `volumes/workspaces/<job8>-<name>/` with origin re-pointed at the canonical's real remote; `sync_canonical(ws)` fast-forwards the canonical after the session pushes; `cleanup_workspace(ws, keep=)` removes it (failed jobs keep theirs for debugging); `prune_old_workspaces(base_dir, max_age_days)` is called by server-upkeep.
- `executors.run_in_container(...)` — `claude -p --output-format stream-json` in a container (docker CLI; colima/OrbStack/Docker Desktop). Emits the SAME audit events as the in-process lane (parity contract, tested in `tests/test_executors.py`). `container_runtime_available()` gates it; `interrupt_container(job_id)` backs /cancel; `build_container_command(...)` and `parse_stream_json_line(...)` are pure and tested. Containers get `CLAUDE_CODE_OAUTH_TOKEN` only — the executor strips `ANTHROPIC_API_KEY` (INV-3).
- `plans.validate_plan(plan, known_kinds)` / `plans.topo_order(subtasks)` / `plans.deps_satisfied(deps, completed, escalation_map)` — pure plan/DAG helpers (P2).
- `plans.spawn_plan_jobs(task_id, plan, created_by)` — one job per subtask: roots queued, dependents `deferred` (payload.depends_on = job uuids). `promote_deferred_for(job)` queues deferred siblings whose deps completed (a completed escalation retry satisfies its failed original); `fail_dependents_of(job)` cascades terminal failures; `plan_jobs_remaining(task_id, exclude_job_id)` is the DAG drain check.
- `llm_router.llm_route(description)` — Haiku one-turn routing fallback when regex rules miss; returns `(skill|""|"plan", confidence)`; `parse_route_response` is pure, fail-open to generic. Every routing decision is audited (`routing_decision`: method=rule|llm|fallback).
- `session.extract_text_events(final_text)` — pure: parses `TASK_COMPLETE:` / `TASK_QUESTION:` / `EVAL_PASS:` / `EVAL_FAIL:` line markers and the `<<<TASK_PLAN … TASK_PLAN>>>` JSON block from a session's final text; the runner synthesizes the audit events (executor-agnostic, race-free — preferred over sessions appending to the audit log themselves).
- `session.parse_skill_file_entries(text)` — pure helper: parses module skills file (GOTCHAS.md, DEBUG.md) into entry titles after the APPEND_ENTRIES_BELOW marker.
- `session.estimate_context_tokens(text)` / `session.context_budget_fraction(prompt, model)` — pure helpers for token estimation (~4 chars/token) and budget fraction calculation.
- `audit_index.rebuild_index(audit_log_dir)` — builds `INDEX.jsonl` from all audit logs. One line per job with skill, model, status, error, keywords. Called by server-upkeep.
- `audit_index.search_index(index_path, skill, status, keyword)` — search the index for matching jobs. Used by self-diagnose to find similar past failures.
- `learning.maybe_extract_and_enqueue(parent_job_id, summary)` — post-session hook. Reads the audit log, gates on whether the job modified files (Write/Edit tool_use), runs a one-turn Haiku classifier that may emit a `LearningProposal`, and enqueues a `_learning_apply` internal child job to append the learning to `.context/modules/<module>/skills/<CATEGORY>.md`. Never raises. Called from `main._process_job` after writeback verification.
- `proposals.extract_proposal_id(text)` — parse `Proposal-ID: <uuid>` marker (pure).
- `proposals.find_recent_duplicate(target_file, change_type, lookback_days=30)` — dedup check for review-and-improve.
- `proposals.insert_proposal(...)` / `proposals.mark_proposal_merged(proposal_id, pr_url)` — lifecycle mutations.
- `proposals.list_pending_proposals(...)` / `proposals.list_recent_proposals(...)` / `proposals.get_proposal_by_id_prefix(...)` — query helpers for the /proposals command.
- `reconcile.reconcile_orphaned_jobs() -> int` — startup hook (called from `main.main()` before the loops). Brings every job left in `running` by a previous process to a terminal state: synthesises a `job_failed` event (`error_category='orphaned'`) + fails the row when the audit log has no terminal event, else adopts the existing terminal outcome without writing a duplicate (idempotent across restarts). Updates the incremental audit index for each. Returns the count.
- `reconcile.orphaned_job_ids(rows)` — pure helper: given `(job_id, status)` pairs, returns ids stranded in `running`.

## Dependencies

- `src.config`, `src.db`, `src.models`, `src.audit_log`
- `src.registry.skills` — frontmatter parser for SKILL.md
- `claude_agent_sdk` — the brain

## Configuration

All via `src.config.settings`:
- `MAX_CONCURRENT_JOBS` (default 4 since P1 — workspace isolation removed the shared-checkout collision risk)
- `SESSION_TIMEOUT_SECONDS` (default 1800)
- `DEFAULT_MODEL` (global fallback when skill doesn't specify)
- `QUOTA_PAUSE_MINUTES` (default 60 when reset time is unknown)
- `CONTAINER_RUNTIME` / `AGENT_IMAGE` / `CONTAINER_MEMORY` / `CONTAINER_CPUS` / `CLAUDE_CODE_OAUTH_TOKEN` (container lane; empty runtime = disabled → container-tier skills run as workspace. See `docs/CONTAINERS.md`)

## Context injection

Sessions receive a context-aware server directive via `_build_server_directive()`:
- **Chat sessions**: minimal preamble (no tool use instructions)
- **Project-scoped sessions**: targeted to the project's CLAUDE.md and CONTEXT.md
- **Server-scoped sessions**: full directive pointing to SYSTEM.md and module docs

Skills can declare `context_files` in their SKILL.md frontmatter to specify which
documentation files their session should read first. These are appended to the
directive as a "Read these files first" list. This reduces token waste by giving
sessions exactly the context they need.

MCP servers are injected based on skill name (`_NEEDS_PROJECTS_MCP`,
`_NEEDS_DISPATCH_MCP` sets) or frontmatter tags (`needs-projects-mcp`,
`needs-dispatch-mcp`).

## Auth

Subscription only. The runner calls `_check_subscription_auth()` on startup and
refuses to start if `ANTHROPIC_API_KEY` is set or `claude` CLI is missing.

## Testing

- `tests/test_pure_functions.py` — router, flag parser, writeback classifier (Phase 2).
- `tests/test_mcp_tools.py` — pure-function tests for MCP tool helpers: `_format_project`, `_read_log_tail`, `_validate_enqueue_args` (Phase 4B). No DB/Redis/SDK. (21 tests)
- `test_review.py` — code-review outcome parser, reviewer prompt construction (16 tests).
- `test_events.py` — event-trigger rules: consecutive failures, healthcheck staleness, dedup guards (20 tests).
- `test_orphaned_jobs.py` — startup reconciliation: `orphaned_job_ids` filtering + orphan error message categorizes back to `orphaned` (6 tests).

## Key invariants (see `.context/SYSTEM.md` for the full list)

- INV-1: Every session has resolved model/effort/permission_mode before starting.
- INV-2: Every job writes `job_started` + exactly one terminal event. Upheld across
  crashes by `reconcile.reconcile_orphaned_jobs()` on startup, which writes the missing
  terminal `job_failed` event for jobs stranded in `running`.
- INV-8: Cancel requests honored within 2 seconds.
- INV-12: Quota exhaustion pauses queue; jobs requeued at front of queue.
- INV-15: On startup the runner reconciles orphaned `running` jobs (fail-only, no
  auto-requeue) before consuming the queue.

## Gotchas

- The semaphore is per-process. With multi-runner deployments (not Phase 1) we'd
  need a Redis-backed rate limiter instead.
- `interrupt()` races with session completion; we check `_running_sessions` map and
  return False if already gone. No error.
- `ResultMessage.usage` is best-effort — older SDK versions may not populate it.
- `ClaudeAgentOptions.mcp_servers` is a `dict[str, McpSdkServerConfig]`, not a list. The dict key is the server name used for routing.
- MCP `@tool` functions receive a single `args: dict` parameter, not keyword args. Always access fields via `args["key"]` or `args.get("key", default)`.
