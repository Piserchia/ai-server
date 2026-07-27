# SDK-native overhaul — 2026-07-27

> Phase 8. Requested as: "overhaul the setup — it depends on executing claude
> commands via CLI and therefore containers; make everything run through the
> Agent SDK on subscription (absolutely no API usage), and author agents that
> way." Owner decisions (2026-07-27): hook-enforced guards replace containers;
> skills compile to SDK subagents with SKILL.md staying the source of truth;
> container artifacts deleted fully.

## Status: SHIPPED

## What the evaluation actually found

The in-process Agent SDK was **already** the primary execution lane
(`runner/session.py` → `ClaudeSDKClient`, subscription auth). The real CLI
dependencies were exactly three, plus one latent bug:

1. **Container lane** (`runner/executors.py` + `Dockerfile.agent`): `claude -p
   --output-format stream-json` inside docker for `isolation: container`
   skills. Only `server-patch` declared it, and `CONTAINER_RUNTIME` was empty
   by default — the lane silently downgraded to workspace isolation, so its
   guarantees were largely aspirational.
2. **Evals judge** (`evals/run.py`): shelled out to `claude -p --model`.
3. **Startup probe** (`runner/main.py`): `subprocess.run(["claude",
   "--version"])`.
4. **Bug — every code review was a silent no-op**: `runner/review.py` called
   `ClaudeSDKClient.process_message()`, which does not exist in the SDK; the
   blanket `except` converted the `AttributeError` into
   `changes_requested` on every run. No LGTM or BLOCKER verdict the system
   ever recorded came from an actual review.

## What changed

| Area | Before | After |
|---|---|---|
| Execution | in-process SDK **or** `claude -p` in docker | in-process SDK only (`claude-agent-sdk`, pinned `>=0.1.63,<0.2`; CLI bundled inside the package) |
| Isolation (high-risk skills) | `isolation: container` (docker; off by default) | `isolation: workspace` + **enforced PreToolUse guard hooks** (`runner/guards.py`): writes outside the clone denied, dangerous Bash denied (sudo, launchctl, keychain, force-push, kills, crontab, API-key injection, destructive ops on protected roots). Hooks fire before permission evaluation → bind under `bypassPermissions`. Denials audited as `guard_denied`. INV-17 redefined accordingly. |
| Agent authoring | SKILL.md body → system prompt only | SKILL.md additionally compiles to SDK `AgentDefinition`s: frontmatter `subagents: [code-review, ...]` gives sessions in-session Task-tool delegation (`runner/agents.py`). SKILL.md remains the single source of truth (MISSION objective I). First adopters: `server-patch`, `app-patch` (both get `code-review`). |
| Reviewer | broken (`process_message`) → always `changes_requested` | `query()` + `output_format` json_schema; verdict enum enforced by the SDK; text parsing kept as fallback |
| Router / learning classifier | JSON scraped out of prose | `output_format` structured outputs with pure validators (`route_from_structured`, `proposal_from_obj`); text parsers kept as fallback |
| Quota detection | string heuristics only | typed-first: `RateLimitEvent` → `quota.detect_from_rate_limit` (status `rejected` + unix `resets_at`); heuristic kept as fallback; every transition audited as `rate_limit_status` |
| Evals judge | `claude -p` subprocess | SDK `query()` (no argv limits, same subscription auth) |
| Startup check | `claude --version` subprocess | no-API-key assertion + SDK import + bundled/system CLI resolution |
| Error handling | in-process lane completed "successfully" on `ResultMessage.is_error` | errors with no usable output now fail the job (escalation chain applies) |
| Effort ladder | `xhigh` passed through unvalidated | normalized at the SDK boundary (`xhigh` → `max`; SDK accepts low/medium/high/max). Frontmatter/Telegram contract unchanged. |

Deleted: `src/runner/executors.py`, `tests/test_executors.py`,
`Dockerfile.agent`, container settings (`CONTAINER_RUNTIME`, `AGENT_IMAGE`,
`CONTAINER_MEMORY`, `CONTAINER_CPUS`, `CLAUDE_CODE_OAUTH_TOKEN`),
`.env.example` container block. `docs/CONTAINERS.md` reduced to a historical
stub. `isolation: container` still parses (runtime maps → workspace; lint
flags it for migration).

Added: `src/runner/guards.py`, `src/runner/agents.py`, `tests/test_guards.py`
(the INV-17 enforcement contract), `tests/test_agents.py`,
`SkillConfig.description` / `SkillConfig.subagents`, god-only-host lint
enforcement in `scripts/lint_docs.py` (INV-18 previously claimed this and the
linter didn't check it).

## Auth posture (unchanged, stated honestly)

Everything runs on the owner's Claude subscription via `claude login`
credentials; `ANTHROPIC_API_KEY` remains banned everywhere (INV-3). One
nuance worth recording: Anthropic's Agent SDK docs steer *third-party
products* toward API keys — the prohibition is on offering claude.ai login to
a product's own users. This system is single-tenant, on the owner's own
machine and subscription, driving the same logged-in Claude Code the owner
uses interactively. Removing the container lane actually simplified the auth
story: no more `claude setup-token` / `CLAUDE_CODE_OAUTH_TOKEN` handling —
host credentials only.

## What was consciously traded away

OS-level (kernel) isolation for `server-patch`. Guard hooks are policy-level:
enforced in the runner process, not escapable by prompt-talk, but not a
container boundary. Accepted because (a) single-tenant personal server,
(b) the container lane was off by default anyway, (c) workspace clones + push
gates + PR-only merges remain, and (d) the SDK's `sandbox` option (macOS
Seatbelt) is available as a follow-up if OS-level confinement is wanted —
tracked in SYSTEM.md § technical debt.

## Follow-ups (deliberate, not drift)

- **SDK 0.2.x upgrade**: PyPI is at 0.2.128; we pinned `<0.2` because the
  entire options surface here was verified against 0.1.x (0.1.81 installed).
  Upgrade in its own pass: bump pin → introspect
  (`effort/agents/hooks/sandbox/output_format/RateLimitEvent`) → pytest →
  live smoke.
- **Seatbelt sandbox per-skill** (see trade-off above).
- **Pipfile.lock refresh** beyond the SDK (April-era lock; unrelated pins).
- **Deployment/update process for sub-projects** — next conversation per the
  owner.
