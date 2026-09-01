# Firm WS1 — Schedule-Adherence Monitor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A deterministic, out-of-band watchdog that answers "did scheduled runs happen at all?" — DARK / NEVER_RAN / FAILURE_STREAK / STUCK findings, daily DM, and a JSON artifact other systems can read.

**Architecture:** Pure decision logic in `src/runner/schedule_adherence.py` (dicts in → findings out, injected `now`, mirroring `schedule_rollup` in `src/gateway/web.py:175`), a thin async `_collect()`/`main()` in the same module using the existing `src.db` session, a bash wrapper `scripts/schedule-monitor.sh` reusing the `healthcheck-all.sh` curl-DM + epoch-rate-limit idiom, and a launchd `install_timer` entry (daily 07:15 local).

**Tech Stack:** Python 3.12, croniter (already a dep — the scheduler uses it), SQLAlchemy async via `src.db`, pytest (pure-function-first, no DB), bash + launchd + psql-free.

**Spec:** `docs/superpowers/specs/2026-09-01-atlas-firm-org-design.md` (§WS1)

## Global Constraints

- Never set `ANTHROPIC_API_KEY`; no new dependencies.
- Jobs join to schedules by `schedule_id`, NEVER by kind (review 2026-08-17).
- Monitor must work with runner, bot, and tunnel all dead (out-of-band doctrine, `healthcheck-all.sh:140-145`).
- Tests are pure-function-first: no DB fixtures; frozen `NOW`; flat `tests/test_<topic>.py` with class grouping and a docstring header stating the run command and the why.
- CHANGELOG update required for `src/` changes (pre-commit hook enforces); doc-map updates: `.context/SYSTEM.md` module graph, `.context/modules/runner/CONTEXT.md`, `.context/modules/hosting/CONTEXT.md`.
- Server code merge gate: full pytest green + `code-review` LGTM (INV-13) + fetch/merge origin/main before push.

---

### Task 1: Pure adherence logic + tests

**Files:**
- Create: `src/runner/schedule_adherence.py` (pure part only)
- Test: `tests/test_schedule_adherence.py`

**Interfaces:**
- Produces: `adherence_report(schedules: list[dict], jobs: list[dict], now: datetime, window_days: int = 45, grace_seconds: int = 10800, streak_threshold: int = 3, stuck_hours: int = 24) -> dict` returning `{"findings": [...], "schedules": [...]}`.
  - `schedules` dicts: `id, name, cron_expression, paused (bool), created_at (datetime), total_jobs (int)`.
  - `jobs` dicts: `schedule_id, status, created_at, started_at, completed_at` — pre-filtered to the window, **newest first** (the fold does not re-sort; same contract as `schedule_rollup`).
  - Finding dicts: `{"kind": "DARK"|"NEVER_RAN"|"FAILURE_STREAK"|"STUCK", "schedule": <name>, "detail": <str>}`.
  - Per-schedule rows: `{"name", "cron", "paused", "status": "ok"|"paused"|"dark"|"never_ran"|"failing"|"stuck", "last_expected" (iso|None), "observed_job_at" (iso|None)}` — the export WS2a's `firm/liveness.py` ingests.

- [ ] **Step 1: Write the failing tests**

`tests/test_schedule_adherence.py`:

```python
"""Schedule-adherence monitor decision logic — the missing-run axis.

schedule_rollup (src/gateway/web.py) answers "did runs fail?"; this module
answers "did runs happen at all?" — the 08-17 governor-dark incident class
(and the scout-never-ran class) that no existing telemetry covers.

Run: pipenv run pytest tests/test_schedule_adherence.py -v
"""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from src.runner.schedule_adherence import adherence_report

NOW = datetime(2026, 9, 2, 18, 0, tzinfo=timezone.utc)  # Wednesday


def _sched(name="s", cron="0 11 * * 1", paused=False, created_days_ago=120,
           total_jobs=10, sid=None):
    return {
        "id": sid or str(uuid4()),
        "name": name,
        "cron_expression": cron,
        "paused": paused,
        "created_at": NOW - timedelta(days=created_days_ago),
        "total_jobs": total_jobs,
    }


def _job(sid, status="completed", created_hours_ago=1.0):
    created = NOW - timedelta(hours=created_hours_ago)
    terminal = status in {"completed", "failed", "cancelled"}
    return {
        "schedule_id": sid,
        "status": status,
        "created_at": created,
        "started_at": created,
        "completed_at": created + timedelta(minutes=5) if terminal else None,
    }


class TestDark:
    def test_governor_dark_incident_shape(self):
        # Weekly Mon 11:00 UTC; last slot Mon 2026-08-31 11:00 — 55h before
        # NOW, no job since. The 08-17 incident: scheduler alive-looking,
        # governor silently not running.
        s = _sched(name="atlas-evaluate", cron="0 11 * * 1")
        jobs = [_job(s["id"], created_hours_ago=24 * 9)]  # last week's run only
        rep = adherence_report([s], jobs, NOW)
        assert [f["kind"] for f in rep["findings"]] == ["DARK"]
        assert rep["schedules"][0]["status"] == "dark"

    def test_job_covering_latest_slot_is_healthy(self):
        s = _sched(cron="0 11 * * 1")
        jobs = [_job(s["id"], created_hours_ago=54.9)]  # fired right at Mon slot
        rep = adherence_report([s], jobs, NOW)
        assert rep["findings"] == []
        assert rep["schedules"][0]["status"] == "ok"

    def test_within_grace_not_dark(self):
        # Slot 2h ago, grace 3h — too early to judge.
        s = _sched(cron="0 16 * * *")
        rep = adherence_report([s], [], NOW)
        assert all(f["kind"] != "DARK" for f in rep["findings"])

    def test_slot_clock_slack(self):
        # Job created 90s BEFORE the slot timestamp still counts (clock skew).
        s = _sched(cron="0 11 * * 1")
        slot = datetime(2026, 8, 31, 11, 0, tzinfo=timezone.utc)
        j = _job(s["id"])
        j["created_at"] = slot - timedelta(seconds=90)
        rep = adherence_report([s], [j], NOW)
        assert rep["findings"] == []

    def test_paused_schedule_skipped(self):
        s = _sched(cron="0 11 * * 1", paused=True)
        rep = adherence_report([s], [], NOW)
        assert rep["findings"] == []
        assert rep["schedules"][0]["status"] == "paused"


class TestNeverRan:
    def test_scout_never_ran(self):
        # Enabled for months, slots expected, zero jobs EVER.
        s = _sched(name="atlas-scout", cron="0 12 * * 3", total_jobs=0)
        rep = adherence_report([s], [], NOW)
        kinds = {f["kind"] for f in rep["findings"]}
        assert "NEVER_RAN" in kinds
        assert rep["schedules"][0]["status"] == "never_ran"

    def test_new_schedule_no_slot_yet_is_ok(self):
        # Created an hour ago, first slot tomorrow: nothing expected yet.
        s = _sched(cron="0 11 * * 1", created_days_ago=0, total_jobs=0)
        s["created_at"] = NOW - timedelta(hours=1)
        rep = adherence_report([s], [], NOW)
        assert rep["findings"] == []


class TestFailureStreak:
    def test_three_consecutive_failures_flagged(self):
        s = _sched(cron="0 16 * * *")
        jobs = [_job(s["id"], "failed", 2), _job(s["id"], "failed", 26),
                _job(s["id"], "failed", 50), _job(s["id"], "completed", 74)]
        rep = adherence_report([s], jobs, NOW)
        assert any(f["kind"] == "FAILURE_STREAK" for f in rep["findings"])
        assert rep["schedules"][0]["status"] == "failing"

    def test_cancelled_ends_streak(self):
        s = _sched(cron="0 16 * * *")
        jobs = [_job(s["id"], "failed", 2), _job(s["id"], "failed", 26),
                _job(s["id"], "cancelled", 50), _job(s["id"], "failed", 74)]
        rep = adherence_report([s], jobs, NOW)
        assert all(f["kind"] != "FAILURE_STREAK" for f in rep["findings"])


class TestStuck:
    def test_old_nonterminal_job_flagged(self):
        s = _sched(cron="0 16 * * *")
        jobs = [_job(s["id"], "awaiting_user", 30), _job(s["id"], "completed", 2)]
        rep = adherence_report([s], jobs, NOW)
        assert any(f["kind"] == "STUCK" for f in rep["findings"])

    def test_recent_running_job_ok(self):
        s = _sched(cron="0 16 * * *")
        jobs = [_job(s["id"], "running", 1), _job(s["id"], "completed", 26)]
        rep = adherence_report([s], jobs, NOW)
        assert all(f["kind"] != "STUCK" for f in rep["findings"])


class TestReportShape:
    def test_dark_sorts_first_and_healthy_fleet_summary(self):
        dark = _sched(name="z-dark", cron="0 11 * * 1")
        ok = _sched(name="a-ok", cron="0 16 * * *")
        jobs = [_job(ok["id"], created_hours_ago=2)]
        rep = adherence_report([dark, ok], jobs, NOW)
        assert rep["schedules"][0]["name"] == "z-dark"
        assert {"findings", "schedules"} <= set(rep)
```

- [ ] **Step 2: Run tests, verify they fail with ModuleNotFoundError/ImportError**

Run: `pipenv run pytest tests/test_schedule_adherence.py -v`

- [ ] **Step 3: Implement the pure module**

`src/runner/schedule_adherence.py`:

```python
"""Schedule-adherence monitor — the missing-run axis of fleet telemetry.

schedule_rollup (src/gateway/web.py) grades runs that exist; nothing in the
system notices a schedule that silently stops producing runs at all. That is
the 08-17 governor-dark incident class (scheduler task dead / phase-shifted
after an outage / row hand-paused and forgotten) and the scout-never-ran
class. This module is the deterministic answer. It is invoked OUT-OF-BAND by
scripts/schedule-monitor.sh on a launchd timer — never by the scheduler it
watches (healthcheck-all.sh codifies the rationale).

Pure decision logic up top (dicts in, findings out, injected now) so the
tests need zero fixtures; the async collector + CLI main at the bottom are
thin I/O.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from croniter import croniter

#: Terminal statuses — same set schedule_rollup uses.
_TERMINAL = {"completed", "failed", "cancelled"}

#: Jobs may be stamped up to this many seconds before their cron slot
#: (clock skew safety); the scheduler itself fires <=30s after.
_SLOT_SLACK_S = 120


def _last_expected(cron: str, now: datetime) -> datetime:
    return croniter(cron, now).get_prev(datetime)


def adherence_report(
    schedules: list[dict],
    jobs: list[dict],
    now: datetime,
    window_days: int = 45,
    grace_seconds: int = 10800,
    streak_threshold: int = 3,
    stuck_hours: int = 24,
) -> dict[str, Any]:
    """Pure. Fold the fleet into adherence findings + per-schedule statuses.

    ``jobs`` must be pre-filtered to the window and ordered NEWEST FIRST and
    matched by schedule_id, never kind — the schedule_rollup contract.
    Finding kinds, in severity order: DARK (latest expected slot has no job
    after grace), NEVER_RAN (slots expected since creation, zero jobs ever),
    STUCK (non-terminal job older than stuck_hours), FAILURE_STREAK
    (>= streak_threshold consecutive terminal failures; cancelled ends a
    streak — operator action, not reliability signal).
    """
    by_schedule: dict[str, list[dict]] = {}
    for j in jobs:
        by_schedule.setdefault(str(j["schedule_id"]), []).append(j)

    findings: list[dict] = []
    rows: list[dict] = []
    for sch in schedules:
        name = sch["name"]
        sjobs = by_schedule.get(str(sch["id"]), [])
        newest = sjobs[0]["created_at"] if sjobs else None
        if sch.get("paused"):
            rows.append(_row(sch, "paused", None, newest))
            continue

        last_slot = _last_expected(sch["cron_expression"], now)
        status = "ok"

        stuck = [
            j for j in sjobs
            if j["status"] not in _TERMINAL
            and (now - j["created_at"]) > timedelta(hours=stuck_hours)
        ]
        if stuck:
            status = "stuck"
            findings.append({
                "kind": "STUCK", "schedule": name,
                "detail": f"{len(stuck)} non-terminal job(s) older than "
                          f"{stuck_hours}h (oldest status "
                          f"{stuck[-1]['status']!r})",
            })

        terminal = [j for j in sjobs if j["status"] in _TERMINAL]
        streak = 0
        for j in terminal:  # newest first
            if j["status"] == "failed":
                streak += 1
            else:
                break
        if streak >= streak_threshold:
            status = "failing"
            findings.append({
                "kind": "FAILURE_STREAK", "schedule": name,
                "detail": f"{streak} consecutive failures",
            })

        slot_covered = any(
            j["created_at"] >= last_slot - timedelta(seconds=_SLOT_SLACK_S)
            for j in sjobs
        )
        past_grace = (now - last_slot) > timedelta(seconds=grace_seconds)
        expected_since_creation = croniter(
            sch["cron_expression"], sch["created_at"]
        ).get_next(datetime) <= now

        if sch.get("total_jobs", 0) == 0:
            if expected_since_creation and past_grace:
                status = "never_ran"
                findings.append({
                    "kind": "NEVER_RAN", "schedule": name,
                    "detail": "zero jobs ever despite expected slots since "
                              f"{sch['created_at']:%Y-%m-%d}",
                })
        elif past_grace and not slot_covered:
            status = "dark"
            findings.append({
                "kind": "DARK", "schedule": name,
                "detail": f"no job since expected slot "
                          f"{last_slot:%Y-%m-%d %H:%M}Z "
                          f"(grace {grace_seconds // 3600}h exceeded)",
            })

        rows.append(_row(sch, status, last_slot, newest))

    severity = {"dark": 0, "never_ran": 1, "stuck": 2, "failing": 3,
                "ok": 4, "paused": 5}
    rows.sort(key=lambda r: (severity[r["status"]], r["name"]))
    order = {"DARK": 0, "NEVER_RAN": 1, "STUCK": 2, "FAILURE_STREAK": 3}
    findings.sort(key=lambda f: (order[f["kind"]], f["schedule"]))
    return {"findings": findings, "schedules": rows}


def _row(sch: dict, status: str, last_slot: datetime | None,
         observed: datetime | None) -> dict:
    return {
        "name": sch["name"],
        "cron": sch["cron_expression"],
        "paused": bool(sch.get("paused")),
        "status": status,
        "last_expected": last_slot.isoformat() if last_slot else None,
        "observed_job_at": observed.isoformat() if observed else None,
    }
```

- [ ] **Step 4: Run tests, verify PASS**

Run: `pipenv run pytest tests/test_schedule_adherence.py -v`

- [ ] **Step 5: Commit**

```bash
git add src/runner/schedule_adherence.py tests/test_schedule_adherence.py
git commit -m "feat(runner): schedule-adherence decision logic — DARK/NEVER_RAN/STUCK/FAILURE_STREAK (firm WS1)"
```

(CHANGELOG comes with Task 3's doc pass; if the pre-commit hook demands it now, add the `.context/modules/runner/CHANGELOG.md` entry from Task 3 in this commit instead.)

---

### Task 2: Collector + CLI main + JSON artifact

**Files:**
- Modify: `src/runner/schedule_adherence.py` (append I/O section)

**Interfaces:**
- Consumes: `adherence_report` (Task 1), `src.db.get_session` (existing house session factory — check its actual name in `src/db.py` and use that), `src.models.Schedule/Job`.
- Produces: `python -m src.runner.schedule_adherence` prints `FINDING <kind> <name>: <detail>` lines then an `OK ...` summary line, writes `volumes/telemetry/schedule_adherence.json`, always exits 0 (alerting is the shell's job).

- [ ] **Step 1: Read `src/db.py` and the top of `src/runner/main.py`** to copy the exact session-factory import and usage idiom (do not invent one).

- [ ] **Step 2: Append the I/O section**

```python
# ── I/O below: thin, untested by design (pure-function-first suite) ──────

async def _collect(window_days: int = 45) -> tuple[list[dict], list[dict]]:
    """Read schedules (+ per-schedule total job count) and windowed jobs."""
    from sqlalchemy import func, select

    from src.db import async_session  # match the real factory name
    from src.models import Job, Schedule

    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    async with async_session() as s:
        counts = dict(
            (await s.execute(
                select(Job.schedule_id, func.count())
                .where(Job.schedule_id.is_not(None))
                .group_by(Job.schedule_id)
            )).all()
        )
        scheds = [{
            "id": str(r.id), "name": r.name,
            "cron_expression": r.cron_expression,
            "paused": r.paused, "created_at": r.created_at,
            "total_jobs": int(counts.get(r.id, 0)),
        } for r in (await s.execute(select(Schedule))).scalars()]
        jobs = [{
            "schedule_id": str(r.schedule_id), "status": r.status,
            "created_at": r.created_at, "started_at": r.started_at,
            "completed_at": r.completed_at,
        } for r in (await s.execute(
            select(Job)
            .where(Job.schedule_id.is_not(None), Job.created_at >= cutoff)
            .order_by(Job.created_at.desc())
        )).scalars()]
    return scheds, jobs


def main() -> None:
    import asyncio
    import json
    from pathlib import Path

    now = datetime.now(timezone.utc)
    scheds, jobs = asyncio.run(_collect())
    rep = adherence_report(scheds, jobs, now)

    out = Path("volumes/telemetry")
    out.mkdir(parents=True, exist_ok=True)
    (out / "schedule_adherence.json").write_text(json.dumps({
        "generated_at": now.isoformat(),
        "findings": rep["findings"],
        "schedules": rep["schedules"],
    }, indent=2))

    for f in rep["findings"]:
        print(f"FINDING {f['kind']} {f['schedule']}: {f['detail']}")
    n_paused = sum(1 for r in rep["schedules"] if r["status"] == "paused")
    print(f"OK {len(scheds)} schedules ({n_paused} paused), "
          f"{len(rep['findings'])} finding(s)")


if __name__ == "__main__":
    main()
```

Adjust the import/typing to whatever `src/db.py` actually exposes; timezone-naive columns (if any) must be coerced to UTC-aware before comparison — check `src/models.py` DateTime(timezone=True) and coerce if false.

- [ ] **Step 3: Smoke-run against the dev DB** (dev `.env` — note the env-topology gotcha: confirm it points at a reachable DB first; if not, run with `DATABASE_URL` overridden or accept a connection error as out-of-scope and verify on prod post-deploy):

Run: `pipenv run python -m src.runner.schedule_adherence; cat volumes/telemetry/schedule_adherence.json | head -30`
Expected: FINDING/OK lines, valid JSON, exit 0.

- [ ] **Step 4: Full suite + commit**

```bash
pipenv run pytest -q
git add -A src/runner/schedule_adherence.py
git commit -m "feat(runner): adherence collector + CLI main + telemetry JSON artifact"
```

---

### Task 3: Shell wrapper + launchd timer + docs

**Files:**
- Create: `scripts/schedule-monitor.sh`
- Modify: `scripts/install-launchd.sh` (one `install_timer` call beside the existing two, ~line 195)
- Modify: `.context/SYSTEM.md` (module-graph/scripts table row), `.context/modules/runner/CONTEXT.md` (Paths + public interface), `.context/modules/hosting/CONTEXT.md` (new timer), `.context/modules/runner/CHANGELOG.md` (entry)

**Interfaces:**
- Consumes: `python -m src.runner.schedule_adherence` FINDING-line contract (Task 2).
- Produces: `com.assistant.schedule-monitor` launchd timer, daily 07:15 local; DM on findings (12h rate limit) and always on Sundays.

- [ ] **Step 1: Write `scripts/schedule-monitor.sh`**

```bash
#!/usr/bin/env bash
# scripts/schedule-monitor.sh — schedule-adherence watchdog (firm WS1).
#
# OUT-OF-BAND by design: the scheduler cannot watchdog itself (08-17
# governor-dark incident; healthcheck-all.sh codifies the doctrine). Daily
# via launchd (com.assistant.schedule-monitor). Deterministic — no LLM.
# DMs the owner when findings exist (>=12h between alert DMs) and always
# sends the Sunday fleet summary.
#
# Usage: bash scripts/schedule-monitor.sh
set -uo pipefail
export PATH="/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG="$PROJECT_DIR/volumes/logs/schedule-monitor.log"
ALERT_STATE="$PROJECT_DIR/volumes/schedule-monitor-alert.epoch"
ALERT_INTERVAL=43200   # one findings-DM per 12h; Sunday summary bypasses

cd "$PROJECT_DIR"
out=$(pipenv run python -m src.runner.schedule_adherence 2>>"$LOG")
rc=$?
echo "$(date -u +%FT%TZ) run rc=$rc" >> "$LOG"
printf '%s\n' "$out" >> "$LOG"
(( rc != 0 )) && exit 0   # collector failure already logged; not a finding

findings=$(printf '%s\n' "$out" | grep '^FINDING ' || true)
summary=$(printf '%s\n' "$out" | grep '^OK ' | tail -1)
dow=$(date -u +%u)
now=$(date +%s)

send_dm() {
    local msg="$1" token chat_ids chat_id
    token=$(grep -E '^TELEGRAM_BOT_TOKEN=' "$PROJECT_DIR/.env" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'" || true)
    chat_ids=$(grep -E '^TELEGRAM_ALLOWED_CHAT_IDS=' "$PROJECT_DIR/.env" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'" || true)
    chat_id=$(printf '%s' "$chat_ids" | cut -d, -f1 | tr -d '[:space:]')
    [[ -z "$token" || -z "$chat_id" ]] && { echo "$(date -u +%FT%TZ) WARN DM skipped: creds missing" >> "$LOG"; return 0; }
    curl -sf --max-time 10 "https://api.telegram.org/bot${token}/sendMessage" \
        --data-urlencode "chat_id=${chat_id}" \
        --data-urlencode "text=${msg}" > /dev/null 2>&1 \
        && echo "$(date -u +%FT%TZ) ALERT DM sent" >> "$LOG" \
        || echo "$(date -u +%FT%TZ) WARN DM failed" >> "$LOG"
}

if [[ -n "$findings" ]]; then
    last_alert=$(cat "$ALERT_STATE" 2>/dev/null || echo 0)
    [[ "$last_alert" =~ ^[0-9]+$ ]] || last_alert=0
    if (( now - last_alert >= ALERT_INTERVAL )); then
        send_dm "🕳 Schedule monitor: $(printf '%s\n' "$findings" | wc -l | tr -d ' ') finding(s)
$findings
$summary"
        echo "$now" > "$ALERT_STATE" 2>/dev/null || true
    fi
elif (( dow == 7 )); then
    send_dm "🗓 Schedule monitor (Sunday): all clear. $summary"
fi
exit 0
```

- [ ] **Step 2: Add the timer to `scripts/install-launchd.sh`** next to the healthcheck-all call:

```bash
install_timer "schedule-monitor" "scripts/schedule-monitor.sh" \
  "<key>StartCalendarInterval</key><dict><key>Hour</key><integer>7</integer><key>Minute</key><integer>15</integer></dict>"
```

- [ ] **Step 3: Shellcheck-by-eye + dry run** (dev DB may be unreachable; the script must still exit 0 and log):

Run: `bash scripts/schedule-monitor.sh; echo "rc=$?"; tail -5 volumes/logs/schedule-monitor.log`
Expected: `rc=0`, log lines present, no DM without findings.

- [ ] **Step 4: Docs pass** — add one-line entries: SYSTEM.md scripts/module table (`scripts/schedule-monitor.sh` + `src/runner/schedule_adherence.py`), runner CONTEXT.md Paths + public interface (`adherence_report`, the JSON artifact path and shape), hosting CONTEXT.md (new `com.assistant.schedule-monitor` timer), runner CHANGELOG.md dated entry (what + why + incident refs 08-17/scout).

- [ ] **Step 5: Lint + full suite + commit**

```bash
pipenv run python scripts/lint_docs.py && pipenv run pytest -q
git add scripts/schedule-monitor.sh scripts/install-launchd.sh .context/
git commit -m "feat(scripts): out-of-band schedule-monitor timer + DM; docs pass (firm WS1)"
```

---

### Task 4: Review gate + merge + deploy note

**Files:** none new.

- [ ] **Step 1: Dispatch the `code-review` subagent** over `git diff origin/main...HEAD` (INV-13). Fix anything short of LGTM; re-run gates.
- [ ] **Step 2: Sync + push**: `git fetch origin && git merge origin/main` → re-run `pipenv run pytest -q` if the merge pulled anything → `git push origin main` (retry-once rule on rejection).
- [ ] **Step 3: Deploy + activate**: production picks this up via `/task deploy server` (server-deploy). The new timer requires one `bash scripts/install-launchd.sh` run on prod — note it in the deploy dispatch payload/summary so the deploy session runs it, or flag for the owner if the deploy skill refuses non-standard steps.
- [ ] **Step 4: Verify on prod** (post-deploy): `launchctl list | grep schedule-monitor`; run `bash scripts/schedule-monitor.sh` once by hand; confirm `volumes/telemetry/schedule_adherence.json` exists and the fleet reads sanely (33 schedules, findings plausibly empty or matching known state).

## Self-review notes

- Spec coverage: DARK/NEVER_RAN/FAILURE_STREAK/STUCK ✓; grace 3h ✓; JSON artifact for WS2a ✓; Sunday always-report ✓ (shell); rate limit ✓; launchd 07:15 ✓; docs/lint/INV-13 ✓. `window_days=45` (spec said 14 for the report; 45 is required so monthly crons' latest slot is inside the job window — spec's intent is covered, use 45).
- The `total_jobs` group-by makes NEVER_RAN exact rather than window-bound.
- Type consistency: `adherence_report` signature identical in Task 1 tests, Task 1 impl, Task 2 caller.
