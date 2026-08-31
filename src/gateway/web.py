"""
Web gateway. FastAPI.

Endpoints:
- GET  /                           — HTMX dashboard shell
- GET  /health                     — unauthenticated liveness probe (503 if runner heartbeat stale or DB/Redis down)
- POST /api/jobs                   — create a job (supports model/effort/permission in body)
- GET  /api/jobs                   — list jobs
- GET  /api/jobs/{id}              — job + audit log
- DELETE /api/jobs/{id}            — request cancel
- POST /api/jobs/{id}/rate         — submit a 1-5 rating
- GET  /api/projects               — list projects
- GET  /api/quota                  — { paused, reset_at, reason }
- GET  /api/retrospective/context  — context consumption rollup
- GET  /api/telemetry/schedules    — per-schedule reliability rollup (runs, success rate, failure streak, durations)
- GET  /api/tasks                  — list tasks
- GET  /api/tasks/{id}             — task + turns

Run: uvicorn src.gateway.web:app --host 127.0.0.1 --port 8080
"""

from __future__ import annotations

import asyncio
import json
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, Field
from sqlalchemy import select, text, update as sql_update
from sse_starlette.sse import EventSourceResponse

from src import audit_log
from src.config import settings
from src.db import CHANNEL_JOB_STREAM, KEY_RUNNER_HEARTBEAT, QUEUE_JOBS, async_session, redis
from src.gateway.jobs import cancel_job, enqueue_job, find_job_by_prefix
from src.models import Job, JobKind, JobStatus, Project, Schedule, Task, TaskStatus, TaskTurn
from src.runner import quota, retrospective

app = FastAPI(title="Assistant gateway", version="0.1.0")
security = HTTPBasic(auto_error=False)


def _check_auth(
    request: Request,
    creds: Annotated[HTTPBasicCredentials | None, Depends(security)] = None,
) -> None:
    token = settings.web_auth_token
    if not token:
        return   # dev mode
    header = request.headers.get("authorization", "")
    if header.startswith("Bearer ") and secrets.compare_digest(header[7:], token):
        return
    if creds and secrets.compare_digest(creds.password, token):
        return
    raise HTTPException(
        status_code=401, detail="Unauthorized", headers={"WWW-Authenticate": "Basic"}
    )


# ── Schemas ─────────────────────────────────────────────────────────────────


class CreateJobRequest(BaseModel):
    description: str
    kind: str = JobKind.task.value
    # Per-request overrides that go into payload (take precedence over skill frontmatter)
    model: str | None = None
    effort: str | None = Field(default=None, description="low|medium|high|xhigh|max")
    permission_mode: str | None = Field(
        default=None, description="default|acceptEdits|bypassPermissions|plan"
    )
    project_slug: str | None = None
    session_timeout_seconds: int | None = Field(
        default=None, ge=60, le=5400,
        description="per-job session-timeout override (runner clamps to the "
                    "same cap; heavyweight lab cycles need >30 min)")


class JobOut(BaseModel):
    id: uuid.UUID
    kind: str
    description: str
    status: str
    resolved_skill: str | None
    resolved_model: str | None
    resolved_effort: str | None
    user_rating: int | None
    review_outcome: str | None
    created_at: str
    started_at: str | None
    completed_at: str | None
    result: dict | None
    error_message: str | None
    created_by: str


class RateRequest(BaseModel):
    rating: int = Field(ge=1, le=5)


def _serialize(job: Job) -> JobOut:
    return JobOut(
        id=job.id,
        kind=job.kind,
        description=job.description,
        status=job.status,
        resolved_skill=job.resolved_skill,
        resolved_model=job.resolved_model,
        resolved_effort=job.resolved_effort,
        user_rating=job.user_rating,
        review_outcome=job.review_outcome,
        created_at=job.created_at.isoformat(),
        started_at=job.started_at.isoformat() if job.started_at else None,
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
        result=job.result,
        error_message=job.error_message,
        created_by=job.created_by,
    )


# ── Routes ──────────────────────────────────────────────────────────────────


def parse_heartbeat_age(raw: str | None, now: datetime) -> float | None:
    """Pure. Runner-heartbeat Redis value → age in seconds, or None if the key
    is absent or unparseable.

    The runner writes epoch seconds (2026-07-30, with a 15-min TTL — see
    ``db.KEY_RUNNER_HEARTBEAT``); runners before that wrote ISO-8601. Accept
    both so the mixed-version deploy window (new web + old runner, or the
    reverse) never misreports a live runner as dead.
    """
    if not raw:
        return None
    try:
        return now.timestamp() - float(raw)
    except (TypeError, ValueError):
        pass
    try:
        ts = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return (now - ts).total_seconds()


def health_verdict(
    heartbeat_age: float | None,
    db_ok: bool,
    redis_ok: bool,
    stale_after: float,
) -> tuple[bool, bool]:
    """Pure. Returns ``(runner_ok, healthy)`` from the collected liveness signals.

    ``runner_ok`` is true only when a heartbeat exists and is within
    ``stale_after`` seconds. ``healthy`` additionally requires DB and Redis.
    """
    runner_ok = heartbeat_age is not None and heartbeat_age <= stale_after
    healthy = db_ok and redis_ok and runner_ok
    return runner_ok, healthy


#: Terminal job statuses that count as a schedule "run" for telemetry.
#: queued/running are in-flight, not evidence about reliability either way.
_TERMINAL_FOR_TELEMETRY = {"completed", "failed", "cancelled"}


def schedule_rollup(
    schedules: list[dict],
    jobs: list[dict],
    window_days: int = 30,
) -> list[dict]:
    """Pure. Per-schedule health folded from its kind's recent jobs.

    ``schedules``: dicts with id/name/cron_expression/paused/next_run_at.
    ``jobs``: dicts with schedule_id/status/created_at/started_at/completed_at,
    pre-filtered to the window and ordered NEWEST FIRST (the fold relies on
    the ordering for last-run and streak semantics; it does not re-sort).

    Jobs are matched to their schedule by ``schedule_id`` — the column the
    scheduler stamps on every job it enqueues — NEVER by kind (review
    2026-08-17): kinds are dispatchable by hand via POST /api/jobs and
    Telegram, so a kind-join lets a manually re-run-and-cancelled job reset a
    schedule's failing streak, and two schedules sharing a kind would count
    each other's runs. No NULL-schedule_id fallback either: that would
    readmit exactly the manual jobs the join exists to exclude, and the
    stamping predates every row a 30d window can see.

    Semantics chosen for the owner's question ("is the machine that runs the
    lab healthy?"), not for dashboards' sake:
      - last_* comes from the newest TERMINAL job — an in-flight run tells
        you nothing about reliability yet.
      - consecutive_failures counts the failed streak from the newest
        terminal run backwards; it resets on completed AND on cancelled
        (a cancel is an operator action, not a reliability signal, but it
        does end a streak's evidential value).
      - in_flight counts EVERY non-terminal job (queued, running,
        awaiting_user, deferred, ...): a run parked in awaiting_user for
        days is precisely the stuck state this section exists to surface,
        and counting only status=='running' would hide it (review
        2026-08-17).
      - durations only exist where both started_at and completed_at do; a
        job that died before starting has no duration, not a zero one.
    """
    jobs_by_schedule: dict[str, list[dict]] = {}
    for j in jobs:
        jobs_by_schedule.setdefault(str(j["schedule_id"]), []).append(j)

    out: list[dict] = []
    for sch in schedules:
        kind_jobs = jobs_by_schedule.get(str(sch["id"]), [])
        terminal = [j for j in kind_jobs if j["status"] in _TERMINAL_FOR_TELEMETRY]
        completed = [j for j in terminal if j["status"] == "completed"]
        failed = [j for j in terminal if j["status"] == "failed"]

        durations = [
            (j["completed_at"] - j["started_at"]).total_seconds()
            for j in terminal
            if j.get("started_at") and j.get("completed_at")
        ]

        streak = 0
        for j in terminal:  # newest first
            if j["status"] == "failed":
                streak += 1
            else:
                break

        last = terminal[0] if terminal else None
        last_duration = None
        if last and last.get("started_at") and last.get("completed_at"):
            last_duration = round((last["completed_at"] - last["started_at"]).total_seconds(), 1)

        out.append({
            "name": sch["name"],
            "cron": sch["cron_expression"],
            "paused": bool(sch.get("paused")),
            "next_run_at": sch.get("next_run_at"),
            "window_days": window_days,
            "runs": len(terminal),
            "completed": len(completed),
            "failed": len(failed),
            "success_rate": round(len(completed) / len(terminal), 3) if terminal else None,
            "consecutive_failures": streak,
            "last_status": last["status"] if last else None,
            "last_finished_at": last.get("completed_at") if last else None,
            "last_duration_s": last_duration,
            "avg_duration_s": round(sum(durations) / len(durations), 1) if durations else None,
            "in_flight": len(kind_jobs) - len(terminal),
        })
    # Attention-first: failing streaks on top, then paused last, then by name.
    out.sort(key=lambda r: (-r["consecutive_failures"], r["paused"], r["name"]))
    return out


@app.get("/api/telemetry/schedules", dependencies=[Depends(_check_auth)])
async def schedule_telemetry(window_days: int = 30) -> list[dict]:
    """Per-schedule reliability rollup — observability for the scheduled fleet.

    One row per schedules-table row: run counts, success rate, failure streak,
    and durations folded from the last ``window_days`` of that kind's jobs.
    The fold itself is the pure ``schedule_rollup`` above.
    """
    window_days = max(1, min(window_days, 365))
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    async with async_session() as s:
        sch_rows = (await s.execute(select(Schedule))).scalars().all()
        ids = [x.id for x in sch_rows]
        jobs_rows = []
        if ids:
            # Column select on purpose: the dashboard polls this every 60s and
            # a full select(Job) would drag payload/result JSON blobs along
            # for every scheduled job in the window (review 2026-08-17).
            jq = (
                select(
                    Job.schedule_id, Job.status,
                    Job.created_at, Job.started_at, Job.completed_at,
                )
                .where(Job.schedule_id.in_(ids), Job.created_at >= cutoff)
                .order_by(Job.created_at.desc())
            )
            jobs_rows = list(await s.execute(jq))
    return schedule_rollup(
        [
            {
                "id": x.id,
                "name": x.name,
                "cron_expression": x.cron_expression,
                "paused": x.paused,
                "next_run_at": x.next_run_at.isoformat() if x.next_run_at else None,
            }
            for x in sch_rows
        ],
        [
            {
                "schedule_id": r.schedule_id,
                "status": r.status,
                "created_at": r.created_at,
                "started_at": r.started_at,
                "completed_at": r.completed_at,
            }
            for r in jobs_rows
        ],
        window_days,
    )


@app.get("/health")
async def health():
    """Liveness probe used by the external Cloudflare Worker dead-man's-switch.

    Returns 200 only when the runner heartbeat is fresh AND the DB and Redis are
    reachable; otherwise 503. This makes "silence" (a dead runner, a stuck web
    process, a sleeping Mac) observable to something outside this process tree.
    Unauthenticated by design so the edge Worker can poll it.
    """
    now = datetime.now(timezone.utc)
    db_ok = True
    redis_ok = True
    heartbeat_age: float | None = None
    redis_llen: int | None = None
    pg_queued: int | None = None
    pg_running: int | None = None
    pg_deferred: int | None = None

    try:
        hb = await redis.get(KEY_RUNNER_HEARTBEAT)
        redis_llen = await redis.llen(QUEUE_JOBS)
        heartbeat_age = parse_heartbeat_age(hb, now)
    except Exception:
        redis_ok = False

    try:
        async with async_session() as s:
            rows = (await s.execute(text(
                "SELECT status, COUNT(*) FROM jobs "
                "WHERE status IN ('queued','running','deferred') GROUP BY status"
            ))).all()
            counts = {status: n for status, n in rows}
            pg_queued = counts.get("queued", 0)
            pg_running = counts.get("running", 0)
            pg_deferred = counts.get("deferred", 0)
    except Exception:
        db_ok = False

    runner_ok, healthy = health_verdict(
        heartbeat_age, db_ok, redis_ok, settings.runner_heartbeat_stale_seconds
    )

    body = {
        "status": "ok" if healthy else "degraded",
        "runner_ok": runner_ok,
        "runner_heartbeat_age_s": round(heartbeat_age, 1) if heartbeat_age is not None else None,
        # queue_depth is the REAL backlog (Postgres queued rows). It used to be
        # the Redis LLEN alone, which reads 0 while ids wait inside the runner
        # process — 15 queued jobs looked like an idle server
        # (2026-08-31, EVALUATION_2026-08-30 F2.4). redis_llen kept for the
        # not-yet-popped view; both should converge near 0 on a quiet server.
        "queue_depth": pg_queued,
        "redis_llen": redis_llen,
        "pg_queued": pg_queued,
        "pg_running": pg_running,
        "pg_deferred": pg_deferred,
        "db_ok": db_ok,
        "redis_ok": redis_ok,
    }
    return JSONResponse(body, status_code=200 if healthy else 503)


@app.post("/api/jobs", dependencies=[Depends(_check_auth)])
async def create_job(req: CreateJobRequest) -> JobOut:
    # Telegram /god is the ONLY break-glass door (INV-18). The dispatch MCP
    # and /task --kind=god are closed; this was the third door — any
    # unisolated skill that can read WEB_AUTH_TOKEN could have posted a
    # kind=god job here (review catch, 2026-08-31).
    if req.kind.strip().lower() == "god":
        raise HTTPException(
            status_code=403,
            detail="kind 'god' is owner-invoked only — use Telegram /god")
    payload = {}
    if req.model:
        payload["model"] = req.model
    if req.effort:
        payload["effort"] = req.effort
    if req.permission_mode:
        payload["permission_mode"] = req.permission_mode
    if req.project_slug:
        payload["project_slug"] = req.project_slug
    if req.session_timeout_seconds:
        payload["session_timeout_seconds"] = req.session_timeout_seconds

    job = await enqueue_job(
        req.description,
        kind=req.kind,
        payload=payload or None,
        created_by="web",
    )
    return _serialize(job)


@app.get("/api/jobs", dependencies=[Depends(_check_auth)])
async def list_jobs(limit: int = 50, status: str | None = None) -> list[JobOut]:
    limit = max(1, min(limit, 200))
    async with async_session() as s:
        q = select(Job).order_by(Job.created_at.desc()).limit(limit)
        if status:
            q = q.where(Job.status == status)
        result = await s.execute(q)
        return [_serialize(j) for j in result.scalars()]


@app.get("/api/jobs/{job_id}", dependencies=[Depends(_check_auth)])
async def get_job(job_id: str) -> dict:
    job = await find_job_by_prefix(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    audit = audit_log.read(job.id, limit=500)
    return {"job": _serialize(job).model_dump(), "audit": audit}


@app.delete("/api/jobs/{job_id}", dependencies=[Depends(_check_auth)])
async def delete_job(job_id: str) -> dict:
    job = await find_job_by_prefix(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if JobStatus(job.status).is_terminal:
        return {"ok": True, "note": "already terminal"}
    await cancel_job(job.id)
    return {"ok": True, "note": "cancel requested"}


@app.post("/api/jobs/{job_id}/rate", dependencies=[Depends(_check_auth)])
async def rate_job(job_id: str, req: RateRequest) -> dict:
    job = await find_job_by_prefix(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    async with async_session() as s:
        await s.execute(
            sql_update(Job).where(Job.id == job.id).values(user_rating=req.rating)
        )
        await s.commit()
    return {"ok": True, "rating": req.rating}


@app.get("/api/projects", dependencies=[Depends(_check_auth)])
async def list_projects() -> list[dict]:
    # Authenticated view carries the delivery contract (topology, deployability).
    return await _get_projects(include_delivery=True)


@app.get("/api/projects/public")
async def list_projects_public() -> list[dict]:
    """Public endpoint — no auth. Returns only safe fields for the landing page."""
    return await _get_projects()


async def _get_projects(include_delivery: bool = False) -> list[dict]:
    async with async_session() as s:
        result = await s.execute(select(Project).order_by(Project.slug))
        out = []
        for p in result.scalars():
            row = {
                "slug": p.slug,
                "subdomain": p.subdomain,
                "type": p.type,
                "port": p.port,
                "last_healthy_at": p.last_healthy_at.isoformat() if p.last_healthy_at else None,
                "created_at": p.created_at.isoformat(),
            }
            if include_delivery:
                # Manifest is the source of truth for the delivery contract; read
                # it per project (fails open to None if missing/invalid).
                from src.runner.delivery import load_project_manifest
                m = load_project_manifest(p.slug)
                if m is not None:
                    row["topology"] = m.delivery.topology
                    row["deployable"] = m.delivery.deployable
                    row["deploy_autonomy"] = m.delivery.deploy.autonomy
                else:
                    row["topology"] = None
                    row["deployable"] = None
                    row["deploy_autonomy"] = None
            out.append(row)
        return out


@app.get("/api/quota", dependencies=[Depends(_check_auth)])
async def quota_status() -> dict:
    paused, reset_at, reason = await quota.is_paused()
    return {
        "paused": paused,
        "reset_at": reset_at.isoformat() if reset_at else None,
        "reason": reason,
    }


@app.get("/api/retrospective/context", dependencies=[Depends(_check_auth)])
async def context_consumption_report(since: str | None = None) -> list[dict]:
    """Context consumption rollup: which files each skill actually reads."""
    since_dt = None
    if since:
        since_dt = datetime.fromisoformat(since).replace(tzinfo=timezone.utc)
    data = await retrospective.context_consumption(since=since_dt)
    return [
        {
            "skill": u.skill,
            "file_path": u.file_path,
            "read_count": u.read_count,
            "total_skill_jobs": u.total_skill_jobs,
            "read_rate": round(u.read_count / u.total_skill_jobs, 3)
            if u.total_skill_jobs > 0 else 0.0,
            "success_rate": round(u.success_rate, 3),
            "avg_rating": round(u.avg_rating, 2) if u.avg_rating is not None else None,
        }
        for u in data
    ]


@app.get("/api/tasks", dependencies=[Depends(_check_auth)])
async def list_tasks(status: str | None = None, limit: int = 25) -> list[dict]:
    limit = max(1, min(limit, 100))
    async with async_session() as s:
        q = select(Task).order_by(Task.created_at.desc()).limit(limit)
        if status:
            q = q.where(Task.status == status)
        result = await s.execute(q)
        return [
            {
                "id": str(t.id),
                "description": t.description,
                "status": t.status,
                "created_by": t.created_by,
                "created_at": t.created_at.isoformat(),
                "updated_at": t.updated_at.isoformat(),
            }
            for t in result.scalars()
        ]


@app.get("/api/tasks/{task_id}", dependencies=[Depends(_check_auth)])
async def get_task(task_id: str) -> dict:
    async with async_session() as s:
        # Try full UUID first, then prefix
        task = None
        try:
            import uuid as _uuid
            task = await s.get(Task, _uuid.UUID(task_id))
        except ValueError:
            from sqlalchemy import text
            result = await s.execute(
                text("SELECT id FROM tasks WHERE CAST(id AS TEXT) LIKE :p LIMIT 2"),
                {"p": f"{task_id}%"},
            )
            ids = [row[0] for row in result.fetchall()]
            if len(ids) == 1:
                task = await s.get(Task, ids[0])
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        result = await s.execute(
            select(TaskTurn)
            .where(TaskTurn.task_id == task.id)
            .order_by(TaskTurn.turn_number)
        )
        turns = [
            {
                "turn_number": t.turn_number,
                "role": t.role,
                "content": t.content,
                "job_id": str(t.job_id) if t.job_id else None,
                "created_at": t.created_at.isoformat(),
            }
            for t in result.scalars()
        ]

    return {
        "task": {
            "id": str(task.id),
            "description": task.description,
            "status": task.status,
            "created_by": task.created_by,
            "created_at": task.created_at.isoformat(),
            "updated_at": task.updated_at.isoformat(),
        },
        "turns": turns,
    }


# ── SSE streaming ──────────────────────────────────────────────────────────


@app.get("/api/jobs/{job_id}/stream")
async def stream_job(job_id: str, request: Request, token: str | None = None):
    """SSE endpoint for live job tailing. Auth via query param ?token=."""
    if token != settings.web_auth_token:
        raise HTTPException(401, "Invalid token")

    job = await find_job_by_prefix(job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    async def event_generator():
        # 1. Send existing audit log events
        existing = audit_log.read(job.id, limit=500)
        for evt in existing:
            yield {"event": "audit", "data": json.dumps(evt, default=str)}

        # 2. If still running, subscribe to Redis for live events
        if job.status in (JobStatus.queued.value, JobStatus.running.value):
            pubsub = redis.pubsub()
            channel = f"{CHANNEL_JOB_STREAM}:{job.id}"
            await pubsub.subscribe(channel)
            try:
                while True:
                    if await request.is_disconnected():
                        break
                    msg = await pubsub.get_message(
                        ignore_subscribe_messages=True, timeout=2
                    )
                    if msg and msg.get("type") == "message":
                        yield {"event": "audit", "data": msg.get("data", "")}
                    # Check if job completed
                    async with async_session() as s:
                        j = await s.get(Job, job.id)
                        if j and j.status not in (
                            JobStatus.queued.value, JobStatus.running.value
                        ):
                            yield {"event": "done", "data": j.status}
                            break
            finally:
                await pubsub.unsubscribe(channel)

    return EventSourceResponse(event_generator())


# ── Dashboard shell ─────────────────────────────────────────────────────────


_INDEX_HTML = """<!DOCTYPE html>
<html>
<head>
  <title>Assistant</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <script src="https://unpkg.com/htmx.org@2.0.0"></script>
  <style>
    :root { color-scheme: dark; }
    body { font-family: ui-monospace, monospace; max-width: 1100px; margin: 2rem auto;
           padding: 0 1rem; background: #0d1117; color: #e6edf3; }
    h1, h2 { color: #7ee3f5; }
    table { width: 100%; border-collapse: collapse; margin: 1rem 0; }
    th, td { text-align: left; padding: .5rem .75rem; border-bottom: 1px solid #1f2a37; }
    th { color: #7ee3f5; font-weight: 600; }
    .badge { padding: .1rem .5rem; border-radius: 4px; font-size: .8em; }
    .queued { background: #1f2a37; color: #9da7b3; }
    .running { background: #0b3a5c; color: #7ee3f5; }
    .completed { background: #0d3d22; color: #7ddc9a; }
    .failed { background: #4c1e1e; color: #f28b82; }
    .cancelled { background: #2a2a2a; color: #888; }
    .awaiting_user { background: #3d3320; color: #f5d97e; }
    form { display: flex; gap: .5rem; margin: 1rem 0; flex-wrap: wrap; }
    input, select { padding: .5rem; background: #161b22; color: #e6edf3;
                    border: 1px solid #30363d; border-radius: 4px; }
    input[type=text] { flex: 1; min-width: 300px; }
    button { padding: .5rem 1rem; background: #238636; color: white; border: 0;
             border-radius: 4px; cursor: pointer; font-weight: 600; }
    a { color: #58a6ff; }
    .quota-banner { padding: .75rem 1rem; background: #3d3320; color: #f5d97e;
                    border-radius: 4px; margin-bottom: 1rem; display: none; }
    .quota-banner.visible { display: block; }
  </style>
</head>
<body>
  <h1>Assistant</h1>

  <div id="quota-banner" class="quota-banner" hx-get="/api/quota"
       hx-trigger="load, every 30s" hx-swap="none"></div>

  <form id="submit-form">
    <input type="text" name="description" placeholder="describe a task..." required>
    <select name="model">
      <option value="">default</option>
      <option value="claude-sonnet-4-6">sonnet 4.6</option>
      <option value="claude-opus-4-7">opus 4.7</option>
      <option value="claude-haiku-4-5-20251001">haiku 4.5</option>
    </select>
    <select name="effort">
      <option value="">default</option>
      <option value="low">low</option>
      <option value="medium">medium</option>
      <option value="high">high</option>
      <option value="xhigh">xhigh</option>
      <option value="max">max</option>
    </select>
    <button type="submit">Submit</button>
  </form>

  <h2>Jobs</h2>
  <div id="jobs" hx-get="/api/jobs?limit=25" hx-trigger="load, every 5s"
       hx-swap="innerHTML">Loading...</div>

  <h2>Projects</h2>
  <div id="projects" hx-get="/api/projects" hx-trigger="load, every 30s"
       hx-swap="innerHTML">Loading...</div>

  <h2>Schedules</h2>
  <div id="schedules" hx-get="/api/telemetry/schedules" hx-trigger="load, every 60s"
       hx-swap="innerHTML">Loading...</div>

  <script>
    document.getElementById("submit-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const f = e.target;
      const body = {
        description: f.description.value,
        ...(f.model.value && { model: f.model.value }),
        ...(f.effort.value && { effort: f.effort.value }),
      };
      const r = await fetch("/api/jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (r.ok) {
        f.description.value = "";
        htmx.trigger("#jobs", "load");
      } else {
        alert("Error: " + r.status);
      }
    });

    document.body.addEventListener("htmx:afterRequest", (e) => {
      const target = e.detail.elt;
      if (!target.id) return;
      try {
        const data = JSON.parse(e.detail.xhr.response);
        if (target.id === "jobs" && Array.isArray(data)) {
          target.innerHTML = renderJobs(data);
        } else if (target.id === "projects" && Array.isArray(data)) {
          target.innerHTML = renderProjects(data);
        } else if (target.id === "schedules" && Array.isArray(data)) {
          target.innerHTML = renderSchedules(data);
        } else if (target.id === "quota-banner") {
          renderQuota(data);
        }
      } catch {}
    });

    function renderJobs(rows) {
      if (!rows.length) return "<p>No jobs yet.</p>";
      return `<table>
        <tr><th>ID</th><th>Skill / Kind</th><th>Model · Effort</th>
            <th>Status</th><th>Description</th><th>Rating</th><th>Created</th></tr>
        ${rows.map(r => `<tr>
          <td><a href="/api/jobs/${r.id}" target="_blank">${r.id.slice(0, 8)}</a></td>
          <td>${r.resolved_skill || r.kind}</td>
          <td>${r.resolved_model ? r.resolved_model.replace('claude-', '') : '—'}${
            r.resolved_effort ? ' · ' + r.resolved_effort : ''}</td>
          <td><span class="badge ${r.status}">${r.status}</span></td>
          <td>${esc(r.description).slice(0, 60)}</td>
          <td>${r.user_rating ?? (r.status === 'completed' ? rateCell(r.id) : '—')}</td>
          <td>${r.created_at.slice(0, 16).replace('T', ' ')}</td>
        </tr>`).join("")}
      </table>`;
    }

    function rateCell(id) {
      return `<span>` + [1,2,3,4,5].map(n =>
        `<a href="#" onclick="rate('${id}',${n});return false">${n}</a>`
      ).join(" ") + `</span>`;
    }

    async function rate(id, n) {
      await fetch(`/api/jobs/${id}/rate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rating: n }),
      });
      htmx.trigger("#jobs", "load");
    }

    function renderSchedules(rows) {
      if (!rows.length) return "<p>No schedules.</p>";
      return `<table>
        <tr><th>Schedule</th><th>Cron</th><th>Last run</th><th>30d</th>
            <th>Streak</th><th>Duration</th><th>Next</th></tr>
        ${rows.map(r => `<tr>
          <td>${esc(r.name)}${r.paused ? ' <span class="badge cancelled">paused</span>' : ''}${
            r.in_flight ? ` <span class="badge running">${r.in_flight} in flight</span>` : ''}</td>
          <td>${esc(r.cron)}</td>
          <td>${r.last_status
            ? `<span class="badge ${r.last_status}">${r.last_status}</span> ${
                r.last_finished_at ? r.last_finished_at.slice(0, 16).replace('T', ' ') : ''}`
            : '—'}</td>
          <td>${r.runs ? `${r.completed}/${r.runs} ok (${Math.round((r.success_rate ?? 0) * 100)}%)` : 'no runs'}</td>
          <td>${r.consecutive_failures
            ? `<span class="badge failed">${r.consecutive_failures} failing</span>` : '—'}</td>
          <td>${r.last_duration_s != null ? r.last_duration_s + 's' : '—'}${
            r.avg_duration_s != null ? ` (avg ${r.avg_duration_s}s)` : ''}</td>
          <td>${r.next_run_at ? r.next_run_at.slice(0, 16).replace('T', ' ') : '—'}</td>
        </tr>`).join("")}
      </table>`;
    }

    function renderProjects(rows) {
      if (!rows.length) return "<p>No projects yet. Try 'new project: <description>'.</p>";
      return `<table>
        <tr><th>Slug</th><th>Type</th><th>Delivery</th><th>URL</th><th>Port</th><th>Healthy</th></tr>
        ${rows.map(r => `<tr>
          <td>${r.slug}</td>
          <td>${r.type}</td>
          <td>${renderDelivery(r)}</td>
          <td><a href="https://${r.subdomain}" target="_blank">${r.subdomain}</a></td>
          <td>${r.port ?? '—'}</td>
          <td>${r.last_healthy_at?.slice(0, 19).replace('T', ' ') ?? '—'}</td>
        </tr>`).join("")}
      </table>`;
    }

    function renderDelivery(r) {
      if (r.topology === undefined || r.topology === null) return '—';
      const dep = r.deployable ? `deploy:${esc(r.deploy_autonomy || '?')}` : 'no-deploy';
      return `${esc(r.topology)} · ${dep}`;
    }

    function renderQuota(data) {
      const banner = document.getElementById("quota-banner");
      if (data && data.paused) {
        const resetStr = data.reset_at ? new Date(data.reset_at).toLocaleString() : "unknown";
        banner.textContent = `⏸ Queue paused on subscription quota. Reset at ${resetStr}. Reason: ${data.reason || '—'}`;
        banner.classList.add("visible");
      } else {
        banner.classList.remove("visible");
      }
    }

    function esc(s) { return (s || "").replace(/[<>&]/g, c => ({"<":"&lt;",">":"&gt;","&":"&amp;"}[c])); }
  </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse, dependencies=[Depends(_check_auth)])
async def index() -> str:
    return _INDEX_HTML
