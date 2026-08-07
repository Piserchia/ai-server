# Autonomous Execution — closing the propose→execute loop (2026-07-31)

> **STATUS: IMPLEMENTED + DEPLOYED 2026-07-31** (single batch, four workstreams; prod 601a5cd; autopilot live).
> Owner decision (2026-07-31): human pre-merge approval is removed from the
> execution path — "agent loops perform the eval and execution"; the owner is
> notified, and can jump in, but is not a gate. Protected paths remain
> owner-approval-only. Goal anchor: **an autonomous, self-healing, self-hosted
> project factory.**

## Why (the evaluation that led here)

The 2026-07-30 live assessment concluded: the org's *sensing* half works (its
first unprompted pass found real bugs), but the *execution* half was
human-bridged. Root causes, each with same-night incident evidence:

1. `permission_mode: plan` — the only structural read-only — **blocks the
   dispatch MCP**, so no safe agent could legally cause work
   (deploy-director rounds 1–2; review-and-improve silently broken for weeks).
2. Evaluation was refusal-blind: a correct preflight refusal was scored
   EVAL_FAIL and re-spawned (wasted opus session; compliance pressure).
3. Self-healing had no circuit breaker (the ~17-job self-diagnose storm).
4. Task-less `depends_on` children stranded forever (`promote_deferred_for`
   early-return).
5. Merged ≠ deployed without a human saying "deploy".
6. If agent LGTM replaces human review, one-pass review is too thin.

## What was built

| # | Change | Where |
|---|---|---|
| 1 | **read-only + dispatch tier**: PreToolUse readonly guard profile (denies Write/Edit/NotebookEdit, mutating Bash patterns, `restart_project`; allows reads + `enqueue_job`), attached whenever `privilege_class: read-only` — every isolation tier, every permission mode. Oversight skills that dispatch (CEO, 4 managers, review-and-improve, deploy-director) run `acceptEdits` + hooks; pure reporters stay `plan`. Lint: oversight ⇒ mode ∈ {plan, acceptEdits}; dispatch-tagged read-only ⇒ acceptEdits. | `runner/guards.py`, `runner/session.py`, `scripts/lint_docs.py`, skill frontmatters — INV-20 |
| 2 | **Autonomous execution lane** (INV-4 rewritten): `server-patch`/`new-skill` merge directly on gate-green + in-session `code-review` subagent LGTM + owner DM — the pattern proven by `server-deploy`'s Class-B lane. **Protected paths never auto-merge**: `.context/PROTOCOL.md`, auth config, project/skill deletion, `runner/guards.py`, `scripts/lint_docs.py`, `MISSION.md`, ORG.md's safety principle, and the lane's own executor skills — the system cannot relax its own restraints. INV-13's post-session review stays as the independent second gate. | `skills/server-patch`, `skills/new-skill`, MISSION §M, SYSTEM.md INV-4 |
| 3 | **Refusal-aware evaluation**: a rule-grounded, evidence-backed stop is `EVAL_PASS: justified stop — <rule> — <evidence>`. Three-part test (names the constraint; blocker was real; stopping is prescribed). | `skills/_evaluate` |
| 4 | **Circuit breaker**: ≥5 same-signature failures in 10 min → Redis-keyed 30-min breaker (constants in `db.py`), event-trigger spawning paused, one bounded breaker-alert self-diagnose whose summary DMs the owner. | `runner/events.py`, `src/db.py` |
| 5 | **Deeper review gate**: `code-review` restructured to find → cross-check → adversarially-verify, with scope-honesty in the LGTM verdict. | `skills/code-review` |
| 6a | **Global deferred promotion**: task-less `depends_on` children now promote when their dependency completes (task-scoped fast path unchanged). | `runner/plans.py` |
| 6b | **Deploy autopilot**: `healthcheck-all.sh` (5-min launchd timer, zero tokens) notices a quiet (≥10 min), fast-forward pending origin/main range with no deploy in flight and dispatches `deploy-director` — which does all judgment. `DEPLOY_AUTOPILOT=0` in `.env` disables. Rate-limited 30 min. | `scripts/healthcheck-all.sh` |

## The closed loop (target state)

```
managers/CEO (read-only+dispatch, hook-enforced)
    → enqueue gated worker jobs (server_patch / new_skill / app_patch)
    → worker executes in workspace clone → in-session code-review LGTM
    → autonomous merge to origin/main + owner DM        [protected paths: PR + owner]
    → INV-13 post-session review (independent, fail-closed)
    → deploy autopilot notices the range → deploy-director preflights + dispatches
    → server-deploy (self-healing, gate-never-bypassed) → restart
    → deploy-director verify / heartbeat / healthcheck / breaker watch the result
    → outcomes feed managers' next pass
```

Human touchpoints that REMAIN: protected-path approvals, Telegram
notifications (informational), `/rate`, Reopen, and god.

## Safety inventory after this change

Structural gates that do not depend on any prompt: pytest deploy gate ·
INV-13 fail-closed post-review · readonly guard hooks (INV-20) · workspace
guard hooks (INV-17) · protected-path list · lint checks 1–13 (incl. oversight
privilege + logger style) · circuit breaker · heartbeat + dead-man's-switch +
healthcheck DM backstop · append-only audit · `paused` flag on every schedule.

Known residual risks (accepted, documented): readonly Bash guard is a
denylist, not a sandbox (Seatbelt is the eventual answer — SYSTEM.md debt);
autopilot deploys anything gate-green + LGTM'd that lands on origin/main, so
branch protection on the GitHub repo is worth enabling; single-machine blast
radius unchanged.
