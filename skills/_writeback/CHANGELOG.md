## 2026-10-05 — max_turns 20 → 30 (headroom for atlas-size writebacks)

**Agent task**: Implement review-and-improve proposal
`dcd79c03-322f-470c-9e66-99dfc7633300`: bump `_writeback` max_turns so
exhaustion stops aborting legitimate writebacks.
**Files changed**:
- `SKILL.md` — `max_turns: 20` → `max_turns: 30` (frontmatter-only).

**Why**: Over the preceding 30 days, 5 of 23 `_writeback` jobs (21.7%)
died at `max_turns=20`. All five parents were atlas-repo sessions
touching 3+ files across multiple directories (`.codex/agents/*.toml`,
`AGENTS.md`, `.agents/skills/*.md`), where the Rec-13 "Why" quality gate
forces audit-log dives spanning many Read/Edit/Write/Bash events. The
companion structural fix (proposal `a164301b`, same session) will shrink
the set of jobs that reach writeback at all, but legitimate multi-module
writebacks still need headroom. 20 → 30 keeps the same safety ceiling
character (budgeted, not open-ended) while covering the observed tail.

**Side effects**: A genuinely stalled `_writeback` burns 10 extra turns
before escalation. Acceptable: the skill's Hard limits forbid code
mutations, and the only consumer is the runner spawning it as a child —
no user-facing surface.

**Gotchas discovered**: this bump is paired with the structural fix in
`src/runner/writeback.py`. Watch the two together: if the agent-dir
reclassification already drops the writeback dispatch rate to near zero
for the atlas pattern, the max_turns bump may never fire in practice.
That's fine — the bump is cheap insurance for the long tail of
legitimately broad writebacks.

## 2026-09-03 — max_turns 10 → 20 (headroom for Rec-13 audit-log dives)

**Agent task**: Fix _writeback max_turns discrepancy; add observability for
future SDK-config failures.
**Files changed**:
- `SKILL.md` — `max_turns: 10` → `max_turns: 20`.

**Why**: The Rec-13 "Why" quality gate frequently forces this skill to open
the prior job's audit log (`volumes/audit_log/<prior_job_id>.jsonl`) and
reconstruct reasoning from a stream of Read/Edit/Write/Bash events —
easily 10+ tool calls for a multi-module CHANGELOG write-back. The prior
bump 6 → 10 (Proposal-ID `d7c87a16`, merged `12a7851` on 2026-09-02) hit
its own ceiling on wide-scope prior sessions; 20 gives clear headroom
without materially raising the runaway-loop risk (the skill's Hard limits
already forbid mutating code, and `_writeback` is spawned as a child, not
routed to).

**Side effects**: A stalled `_writeback` will burn more tool budget before
falling into the escalation chain — acceptable because the failure mode we
saw was legitimate work exceeding the limit, not runaways.

**Gotchas discovered**: The 2026-09-01 failure of job
`f6c9e375-376f-423f-9566-40a686131f60` looked like a "SKILL.md says 10 but
SDK enforced 6" discrepancy — it wasn't. The 6 → 10 bump merged the *next
day* (2026-09-02, `12a7851`), so at run time the SKILL.md truly said 6.
The audit log has no record of the effective `max_turns` / `permission_mode`
the SDK was configured with, which is what made this hard to diagnose;
added a companion `logger.info` in `session._build_options` this same
session so the next occurrence leaves a trace.
