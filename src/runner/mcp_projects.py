"""
In-process MCP server exposing project-related tools to skills that need them
(self-diagnose, review-and-improve, server-upkeep, server-patch).

Provides: list_projects, get_project, read_project_logs, restart_project.

Uses create_sdk_mcp_server() from the Claude Agent SDK. The server runs
in the runner process; no extra processes needed.
"""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path
from typing import Annotated, Any

from claude_agent_sdk import create_sdk_mcp_server, tool

from src.config import settings

logger = logging.getLogger(__name__)


# ── Pure helpers (tested directly) ─────────────────────────────────────────


def _format_project(row: dict[str, Any]) -> dict[str, Any]:
    """Format a project ORM row (as dict) for JSON output.

    Normalises types: UUID -> str, datetime -> ISO string or null.
    """
    last_healthy = row.get("last_healthy_at")
    return {
        "slug": str(row.get("slug", "")),
        "subdomain": str(row.get("subdomain", "")),
        "type": str(row.get("type", "")),
        "port": row.get("port"),
        "last_healthy_at": last_healthy.isoformat() if last_healthy else None,
    }


def _read_log_tail(log_path: Path, n: int = 100) -> str:
    """Read the last *n* lines from a log file. Pure function (no DB/subprocess).

    Returns the tail content as a string, or a user-friendly message if the
    file doesn't exist.
    """
    if not log_path.exists():
        return "No log file found."
    try:
        lines = log_path.read_text(errors="replace").splitlines()
        tail = lines[-n:] if n < len(lines) else lines
        return "\n".join(tail)
    except Exception as exc:
        return f"Error reading log: {exc}"


# ── MCP tool implementations ──────────────────────────────────────────────


@tool(
    "list_projects",
    "Return all registered projects with slug, subdomain, type, port, and last_healthy_at.",
    {},
)
async def list_projects_tool(args: dict[str, Any]) -> dict[str, Any]:
    from sqlalchemy import select

    from src.db import async_session
    from src.models import Project

    async with async_session() as session:
        result = await session.execute(select(Project))
        projects = result.scalars().all()

    formatted = [
        _format_project({
            "slug": p.slug,
            "subdomain": p.subdomain,
            "type": p.type,
            "port": p.port,
            "last_healthy_at": p.last_healthy_at,
        })
        for p in projects
    ]
    return {
        "content": [{"type": "text", "text": json.dumps(formatted, indent=2)}],
    }


@tool(
    "get_project",
    "Return a single project's full details including its manifest.yml content.",
    {"slug": Annotated[str, "Project slug identifier"]},
)
async def get_project_tool(args: dict[str, Any]) -> dict[str, Any]:
    from sqlalchemy import select

    from src.db import async_session
    from src.models import Project

    slug = args["slug"]
    async with async_session() as session:
        result = await session.execute(
            select(Project).where(Project.slug == slug)
        )
        project = result.scalar_one_or_none()

    if not project:
        return {
            "content": [{"type": "text", "text": f"No project found with slug: {slug}"}],
            "is_error": True,
        }

    info = _format_project({
        "slug": project.slug,
        "subdomain": project.subdomain,
        "type": project.type,
        "port": project.port,
        "last_healthy_at": project.last_healthy_at,
    })
    info["manifest_path"] = project.manifest_path

    # Read manifest content from disk
    manifest_content = ""
    manifest_path = Path(project.manifest_path)
    if manifest_path.exists():
        try:
            manifest_content = manifest_path.read_text()
        except Exception as exc:
            manifest_content = f"Error reading manifest: {exc}"
    else:
        manifest_content = f"Manifest file not found at {project.manifest_path}"
    info["manifest_content"] = manifest_content

    return {
        "content": [{"type": "text", "text": json.dumps(info, indent=2)}],
    }


@tool(
    "read_project_logs",
    "Read the last N lines of a project's stderr log.",
    {
        "slug": Annotated[str, "Project slug identifier"],
        "n": Annotated[int, "Number of lines to read (default 100)"],
    },
)
async def read_project_logs_tool(args: dict[str, Any]) -> dict[str, Any]:
    slug = args["slug"]
    n = args.get("n", 100)
    log_path = settings.logs_dir / f"project.{slug}.err.log"
    content = _read_log_tail(log_path, n)
    return {
        "content": [{"type": "text", "text": content}],
    }


@tool(
    "restart_project",
    "Restart a service-type project via launchctl kickstart.",
    {"slug": Annotated[str, "Project slug identifier"]},
)
async def restart_project_tool(args: dict[str, Any]) -> dict[str, Any]:
    slug = args["slug"]
    label = f"com.assistant.project.{slug}"
    try:
        uid = subprocess.check_output(["id", "-u"], text=True, timeout=5).strip()
        result = subprocess.run(
            ["launchctl", "kickstart", "-k", f"gui/{uid}/{label}"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            msg = f"Restart failed (exit {result.returncode}): {result.stderr.strip()}"
            logger.warning("restart_project %s: %s", slug, msg)
            return {"content": [{"type": "text", "text": msg}], "is_error": True}
        msg = f"Restarted {slug} successfully."
        logger.info("restart_project %s: OK", slug)
        return {"content": [{"type": "text", "text": msg}]}
    except subprocess.TimeoutExpired:
        return {"content": [{"type": "text", "text": f"Restart timed out for {slug}"}], "is_error": True}
    except Exception as exc:
        return {"content": [{"type": "text", "text": f"Restart error: {exc}"}], "is_error": True}


# ── Server factory ─────────────────────────────────────────────────────────


def create_server():
    """Return an McpSdkServerConfig for the projects MCP server."""
    return create_sdk_mcp_server(
        name="projects",
        version="0.1.0",
        tools=[
            list_projects_tool,
            get_project_tool,
            read_project_logs_tool,
            restart_project_tool,
        ],
    )
