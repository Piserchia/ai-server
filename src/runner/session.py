"""
One function: `run_session(job)`. Spins up a Claude Agent SDK session, streams its
output to audit log + Redis, and returns a result dict or raises QuotaExhausted.

Auth: subscription via bundled Claude Code CLI. The bootstrap script unsets
ANTHROPIC_API_KEY before starting any process, so the SDK uses the CLI's stored
credentials from `claude login`.

Skill-driven config: the runner calls registry.skills.load() and uses the skill's
frontmatter for model/effort/permission_mode/required_tools.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    TextBlock,
    ThinkingBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)

from src import audit_log
from src.config import settings
from src.db import CHANNEL_JOB_DONE, CHANNEL_JOB_STREAM, async_session, redis
from src.models import Job, JobKind, Project
from src.registry.skills import SkillConfig, load as load_skill
from src.runner import quota, router

logger = logging.getLogger(__name__)

# ── MCP server opt-in sets ─────────────────────────────────────────────────
# Skills opt in by name here or via "needs-projects-mcp" / "needs-dispatch-mcp"
# tags in their SKILL.md frontmatter.

_NEEDS_PROJECTS_MCP = {"self-diagnose", "review-and-improve", "server-upkeep", "server-patch"}
_NEEDS_DISPATCH_MCP = {"self-diagnose", "review-and-improve"}


# In-process registry of running sessions for /cancel.
_running_sessions: dict[str, ClaudeSDKClient] = {}


async def interrupt(job_id: str | uuid.UUID) -> bool:
    client = _running_sessions.get(str(job_id))
    if not client:
        return False
    try:
        await client.interrupt()
        return True
    except Exception as exc:
        logger.warning("interrupt failed for %s: %s", job_id, exc)
        return False


# ── Skill resolution ────────────────────────────────────────────────────────


def _build_server_directive(skill_cfg: SkillConfig | None, cwd: Path) -> str:
    """Build a context-appropriate server preamble. Reduces token waste by
    tailoring the directive to the task type."""
    base = "You are working inside the assistant server.\n\n"

    # Chat: minimal directive
    if skill_cfg and skill_cfg.name == "chat":
        return base + "Respond directly. No tool use, no context reading needed.\n"

    # Project-scoped: point to project context
    if cwd != settings.server_root:
        project_slug = cwd.name
        directive = base + (
            f"This job is scoped to the `{project_slug}` project at `{cwd}`.\n"
            "Read that project's CLAUDE.md and .context/CONTEXT.md before acting.\n\n"
            "While working: prefer small committed steps. When you learn something "
            "non-obvious, append to the relevant skill file.\n\n"
            "Before finishing: update the project's .context/CHANGELOG.md. "
            "Write a one-paragraph summary as your final text message.\n"
        )
    else:
        # Server-scoped: full directive
        directive = base + (
            "Before acting:\n"
            "1. Read .context/SYSTEM.md and the relevant module CONTEXT.md.\n"
            "2. For debug/patch jobs, tail volumes/audit_log/*.jsonl for related work.\n\n"
            "While working: prefer small committed steps. When you learn something "
            "non-obvious, append to the relevant skill file (GOTCHAS.md / PATTERNS.md).\n\n"
            "Before finishing: update CHANGELOG.md for every module you touched. "
            "Write a one-paragraph summary as your final text message.\n"
        )

    # Append context_files reading list if the skill declares them
    if skill_cfg and skill_cfg.context_files:
        files_list = "\n".join(f"- `{f}`" for f in skill_cfg.context_files)
        directive += f"\n**Read these files first**:\n{files_list}\n"

    return directive


def _resolve_skill(job: Job) -> tuple[str, SkillConfig | None]:
    """
    Determine the skill for this job:
      - explicit kind (not "task" / "chat") → that skill
      - kind = "chat" → chat skill
      - kind = "task" → rule-based router on description; None means "generic task"
    Returns (skill_name_or_empty, SkillConfig_or_None).
    """
    if job.kind == JobKind.task.value:
        matched = router.route(job.description)
        if matched:
            return matched, load_skill(matched)
        return "", None   # generic task, use defaults + full tool set
    # Any other kind maps directly to a skill of the same name.
    # Underscores become dashes EXCEPT a leading underscore (marks internal skills):
    #   research_report → research-report
    #   _writeback      → _writeback   (leading _ preserved)
    skill_name = job.kind if job.kind.startswith("_") else job.kind.replace("_", "-")
    return skill_name, load_skill(skill_name)


def _build_options(job: Job, cwd: Path, skill_cfg: SkillConfig | None) -> ClaudeAgentOptions:
    """Assemble ClaudeAgentOptions. Skill frontmatter wins over server defaults."""
    # System prompt — context-aware preamble + skill body
    server_directive = _build_server_directive(skill_cfg, cwd)
    system_prompt = server_directive
    if skill_cfg and skill_cfg.body.strip():
        system_prompt = f"{server_directive}\n\n---\n\n# Active skill\n\n{skill_cfg.body}"

    # Model + effort + permission + tools
    model = (skill_cfg.model if skill_cfg and skill_cfg.model else settings.default_model)

    # Per-request overrides from job.payload take precedence over skill frontmatter
    payload = job.payload or {}
    if payload.get("model"):
        model = payload["model"]

    effort = payload.get("effort") or (skill_cfg.effort if skill_cfg else "medium")
    permission_mode = payload.get("permission_mode") or (
        skill_cfg.permission_mode if skill_cfg else "acceptEdits"
    )
    tools = (skill_cfg.required_tools if skill_cfg else [
        "Read", "Write", "Edit", "Bash", "Glob", "Grep",
        "WebSearch", "WebFetch", "AskUserQuestion",
    ])

    kwargs: dict[str, Any] = dict(
        cwd=str(cwd),
        system_prompt=system_prompt,
        allowed_tools=tools,
        permission_mode=permission_mode,
        setting_sources=["project"],   # picks up CLAUDE.md from cwd
        session_id=str(job.id),
        model=model,
    )
    if effort and effort != "medium":
        kwargs["effort"] = effort  # low | medium | high | xhigh | max
    if skill_cfg and skill_cfg.max_turns:
        kwargs["max_turns"] = skill_cfg.max_turns

    # ── MCP server injection ──────────────────────────────────────────
    # Skills opt in via _NEEDS_*_MCP sets (module-level) or tags in frontmatter.
    mcp_servers: dict[str, Any] = {}
    skill_name = skill_cfg.name if skill_cfg else ""
    skill_tags = skill_cfg.tags if skill_cfg else []

    if skill_name in _NEEDS_PROJECTS_MCP or "needs-projects-mcp" in skill_tags:
        from src.runner.mcp_projects import create_server as create_projects_mcp
        mcp_servers["projects"] = create_projects_mcp()

    if skill_name in _NEEDS_DISPATCH_MCP or "needs-dispatch-mcp" in skill_tags:
        from src.runner.mcp_dispatch import create_server as create_dispatch_mcp
        mcp_servers["dispatch"] = create_dispatch_mcp()

    if mcp_servers:
        kwargs["mcp_servers"] = mcp_servers

    return ClaudeAgentOptions(**kwargs)


async def _resolve_cwd(job: Job) -> Path:
    """Working directory for the session."""
    if job.project_id:
        async with async_session() as s:
            project = await s.get(Project, job.project_id)
            if project:
                p = settings.projects_dir / project.slug
                if p.exists():
                    return p
    slug = (job.payload or {}).get("project_slug")
    if slug and (settings.projects_dir / slug).exists():
        return settings.projects_dir / slug
    return settings.server_root


# ── Main entry ──────────────────────────────────────────────────────────────


async def run_session(job: Job) -> dict[str, Any]:
    job_id = str(job.id)
    skill_name, skill_cfg = _resolve_skill(job)
    cwd = await _resolve_cwd(job)
    options = _build_options(job, cwd, skill_cfg)

    # Record what was actually resolved, for the auto-tuning loop
    effort_used = (
        (job.payload or {}).get("effort")
        or (skill_cfg.effort if skill_cfg else "medium")
    )
    from sqlalchemy import update as sql_update
    async with async_session() as s:
        await s.execute(
            sql_update(Job).where(Job.id == job.id).values(
                resolved_skill=skill_name or None,
                resolved_model=options.model,
                resolved_effort=effort_used,
            )
        )
        await s.commit()

    audit_log.append(
        job_id,
        "job_started",
        description=job.description,
        job_kind=job.kind,
        skill=skill_name,
        cwd=str(cwd),
        model=options.model,
        effort=effort_used,
        payload=job.payload,
    )

    started_at = datetime.now(timezone.utc)
    final_text_chunks: list[str] = []
    usage: dict[str, Any] = {}

    client = ClaudeSDKClient(options=options)
    _running_sessions[job_id] = client

    try:
        async with client:
            await client.query(job.description)

            async for message in client.receive_response():
                # Check for quota/rate-limit error inside a message
                err = getattr(message, "error", None)
                if err:
                    detected = quota.detect_quota_error(str(err))
                    if detected is not None:
                        reset_at = detected if isinstance(detected, datetime) else None
                        raise quota.QuotaExhausted(reset_at, reason=str(err)[:500])

                await _handle_message(job_id, message, final_text_chunks)

                if isinstance(message, ResultMessage):
                    usage = getattr(message, "usage", {}) or {}

        final_summary = "\n".join(final_text_chunks).strip()
        if final_summary:
            audit_log.write_summary(job_id, final_summary)

        duration = (datetime.now(timezone.utc) - started_at).total_seconds()
        audit_log.append(
            job_id,
            "job_completed",
            duration_seconds=duration,
            usage=usage,
        )

        return {
            "summary": final_summary,
            "duration_seconds": duration,
            "usage": usage,
            "skill": skill_name,
        }
    finally:
        _running_sessions.pop(job_id, None)


# ── Message handler ─────────────────────────────────────────────────────────


async def _handle_message(
    job_id: str, message: Any, final_text_chunks: list[str]
) -> None:
    if isinstance(message, AssistantMessage):
        for block in message.content:
            if isinstance(block, TextBlock):
                audit_log.append(job_id, "text", text=block.text)
                final_text_chunks.append(block.text)
                await _publish_stream(job_id, {"kind": "text", "text": block.text})
            elif isinstance(block, ToolUseBlock):
                audit_log.append(
                    job_id, "tool_use",
                    tool_name=block.name,
                    tool_use_id=block.id,
                    input=_truncate_for_log(block.input),
                )
                await _publish_stream(
                    job_id,
                    {"kind": "tool_use", "tool_name": block.name, "tool_use_id": block.id},
                )
            elif isinstance(block, ThinkingBlock):
                audit_log.append(job_id, "thinking", text=block.thinking)

    elif isinstance(message, UserMessage):
        for block in message.content:
            if isinstance(block, ToolResultBlock):
                audit_log.append(
                    job_id, "tool_result",
                    tool_use_id=block.tool_use_id,
                    is_error=bool(block.is_error),
                    result_preview=_preview_text(block.content),
                )


def _truncate_for_log(value: Any, limit: int = 2000) -> Any:
    if isinstance(value, str) and len(value) > limit:
        return value[:limit] + f"... [{len(value) - limit} chars truncated]"
    if isinstance(value, dict):
        return {k: _truncate_for_log(v, limit) for k, v in value.items()}
    if isinstance(value, list):
        return [_truncate_for_log(v, limit) for v in value[:20]]
    return value


def _preview_text(content: Any, limit: int = 500) -> str:
    try:
        s = content if isinstance(content, str) else json.dumps(content, default=str)
    except Exception:
        s = str(content)
    return s[:limit] + (f"... [{len(s) - limit} more]" if len(s) > limit else "")


async def _publish_stream(job_id: str, payload: dict[str, Any]) -> None:
    try:
        await redis.publish(f"{CHANNEL_JOB_STREAM}:{job_id}", json.dumps(payload))
    except Exception:
        pass


async def publish_done(job_id: str, status: str, payload: dict[str, Any] | None = None) -> None:
    body = json.dumps({"status": status, **(payload or {})}, default=str)
    try:
        await redis.publish(f"{CHANNEL_JOB_DONE}:{job_id}", body)
    except Exception:
        pass
