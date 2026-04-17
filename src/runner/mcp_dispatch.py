"""
In-process MCP server exposing a dispatch tool so a parent skill can enqueue
a child job (fire-and-forget).

Used by self-diagnose, review-and-improve, and any skill tagged
"needs-dispatch-mcp" in its frontmatter.
"""

from __future__ import annotations

import logging
from typing import Annotated, Any

from claude_agent_sdk import create_sdk_mcp_server, tool

logger = logging.getLogger(__name__)


# ── Pure helpers (tested directly) ─────────────────────────────────────────


def _validate_enqueue_args(kind: str, description: str) -> list[str]:
    """Validate enqueue arguments. Returns a list of error strings (empty = valid)."""
    errors: list[str] = []
    if not isinstance(kind, str) or not kind.strip():
        errors.append("kind must be a non-empty string")
    if not isinstance(description, str) or not description.strip():
        errors.append("description must be a non-empty string")
    return errors


# ── MCP tool implementations ──────────────────────────────────────────────


@tool(
    "enqueue_job",
    "Enqueue a new job by kind and description. Returns the new job's ID.",
    {
        "kind": Annotated[str, "Job kind (e.g. 'task', 'research_report', 'app_patch')"],
        "description": Annotated[str, "Human-readable description of what to do"],
        "payload": Annotated[dict, "Optional extra payload for the job"],
    },
)
async def enqueue_job_tool(args: dict[str, Any]) -> dict[str, Any]:
    kind = args.get("kind", "")
    description = args.get("description", "")
    payload = args.get("payload")

    validation_errors = _validate_enqueue_args(kind, description)
    if validation_errors:
        return {
            "content": [{"type": "text", "text": f"Validation failed: {'; '.join(validation_errors)}"}],
            "is_error": True,
        }

    from src.gateway.jobs import enqueue_job

    job = await enqueue_job(
        description,
        kind=kind,
        payload=payload,
        created_by="dispatch-mcp",
    )
    job_id = str(job.id)
    logger.info("dispatch-mcp enqueued job %s (kind=%s)", job_id[:8], kind)
    return {
        "content": [{"type": "text", "text": job_id}],
    }


# ── Server factory ─────────────────────────────────────────────────────────


def create_server():
    """Return an McpSdkServerConfig for the dispatch MCP server."""
    return create_sdk_mcp_server(
        name="dispatch",
        version="0.1.0",
        tools=[enqueue_job_tool],
    )
