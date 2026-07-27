# Containerized sessions — HISTORICAL (lane removed 2026-07-27)

> The `isolation: container` tier (`claude -p` inside docker, written
> 2026-07-12 as part of P1) was removed on 2026-07-27. This stub exists so
> old links resolve; the full original document and implementation live in
> git history (`git log --all -- docs/CONTAINERS.md Dockerfile.agent
> src/runner/executors.py`).

## Why it was removed

- The mission is Agent-SDK-native execution on subscription auth. The
  container lane was the system's only self-managed `claude` CLI subprocess
  path, duplicated the SDK lane's audit plumbing behind a parity contract,
  and was **disabled by default** (empty `CONTAINER_RUNTIME`) — meaning its
  only consumer (`server-patch`) silently ran with workspace isolation anyway.
- The SDK now provides the pieces the lane existed for: PreToolUse hooks
  give enforceable containment (they fire before permission evaluation, so
  they bind even under `bypassPermissions`), and the CLI ships bundled
  inside the SDK package.

## What replaced it

| Container-lane property | Replacement |
|---|---|
| Filesystem confinement to the clone | `runner/guards.py` PreToolUse hooks: writes outside the workspace denied; destructive Bash referencing protected roots denied (INV-17, `tests/test_guards.py`) |
| No service/host control from sessions | Bash denylist: `sudo`, `launchctl`, kills, crontab, keychain reads |
| `ANTHROPIC_API_KEY` stripped (INV-3) | Denylist blocks API-key injection into commands; config never carries a key |
| Separate OAuth token (`claude setup-token`) | Not needed — sessions run in-process on the host's `claude login` credentials |
| OS-level escape resistance | **Traded away** — accepted for a single-tenant personal server; the SDK's `sandbox` option (macOS Seatbelt) is the documented follow-up if OS-level confinement is wanted again (SYSTEM.md § technical debt) |

Isolation tiers today: `none | workspace | host` — see
`.context/SYSTEM.md` (INV-16..18) and `docs/SDK_MIGRATION_2026-07-27.md`.
