"""
In-process MCP server exposing a dispatch tool so a parent skill can enqueue
a child job.

Used by self-diagnose, review-and-improve, and any skill tagged
"needs-dispatch-mcp" in its frontmatter.

P2: child jobs are linked to the spawning job (parent_job_id) and its task
(task_id) so dispatched work shows up in the task thread instead of floating
free, and `depends_on` lets a session build a dependency chain (dependent
jobs are created `deferred` and promoted by the runner when their
dependencies complete — see runner/plans.py).
"""

from __future__ import annotations

import logging
from typing import Annotated, Any

from claude_agent_sdk import create_sdk_mcp_server, tool

logger = logging.getLogger(__name__)


# ── Pure helpers (tested directly) ─────────────────────────────────────────


# Kinds no session may dispatch (2026-08-31, EVALUATION_2026-08-30 F1.3):
# `god` is the owner-invoked break-glass — reachable ONLY via Telegram /god.
# Before this check, any skill holding the dispatch MCP could enqueue a
# kind='god' job and inherit host isolation + bypassPermissions.
_FORBIDDEN_KINDS = frozenset({"god"})

# Payload keys a dispatching session may not set: isolation and permission
# escalation belong to the target skill's frontmatter, not the caller.
# (session.resolve_isolation independently ignores loosening overrides —
# this strip just makes the refusal visible at enqueue time.)
_STRIPPED_PAYLOAD_KEYS = frozenset({"isolation", "permission_mode", "permission"})


def _validate_enqueue_args(kind: str, description: str) -> list[str]:
    """Validate enqueue arguments. Returns a list of error strings (empty = valid)."""
    errors: list[str] = []
    if not isinstance(kind, str) or not kind.strip():
        errors.append("kind must be a non-empty string")
    elif kind.strip().lower() in _FORBIDDEN_KINDS:
        errors.append(f"kind '{kind.strip()}' is owner-invoked only (use Telegram /god)")
    if not isinstance(description, str) or not description.strip():
        errors.append("description must be a non-empty string")
    return errors


def _sanitize_payload(payload: dict) -> tuple[dict, list[str]]:
    """Drop privilege-bearing keys from a dispatched payload.

    Returns (clean_payload, stripped_key_names). Pure.
    """
    stripped = sorted(k for k in payload if k in _STRIPPED_PAYLOAD_KEYS)
    return {k: v for k, v in payload.items() if k not in _STRIPPED_PAYLOAD_KEYS}, stripped


# ── Server factory ─────────────────────────────────────────────────────────
#
# The tool is built inside the factory so each session's dispatch server
# captures ITS job's context in a closure — a module-level context var would
# be shared mutable state across up to MAX_CONCURRENT_JOBS sessions.


def create_server(spawning_job=None):
    """Return an McpSdkServerConfig for the dispatch MCP server.

    spawning_job: the Job this session is running (optional for backward
    compatibility). When given, children inherit task_id and get
    parent_job_id automatically.
    """
    spawner_task_id = getattr(spawning_job, "task_id", None)
    spawner_job_id = getattr(spawning_job, "id", None)

    @tool(
        "enqueue_job",
        "Enqueue a new job by kind and description. Returns the new job's ID. "
        "Pass depends_on=[job ids] to defer this job until those complete.",
        {
            "kind": Annotated[str, "Job kind (e.g. 'task', 'research_report', 'app_patch')"],
            "description": Annotated[str, "Human-readable description of what to do"],
            "payload": Annotated[dict, "Optional extra payload for the job"],
            "depends_on": Annotated[list, "Optional job IDs that must complete first"],
        },
    )
    async def enqueue_job_tool(args: dict[str, Any]) -> dict[str, Any]:
        kind = args.get("kind", "")
        description = args.get("description", "")
        payload = dict(args.get("payload") or {})
        depends_on = [str(d) for d in (args.get("depends_on") or []) if str(d).strip()]

        payload, stripped_keys = _sanitize_payload(payload)
        if stripped_keys:
            logger.warning("dispatch-mcp stripped privileged payload keys %s "
                           "(kind=%s, spawner=%s)", stripped_keys, kind,
                           str(spawner_job_id)[:8] if spawner_job_id else "?")

        validation_errors = _validate_enqueue_args(kind, description)
        if validation_errors:
            return {
                "content": [{"type": "text", "text": f"Validation failed: {'; '.join(validation_errors)}"}],
                "is_error": True,
            }

        if depends_on:
            # Deferred creation: row only, no queue push — the runner promotes
            # it when the dependencies complete (runner/plans.py).
            payload["depends_on"] = depends_on
            from src.db import async_session
            from src.models import Job, JobStatus
            job = Job(
                kind=kind,
                description=description,
                payload=payload,
                status=JobStatus.deferred.value,
                created_by="dispatch-mcp",
                task_id=spawner_task_id,
                parent_job_id=spawner_job_id,
            )
            async with async_session() as s:
                s.add(job)
                await s.commit()
                await s.refresh(job)
        else:
            from src.gateway.jobs import enqueue_job
            job = await enqueue_job(
                description,
                kind=kind,
                payload=payload or None,
                created_by="dispatch-mcp",
                task_id=spawner_task_id,
                parent_job_id=spawner_job_id,
            )
        job_id = str(job.id)
        logger.info("dispatch-mcp enqueued job %s (kind=%s, deferred=%s)",
                    job_id[:8], kind, bool(depends_on))
        return {
            "content": [{"type": "text", "text": job_id}],
        }

    return create_sdk_mcp_server(
        name="dispatch",
        version="0.1.0",
        tools=[enqueue_job_tool],
    )
