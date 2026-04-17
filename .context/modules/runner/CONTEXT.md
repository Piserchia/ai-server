# Runner module

**Paths:** `src/runner/main.py`, `src/runner/session.py`, `src/runner/router.py`, `src/runner/quota.py`

## Purpose

The runner is the execution engine. It pops jobs off `jobs:queue`, resolves each
to a skill and a Claude Agent SDK session, streams the session's messages to the
audit log, and updates the Job row with the result.

Three async tasks running in one process:
1. `_job_loop` — BLPOPs from `jobs:queue`, respects `quota.is_paused()`, runs sessions under a semaphore gated by `MAX_CONCURRENT_JOBS`.
2. `_scheduler_loop` — every 30s, picks schedules with `next_run_at <= now` and enqueues jobs from their templates.
3. `_cancel_listener` — subscribes to `jobs:cancel` channel, calls `session.interrupt(job_id)` for matches.

## Public interface

- `src.runner.main.main()` — entry point (via `python -m src.runner.main`).
- `src.runner.session.run_session(job) -> dict` — runs one job; raises `QuotaExhausted` or generic `Exception` on failure.
- `src.runner.session.interrupt(job_id)` — signal a running session to stop.
- `src.runner.quota.is_paused()` / `pause_queue(...)` / `clear()` — queue pause state.
- `src.runner.router.route(description)` — rule-based skill matcher; returns a skill name or `None`.

## Dependencies

- `src.config`, `src.db`, `src.models`, `src.audit_log`
- `src.registry.skills` — frontmatter parser for SKILL.md
- `claude_agent_sdk` — the brain

## Configuration

All via `src.config.settings`:
- `MAX_CONCURRENT_JOBS` (default 2 on Max 5x plan)
- `SESSION_TIMEOUT_SECONDS` (default 1800)
- `DEFAULT_MODEL` (global fallback when skill doesn't specify)
- `QUOTA_PAUSE_MINUTES` (default 60 when reset time is unknown)

## Auth

Subscription only. The runner calls `_check_subscription_auth()` on startup and
refuses to start if `ANTHROPIC_API_KEY` is set or `claude` CLI is missing.

## Testing

None yet (Phase 1). Phase 2 adds:
- `tests/test_router.py` — rule match/miss cases
- `tests/test_session.py` — mocked SDK
- `tests/test_quota.py` — pause/resume, ISO-parsing edge cases

## Key invariants (see `.context/SYSTEM.md` for the full list)

- INV-1: Every session has resolved model/effort/permission_mode before starting.
- INV-2: Every job writes `job_started` + exactly one terminal event.
- INV-8: Cancel requests honored within 2 seconds.
- INV-12: Quota exhaustion pauses queue; jobs requeued at front of queue.

## Gotchas

- The semaphore is per-process. With multi-runner deployments (not Phase 1) we'd
  need a Redis-backed rate limiter instead.
- `interrupt()` races with session completion; we check `_running_sessions` map and
  return False if already gone. No error.
- `ResultMessage.usage` is best-effort — older SDK versions may not populate it.
