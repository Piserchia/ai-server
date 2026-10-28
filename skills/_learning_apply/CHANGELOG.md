## 2026-10-26 — Preload `.context/modules/runner/skills/GOTCHAS.md` via context_files

**Files created**: `skills/_learning_apply/CHANGELOG.md` (this file).
**Files changed**: `skills/_learning_apply/SKILL.md` (frontmatter `context_files`).
**Why**: review-and-improve proposal
`26dcaee4-3772-4265-b808-ab7a171a8e14` found that over the last 30 days, 8
of 12 `_learning_apply` runs (67%) Read `.context/modules/runner/skills/GOTCHAS.md`
during the session. The skill declared no `context_files`, so each of those
8 runs paid a Read tool call for a file we already know the majority of
runs want. Preloading it eliminates that Read on ~2 of every 3 runs; the
remaining ~1 in 3 (learnings landing on gateway/db/registry/hosting/project
modules) absorb ~617 extra lines of static context. For a short-lived
(`max_turns=10`), internal Sonnet/low-effort skill, the net is a win.
Frontmatter-only change; markdown body unchanged, so no system-prompt /
behavioral regression surface — the review-and-improve eval guard does not
apply, and `_learning_apply` has no `evals/cases/*.yml` (internal, not
user-triggerable).

**Side effects**: Each _learning_apply run now pays a one-time preload cost
for the runner GOTCHAS file (~617 lines) regardless of which module the
learning targets. For the ~1-in-3 runs that would not have Read it anyway,
this is pure overhead; for the ~2-in-3 that would, it is a win. Acceptable
on net.

**Gotchas discovered**: None.

Proposal-ID: 26dcaee4-3772-4265-b808-ab7a171a8e14
