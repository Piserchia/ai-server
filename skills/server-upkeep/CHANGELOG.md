## 2026-05-23 — Routine upkeep run (all clear)

**Agent task**: daily server upkeep audit
**Result**: All checks passed — no anomalies. Logs not rotated (none exceeded 50 MB). Audit index rebuilt (34 jobs). DB vacuum OK. Tunnel active. No stale projects. No writebacks. Disk 34% used. Restart grep matches confirmed false positives (Telegram shutdown messages + normal service startups).

---

## 2026-04-17 — Gotchas added from live run observations

**Agent task**: server-upkeep routine maintenance run (job 0143bf23)
**Files changed**:
- `skills/server-upkeep/SKILL.md` — appended two gotchas discovered during live runs: (1) `projects` table has no `status` column — queries must use only `slug` and `last_healthy_at`; (2) restart grep pattern produces false positives from Telegram error messages and project startup logs.

**Why**: Skill was producing false-positive restart alerts and crashing on missing `status` column. Gotchas were appended so future runs avoid the same pitfalls.
**Side effects**: None — documentation-only change.
**Gotchas discovered**: See SKILL.md §Gotchas section.
