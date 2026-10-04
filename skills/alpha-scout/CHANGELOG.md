## 2026-10-04 — GOTCHAS: capacity-check Glob false-zero + F-08 NAV-source scope

**Agent task**: docs append — record two runtime-discovered gotchas
**Files changed**:
- `skills/alpha-scout/GOTCHAS.md` — two entries appended: (1) Glob
  false-zero when capacity check runs from ai-server workspace cwd instead
  of the atlas repo path; (2) F-08 candidates require an explicit free NAV
  source name or triage blocks them as BLOCKED-ON-DATA.

**Why**: Glob with a relative path returns false-zero in the ai-server
workspace context; F-08 candidates consistently fail triage without a
named free NAV source. Documenting both to prevent recurrence.
**Side effects**: None — documentation-only change.
