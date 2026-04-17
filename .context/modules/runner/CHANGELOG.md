# Changelog: runner

<!-- Newest entries at top. Every session that modifies src/runner/ appends here. -->

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
