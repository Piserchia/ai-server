## 2026-04-17 — Gotchas added from live run observations

**Agent task**: server-upkeep routine maintenance run (job 0143bf23)
**Files changed**:
- `skills/server-upkeep/SKILL.md` — appended two gotchas discovered during live runs: (1) `projects` table has no `status` column — queries must use only `slug` and `last_healthy_at`; (2) restart grep pattern produces false positives from Telegram error messages and project startup logs.

**Why**: Skill was producing false-positive restart alerts and crashing on missing `status` column. Gotchas were appended so future runs avoid the same pitfalls.
**Side effects**: None — documentation-only change.
**Gotchas discovered**: See SKILL.md §Gotchas section.
