# Changelog: runner

<!-- Newest entries at top. Every session that modifies src/runner/ appends here. -->

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
