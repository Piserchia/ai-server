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


def _build_server_directive(
    skill_cfg: SkillConfig | None,
    cwd: Path,
    job_description: str = "",
) -> str:
    """Build a context-appropriate server preamble. Reduces token waste by
    tailoring the directive to the task type."""
    base = "You are working inside the assistant server.\n\n"

    # Chat: minimal directive
    if skill_cfg and skill_cfg.name == "chat":
        return base + "Respond directly. No tool use, no context reading needed.\n"

    # Project-scoped: point to project context + project protocol
    if cwd != settings.server_root:
        project_slug = cwd.name
        directive = base + (
            f"This job is scoped to the `{project_slug}` project at `{cwd}`.\n"
            "Follow the project protocol at `.context/PROJECT_PROTOCOL.md` "
            "(in the ai-server root).\n\n"
            "Read that project's CLAUDE.md and .context/CONTEXT.md before acting.\n\n"
            "While working: prefer small committed steps. When you learn something "
            "non-obvious, append to the project's skills/GOTCHAS.md.\n\n"
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

        # Graph-walked context injection (Rec 4): if the job description
        # references known modules, append dependency context so the session
        # knows what else to check before making changes.
        if job_description:
            directive += _module_dependency_context(job_description)
            directive += _module_knowledge_context(job_description)

    # Append context_files reading list if the skill declares them
    if skill_cfg and skill_cfg.context_files:
        files_list = "\n".join(f"- `{f}`" for f in skill_cfg.context_files)
        directive += f"\n**Read these files first**:\n{files_list}\n"

    return directive


def _module_dependency_context(job_description: str) -> str:
    """If the job description mentions known modules, return a brief dependency
    note. Returns empty string if no modules detected or graph unavailable."""
    try:
        from src.context.module_graph import (
            detect_modules_in_text,
            parse_module_graph,
            reverse_graph,
        )
        system_md = (settings.server_root / ".context" / "SYSTEM.md").read_text()
        graph = parse_module_graph(system_md)
        if not graph:
            return ""
        rev = reverse_graph(graph)
        mentioned = detect_modules_in_text(job_description, set(graph.keys()))
        if not mentioned:
            return ""

        lines = ["\n**Module dependencies** (auto-detected from your task):"]
        for mod in sorted(mentioned):
            dependents = rev.get(mod, [])
            if dependents:
                dep_str = ", ".join(sorted(dependents))
                lines.append(
                    f"- `{mod}` is depended on by: {dep_str}. "
                    f"Read their CONTEXT.md before changing its API."
                )
            else:
                lines.append(f"- `{mod}` has no dependents in the graph.")
        lines.append("")
        return "\n".join(lines)
    except Exception:
        return ""


def parse_skill_file_entries(text: str) -> list[str]:
    """Parse entry titles from a module skills file (GOTCHAS.md, DEBUG.md, etc.).

    Entries start with '## ' after the APPEND_ENTRIES_BELOW marker.
    Returns a list of entry titles (the text after '## ').
    Pure function.
    """
    titles: list[str] = []
    after_marker = False
    for line in text.splitlines():
        if "APPEND_ENTRIES_BELOW" in line:
            after_marker = True
            continue
        if after_marker and line.startswith("## "):
            title = line[3:].strip()
            # Strip date prefix if present (e.g., "2026-04-20 — Title")
            if " — " in title:
                title = title.split(" — ", 1)[1]
            if title:
                titles.append(title)
    return titles


def _module_knowledge_context(job_description: str) -> str:
    """If the job description mentions known modules, surface relevant
    GOTCHAS and DEBUG entries from those modules' skill files.

    Returns a compact section with entry titles only (not full bodies)
    to keep token budget low. Returns empty string if nothing found.
    """
    try:
        from src.context.module_graph import detect_modules_in_text, parse_module_graph
        system_md = (settings.server_root / ".context" / "SYSTEM.md").read_text()
        graph = parse_module_graph(system_md)
        if not graph:
            return ""
        mentioned = detect_modules_in_text(job_description, set(graph.keys()))
        if not mentioned:
            return ""

        # Map module shorthands to top-level module names (runner, gateway, db, etc.)
        module_dirs: set[str] = set()
        for mod in mentioned:
            top = mod.split(".")[0]
            module_dir = settings.server_root / ".context" / "modules" / top / "skills"
            if module_dir.exists():
                module_dirs.add(top)

        if not module_dirs:
            return ""

        sections: list[str] = []
        for mod_name in sorted(module_dirs):
            skills_dir = settings.server_root / ".context" / "modules" / mod_name / "skills"
            entries: list[tuple[str, str]] = []  # (category, title)
            for fname in ("GOTCHAS.md", "DEBUG.md"):
                fpath = skills_dir / fname
                if not fpath.exists():
                    continue
                titles = parse_skill_file_entries(fpath.read_text())
                category = fname.replace(".md", "").lower()
                for t in titles:
                    entries.append((category, t))

            if entries:
                items = "\n".join(
                    f"  - [{cat}] {title}" for cat, title in entries
                )
                sections.append(f"- **{mod_name}**:\n{items}")

        if not sections:
            return ""

        return "\n**Known issues** (from module skill files):\n" + "\n".join(sections) + "\n"
    except Exception:
        return ""


# ── Task context (multi-turn) ──────────────────────────────────────────────


def format_task_turns(turns: list[dict]) -> str:
    """Format task turns into a compact conversation summary.

    turns: list of {"turn_number": int, "role": str, "content": str, "job_id": str|None}
    Pure function.
    """
    if not turns:
        return ""
    lines: list[str] = []
    for t in turns:
        role = t["role"]
        content = t["content"]
        job_ref = f", job {t['job_id'][:8]}" if t.get("job_id") else ""
        # Truncate long content to keep context budget reasonable
        if len(content) > 500:
            content = content[:500] + "..."
        lines.append(f"**Turn {t['turn_number']} ({role}{job_ref})**: {content}")
    return "\n\n".join(lines)


def _build_task_context(task_id) -> str:
    """Load prior turns for a task and format as conversation context.

    Returns a markdown section to prepend to the system prompt, or empty
    string if no prior turns exist.
    """
    try:
        from src.models import TaskTurn
        import uuid as _uuid

        tid = task_id if isinstance(task_id, _uuid.UUID) else _uuid.UUID(str(task_id))

        # Synchronous-safe: use a new event loop or run in the existing one.
        # Since this is called from an async context (via _build_options which
        # is sync but called from async _process_job), we use a sync query path.
        # For simplicity, read from DB synchronously via a helper.
        import asyncio
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # We're inside an async context — schedule the coroutine
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                turns_data = pool.submit(
                    lambda: asyncio.run(_fetch_task_turns(tid))
                ).result(timeout=5)
        else:
            turns_data = asyncio.run(_fetch_task_turns(tid))

        if not turns_data:
            return ""

        formatted = format_task_turns(turns_data)
        task_id_short = str(tid)[:8]
        return (
            f"## Task conversation ({task_id_short})\n\n"
            f"{formatted}\n\n"
            "---\n"
            "Continue from where the previous turn left off. "
            "If you need more information from the user, emit a "
            "`task_question` audit event and complete normally.\n"
        )
    except Exception:
        return ""


async def _fetch_task_turns(task_id) -> list[dict]:
    """Fetch task turns from DB. Returns list of dicts."""
    from src.models import TaskTurn
    from sqlalchemy import select

    async with async_session() as s:
        result = await s.execute(
            select(
                TaskTurn.turn_number,
                TaskTurn.role,
                TaskTurn.content,
                TaskTurn.job_id,
            )
            .where(TaskTurn.task_id == task_id)
            .order_by(TaskTurn.turn_number)
        )
        return [
            {
                "turn_number": row.turn_number,
                "role": row.role,
                "content": row.content,
                "job_id": str(row.job_id) if row.job_id else None,
            }
            for row in result.all()
        ]


# ── Budget accounting (Rec 8) ──────────────────────────────────────────────

# Approximate context windows by model family (input tokens).
_MODEL_BUDGETS: dict[str, int] = {
    "claude-haiku-4-5-20251001": 200_000,
    "claude-sonnet-4-6": 200_000,
    "claude-opus-4-7": 200_000,
}
_DEFAULT_BUDGET = 200_000


def estimate_context_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token. Pure function."""
    return len(text) // 4


def context_budget_fraction(
    system_prompt: str,
    model: str,
) -> tuple[int, int, float]:
    """Return (estimated_tokens, model_budget, fraction). Pure function."""
    tokens = estimate_context_tokens(system_prompt)
    budget = _MODEL_BUDGETS.get(model, _DEFAULT_BUDGET)
    return tokens, budget, tokens / budget if budget > 0 else 0.0


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
    # System prompt — context-aware preamble + skill body + task context
    server_directive = _build_server_directive(skill_cfg, cwd, job.description)
    system_prompt = server_directive

    # Multi-turn task context injection
    if job.task_id:
        task_ctx = _build_task_context(job.task_id)
        if task_ctx:
            system_prompt += f"\n{task_ctx}\n"

    if skill_cfg and skill_cfg.body.strip():
        system_prompt = f"{system_prompt}\n\n---\n\n# Active skill\n\n{skill_cfg.body}"

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
    # Skills opt in via "needs-projects-mcp" / "needs-dispatch-mcp" tags
    # in their SKILL.md frontmatter. Tags are the sole source of truth.
    mcp_servers: dict[str, Any] = {}
    skill_tags = skill_cfg.tags if skill_cfg else []

    if "needs-projects-mcp" in skill_tags:
        from src.runner.mcp_projects import create_server as create_projects_mcp
        mcp_servers["projects"] = create_projects_mcp()

    if "needs-dispatch-mcp" in skill_tags:
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

    # Log context budget usage (Rec 8)
    ctx_tokens, ctx_budget, ctx_fraction = context_budget_fraction(
        options.system_prompt or "", options.model or "",
    )
    audit_log.append(
        job_id,
        "context_budget_used",
        estimated_tokens=ctx_tokens,
        model_budget=ctx_budget,
        fraction=round(ctx_fraction, 4),
        skill=skill_name,
    )

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
        parent_job_id=str(job.parent_job_id) if job.parent_job_id else None,
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
