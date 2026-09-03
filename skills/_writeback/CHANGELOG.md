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
