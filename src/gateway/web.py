"""
Web gateway. FastAPI.

Endpoints:
- GET  /                           — HTMX dashboard shell
- GET  /health                     — unauthenticated health probe
- POST /api/jobs                   — create a job (supports model/effort/permission in body)
- GET  /api/jobs                   — list jobs
- GET  /api/jobs/{id}              — job + audit log
- DELETE /api/jobs/{id}            — request cancel
- POST /api/jobs/{id}/rate         — submit a 1-5 rating
- GET  /api/projects               — list projects
- GET  /api/quota                  — { paused, reset_at, reason }
- GET  /api/retrospective/context  — context consumption rollup
- GET  /api/tasks                  — list tasks
- GET  /api/tasks/{id}             — task + turns

Run: uvicorn src.gateway.web:app --host 127.0.0.1 --port 8080
"""

from __future__ import annotations

import asyncio
import json
import secrets
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, Field
from sqlalchemy import select, update as sql_update
from sse_starlette.sse import EventSourceResponse

from src import audit_log
from src.config import settings
from src.db import CHANNEL_JOB_STREAM, async_session, redis
from src.gateway.jobs import cancel_job, enqueue_job, find_job_by_prefix
from src.models import Job, JobKind, JobStatus, Project, Task, TaskStatus, TaskTurn
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


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/api/jobs", dependencies=[Depends(_check_auth)])
async def create_job(req: CreateJobRequest) -> JobOut:
    payload = {}
    if req.model:
        payload["model"] = req.model
    if req.effort:
        payload["effort"] = req.effort
    if req.permission_mode:
        payload["permission_mode"] = req.permission_mode
    if req.project_slug:
        payload["project_slug"] = req.project_slug

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
    return await _get_projects()


@app.get("/api/projects/public")
async def list_projects_public() -> list[dict]:
    """Public endpoint — no auth. Returns only safe fields for the landing page."""
    return await _get_projects()


async def _get_projects() -> list[dict]:
    async with async_session() as s:
        result = await s.execute(select(Project).order_by(Project.slug))
        out = []
        for p in result.scalars():
            out.append({
                "slug": p.slug,
                "subdomain": p.subdomain,
                "type": p.type,
                "port": p.port,
                "last_healthy_at": p.last_healthy_at.isoformat() if p.last_healthy_at else None,
                "created_at": p.created_at.isoformat(),
            })
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

    function renderProjects(rows) {
      if (!rows.length) return "<p>No projects yet. Try 'new project: <description>'.</p>";
      return `<table>
        <tr><th>Slug</th><th>Type</th><th>URL</th><th>Port</th><th>Healthy</th></tr>
        ${rows.map(r => `<tr>
          <td>${r.slug}</td>
          <td>${r.type}</td>
          <td><a href="https://${r.subdomain}" target="_blank">${r.subdomain}</a></td>
          <td>${r.port ?? '—'}</td>
          <td>${r.last_healthy_at?.slice(0, 19).replace('T', ' ') ?? '—'}</td>
        </tr>`).join("")}
      </table>`;
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
