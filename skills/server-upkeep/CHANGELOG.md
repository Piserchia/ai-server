## 2026-07-12 — Routine upkeep run (anomalies: stale projects + review-and-improve never run)

**Agent task**: daily server upkeep audit
**Result**: 3 projects stale >24h (market-tracker ~3d, baseball-bingo ~2d, atlas ~2d). review-and-improve skill has never run. launchd -15 exit codes present but all processes have active PIDs — this is normal SIGTERM-from-prior-restart behavior, not a crash. Logs: nothing rotated/compressed/deleted. Audit index rebuilt (145 jobs). DB vacuum OK. Tunnel active (version outdated: 2026.3.0 → 2026.7.1). Disk 42%. Local backup fresh (19h). Off-site not configured. Writebacks 8/7d (normal). Restarts: false positives only (Vite startup lines in atlas log).

---

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
