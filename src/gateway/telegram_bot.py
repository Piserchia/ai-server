"""
Telegram gateway. Commands: /task /status /jobs /help /chat /resume /schedule.
Thread-based: reply in task threads to continue. Inline buttons for actions.

Flag syntax (parsed off the front of /task and /chat descriptions):
    /task --model=opus-4-7 --effort=high  fix the NaN bug in market-tracker
    /task --effort=max  design the props model schema

Flags land in job.payload and take precedence over skill frontmatter.

Run: `python -m src.gateway.telegram_bot`
"""

from __future__ import annotations

import asyncio
import functools
import json
import logging
import re
import traceback
import uuid

import structlog
from sqlalchemy import select, update as sql_update
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from src.config import settings
from src.db import CHANNEL_JOB_DONE, async_session, redis
from src.gateway.jobs import cancel_job, enqueue_job, find_job_by_prefix
from src.models import Job, JobKind, JobStatus, Project, Schedule, Task, TaskStatus, TaskTurn
from src.runner import quota

logger = structlog.get_logger()

# In-memory: maps job_id → chat_id so we know where to send the result
_job_to_chat: dict[str, int] = {}


def _is_authorized(chat_id: int) -> bool:
    allowed = settings.allowed_chat_ids
    return bool(allowed) and chat_id in allowed


async def _guard(update: Update) -> int | None:
    chat_id = update.effective_chat.id
    if not _is_authorized(chat_id):
        await update.message.reply_text(
            "Not authorized. Add your chat ID to TELEGRAM_ALLOWED_CHAT_IDS."
        )
        return None
    return chat_id


# ── Helpers ────────────────────────────────────────────────────────────────


def _esc_md(text: str) -> str:
    """Escape Telegram Markdown v1 special characters in user-supplied text."""
    for ch in ("_", "*", "`", "["):
        text = text.replace(ch, f"\\{ch}")
    return text


def _error_safe(handler):
    """Wrap a command handler with 4-level error handling.
    Level 1: Reply with error. Level 2: Auto-retry (1x).
    Level 3: Dispatch self-diagnose. Level 4: Graceful degradation.
    """
    @functools.wraps(handler)
    async def wrapper(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            return await handler(update, ctx)
        except Exception as first_exc:
            # Level 1+2: Reply with error + retry once
            try:
                await update.message.reply_text(
                    f"\u26a0\ufe0f Retrying... ({type(first_exc).__name__})"
                )
                await asyncio.sleep(1)
                return await handler(update, ctx)
            except Exception as retry_exc:
                # Level 3: Dispatch self-diagnose
                tb = traceback.format_exc()
                try:
                    await enqueue_job(
                        f"Self-diagnose: Telegram handler '{handler.__name__}' "
                        f"failed twice. Error: {str(retry_exc)[:200]}",
                        kind="self-diagnose",
                        payload={
                            "target_kind": "bot",
                            "error": str(retry_exc)[:500],
                            "traceback": tb[:1000],
                            "handler": handler.__name__,
                        },
                        created_by="bot-error-handler",
                    )
                    await update.message.reply_text(
                        "\u26a0\ufe0f Failed after retry. Auto-diagnosing...\n"
                        "I've dispatched a self-diagnose job to investigate."
                    )
                except Exception:
                    # Level 4: Graceful degradation
                    await update.message.reply_text(
                        f"\u26a0\ufe0f System error: {type(retry_exc).__name__}\n"
                        "Try again in a few minutes."
                    )
    return wrapper


# ── Flag parsing ────────────────────────────────────────────────────────────

_FLAG_RE = re.compile(r"--(\w+)=(\S+)")

# Model alias expansion — accepts short names on the command line
_MODEL_ALIASES = {
    "opus": "claude-opus-4-7",
    "opus-4-7": "claude-opus-4-7",
    "opus-4-6": "claude-opus-4-6",
    "sonnet": "claude-sonnet-4-6",
    "sonnet-4-6": "claude-sonnet-4-6",
    "haiku": "claude-haiku-4-5-20251001",
    "haiku-4-5": "claude-haiku-4-5-20251001",
}

_VALID_EFFORTS = {"low", "medium", "high", "xhigh", "max"}
_VALID_PERMISSIONS = {"default", "acceptEdits", "bypassPermissions", "plan"}


def parse_flags(text: str) -> tuple[str, dict]:
    """
    Extract --flag=value tokens from the front of a description.
    Returns (cleaned_description, flags_dict).

    Supported flags: --model, --effort, --permission, --project, --kind.
    Unknown flags are left in the description (caller can decide to reject).
    """
    flags: dict = {}
    tokens = text.strip().split()
    consumed = 0
    for tok in tokens:
        m = _FLAG_RE.match(tok)
        if not m:
            break   # stop at first non-flag; description starts here
        key, val = m.group(1), m.group(2)
        if key == "model":
            flags["model"] = _MODEL_ALIASES.get(val.lower(), val)
        elif key == "effort":
            if val.lower() in _VALID_EFFORTS:
                flags["effort"] = val.lower()
        elif key == "permission":
            if val in _VALID_PERMISSIONS:
                flags["permission_mode"] = val
        elif key == "project":
            flags["project_slug"] = val
        elif key == "kind":
            flags["kind_override"] = val
        else:
            break   # unknown flag — stop parsing, treat rest as description
        consumed += 1
    remaining = " ".join(tokens[consumed:])
    return remaining, flags


# ── Commands ────────────────────────────────────────────────────────────────


@_error_safe
async def cmd_help(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    if await _guard(update) is None:
        return
    await update.message.reply_text(
        "*Commands:*\n\n"
        "/task <description> — start a new task\n"
        "  _Reply in the thread to continue. Buttons for actions._\n\n"
        "/status — see active tasks\n"
        "/jobs — see recent job runs\n"
        "/help — this message\n\n"
        "_Admin: /chat, /resume, /clear, /schedule_",
        parse_mode="Markdown",
    )


@_error_safe
async def cmd_task(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = await _guard(update)
    if chat_id is None:
        return
    raw = " ".join(ctx.args).strip()
    if not raw:
        await update.message.reply_text("Usage: /task [flags] <what you want me to do>")
        return

    description, flags = parse_flags(raw)
    if not description:
        await update.message.reply_text(
            "Flags parsed but no description remaining. Put the task after the flags."
        )
        return

    # Optional kind override from flags (e.g., --kind=research_deep)
    kind = flags.pop("kind_override", JobKind.task.value)

    # Create a Task to wrap this job (enables multi-turn interaction)
    task = Task(
        description=description,
        created_by=f"telegram:{chat_id}",
        chat_id=chat_id,
    )
    async with async_session() as s:
        s.add(task)
        await s.commit()
        await s.refresh(task)

    # Record the initial user turn
    async with async_session() as s:
        s.add(TaskTurn(
            task_id=task.id,
            turn_number=1,
            role="user",
            content=description,
        ))
        await s.commit()

    job = await enqueue_job(
        description,
        kind=kind,
        payload=flags or None,
        created_by=f"telegram:{chat_id}",
    )
    # Link job to task
    async with async_session() as s:
        await s.execute(
            sql_update(Job).where(Job.id == job.id).values(task_id=task.id)
        )
        await s.commit()

    _job_to_chat[str(job.id)] = chat_id

    # Reply in thread with [Cancel] button
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("Cancel", callback_data=f"cancel:{str(task.id)[:8]}"),
    ]])
    reply = await update.message.reply_text(
        f"\U0001f504 Working on it... ({_esc_md(description[:60])})",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )
    # Save thread_message_id
    async with async_session() as s:
        await s.execute(sql_update(Task).where(Task.id == task.id).values(
            thread_message_id=reply.message_id))
        await s.commit()


@_error_safe
async def cmd_chat(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = await _guard(update)
    if chat_id is None:
        return
    raw = " ".join(ctx.args).strip()
    if not raw:
        await update.message.reply_text("Usage: /chat <your message>")
        return

    description, flags = parse_flags(raw)
    job = await enqueue_job(
        description,
        kind=JobKind.chat.value,
        payload=flags or None,
        created_by=f"telegram:{chat_id}",
    )
    _job_to_chat[str(job.id)] = chat_id
    await update.message.reply_text(f"Thinking... ({str(job.id)[:8]})")


@_error_safe
async def cmd_status(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """Show active tasks with status icons and inline prompts."""
    if await _guard(update) is None:
        return

    active_statuses = [
        TaskStatus.active.value,
        TaskStatus.awaiting_user.value,
        TaskStatus.pending_approval.value,
    ]
    async with async_session() as s:
        result = await s.execute(
            select(Task)
            .where(Task.status.in_(active_statuses))
            .order_by(Task.created_at.desc())
            .limit(15)
        )
        tasks = list(result.scalars().all())

    if not tasks:
        await update.message.reply_text("No active tasks. Start one with /task.")
        return

    status_icons = {"active": "\U0001f504", "awaiting_user": "\u2753", "pending_approval": "\u270b"}
    lines = [f"*Active tasks ({len(tasks)}):*\n"]
    for t in tasks:
        prefix = str(t.id)[:8]
        desc = _esc_md(t.description[:50])
        icon = status_icons.get(t.status, "")
        lines.append(f"`{prefix}` {icon} {desc}")
        if t.status == TaskStatus.awaiting_user.value:
            lines.append("  _Reply in thread to answer_")
        elif t.status == TaskStatus.pending_approval.value:
            lines.append("  _Tap Approve in thread_")
        elif t.status == TaskStatus.active.value:
            lines.append("  _Running..._")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if await _guard(update) is None:
        return
    if not ctx.args:
        await update.message.reply_text("Usage: /cancel <job_id_prefix>")
        return
    job = await find_job_by_prefix(ctx.args[0])
    if not job:
        await update.message.reply_text("Job not found.")
        return
    if JobStatus(job.status).is_terminal:
        await update.message.reply_text(f"Job is already {job.status}.")
        return
    await cancel_job(job.id)
    await update.message.reply_text(
        f"Cancel requested for `{str(job.id)[:8]}`.", parse_mode="Markdown"
    )


async def cmd_rate(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if await _guard(update) is None:
        return
    if len(ctx.args) < 2:
        await update.message.reply_text("Usage: /rate <job_id_prefix> <1-5>")
        return
    job = await find_job_by_prefix(ctx.args[0])
    if not job:
        await update.message.reply_text("Job not found.")
        return
    try:
        rating = int(ctx.args[1])
    except ValueError:
        await update.message.reply_text("Rating must be an integer 1-5.")
        return
    if rating < 1 or rating > 5:
        await update.message.reply_text("Rating must be 1-5.")
        return

    async with async_session() as s:
        await s.execute(
            sql_update(Job).where(Job.id == job.id).values(user_rating=rating)
        )
        await s.commit()

    await update.message.reply_text(
        f"Rated {str(job.id)[:8]} as {rating}/5. Feeds the monthly review-and-improve pass."
    )


@_error_safe
async def cmd_projects(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    if await _guard(update) is None:
        return
    async with async_session() as s:
        result = await s.execute(select(Project).order_by(Project.slug))
        rows = list(result.scalars())
    if not rows:
        await update.message.reply_text(
            "No projects yet. Try `/task new project: <description>`.",
            parse_mode="Markdown",
        )
        return
    lines = ["*Projects:*"]
    for p in rows:
        health = "✓" if p.last_healthy_at else "?"
        lines.append(f"{health} `{p.slug}` → https://{p.subdomain}")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


@_error_safe
async def cmd_resume(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    if await _guard(update) is None:
        return
    paused, reset_at, reason = await quota.is_paused()
    if not paused:
        await update.message.reply_text("Queue is not paused.")
        return
    await quota.clear()
    await update.message.reply_text(
        f"Queue manually resumed (was paused for: {reason[:100]})."
    )


@_error_safe
async def cmd_clear(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """Cancel all queued/running jobs and fail all active tasks."""
    if await _guard(update) is None:
        return

    async with async_session() as s:
        # Cancel queued + running jobs
        result = await s.execute(
            sql_update(Job)
            .where(Job.status.in_([JobStatus.queued.value, JobStatus.running.value]))
            .values(status=JobStatus.cancelled.value)
        )
        jobs_cleared = result.rowcount or 0

        # Fail active + awaiting tasks
        result = await s.execute(
            sql_update(Task)
            .where(Task.status.in_([
                TaskStatus.active.value,
                TaskStatus.awaiting_user.value,
                TaskStatus.pending_approval.value,
            ]))
            .values(status=TaskStatus.failed.value)
        )
        tasks_cleared = result.rowcount or 0
        await s.commit()

    # Flush the Redis queue
    await redis.delete("jobs:queue")

    await update.message.reply_text(
        f"Cleared {jobs_cleared} job(s) and {tasks_cleared} task(s)."
    )


async def cmd_proposals(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """List tuning/doc proposals emitted by review-and-improve.

    Usage:
      /proposals              — list pending proposals
      /proposals 30d          — list all proposals in last 30 days with outcome
      /proposals <id_prefix>  — show details for one proposal
    """
    if await _guard(update) is None:
        return
    from src.runner.proposals import (
        format_proposal_line,
        get_proposal_by_id_prefix,
        list_pending_proposals,
        list_recent_proposals,
    )

    args = ctx.args or []

    if not args:
        rows = await list_pending_proposals(limit=40)
        if not rows:
            await update.message.reply_text("No pending proposals.")
            return
        header = f"*Pending proposals* ({len(rows)}):"
        lines = [header, "```"]
        for p in rows:
            lines.append(format_proposal_line(p.id, p.target_file, p.change_type, p.outcome, p.proposed_at))
        lines.append("```")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
        return

    arg = args[0]

    if arg.endswith("d") and arg[:-1].isdigit():
        days = int(arg[:-1])
        rows = await list_recent_proposals(lookback_days=days, limit=50)
        if not rows:
            await update.message.reply_text(f"No proposals in last {days} days.")
            return
        header = f"*Proposals (last {days}d)* ({len(rows)}):"
        lines = [header, "```"]
        for p in rows:
            lines.append(format_proposal_line(p.id, p.target_file, p.change_type, p.outcome, p.proposed_at))
        lines.append("```")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
        return

    prop = await get_proposal_by_id_prefix(arg)
    if not prop:
        await update.message.reply_text(
            f"No proposal matching `{arg}` (or ambiguous prefix).",
            parse_mode="Markdown",
        )
        return
    lines = [
        f"*Proposal* `{str(prop.id)[:8]}`",
        f"*target*: `{prop.target_file}`",
        f"*change_type*: `{prop.change_type}`",
        f"*outcome*: `{prop.outcome}`",
        f"*proposed_by_job*: `{str(prop.proposed_by_job_id)[:8]}`",
        f"*proposed_at*: {prop.proposed_at.isoformat(timespec='seconds')}",
    ]
    if prop.applied_at:
        lines.append(f"*applied_at*: {prop.applied_at.isoformat(timespec='seconds')}")
    if prop.applied_pr_url:
        lines.append(f"*pr*: {prop.applied_pr_url}")
    if prop.rationale:
        lines.append("")
        lines.append("*rationale*:")
        lines.append(prop.rationale[:1500])
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


# ── Schedule management ────────────────────────────────────────────────────


@_error_safe
async def cmd_schedule(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if await _guard(update) is None:
        return
    args = ctx.args
    if not args:
        await update.message.reply_text(
            "Usage:\n"
            "`/schedule list`\n"
            "`/schedule add <name> <cron> <kind>: <desc>`\n"
            "`/schedule pause <name>`\n"
            "`/schedule resume <name>`",
            parse_mode="Markdown",
        )
        return

    sub = args[0].lower()

    if sub == "list":
        async with async_session() as s:
            result = await s.execute(select(Schedule).order_by(Schedule.name))
            rows = list(result.scalars())
        if not rows:
            await update.message.reply_text("No schedules configured.")
            return
        lines = ["*Schedules:*"]
        for sched in rows:
            icon = "\u23f8" if sched.paused else "\u25b6"
            nxt = sched.next_run_at.strftime("%m-%d %H:%M") if sched.next_run_at else "—"
            lines.append(f"{icon} `{sched.name}` `{sched.cron_expression}` next: {nxt}")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    elif sub == "add" and len(args) >= 4:
        # Format: /schedule add <name> <cron-5-fields> <kind>: <description>
        name = args[1]
        # Find the cron expression (5 space-separated fields)
        remaining = " ".join(args[2:])
        parts = remaining.split()
        if len(parts) < 6:
            await update.message.reply_text(
                "Need: `/schedule add <name> <min> <hr> <dom> <mon> <dow> <kind>: <desc>`",
                parse_mode="Markdown",
            )
            return
        cron_expr = " ".join(parts[:5])
        rest = " ".join(parts[5:])

        # Validate cron
        try:
            from croniter import croniter
            croniter(cron_expr)
        except (ValueError, KeyError):
            await update.message.reply_text(f"Invalid cron: `{cron_expr}`", parse_mode="Markdown")
            return

        # Parse kind: description
        if ":" in rest:
            kind_str, desc = rest.split(":", 1)
            kind_str = kind_str.strip().replace("_", "-")
            desc = desc.strip()
        else:
            kind_str = rest.strip().replace("_", "-")
            desc = f"Scheduled {kind_str}"

        try:
            from src.db import session_scope
            async with session_scope() as s:
                sched = Schedule(
                    name=name,
                    cron_expression=cron_expr,
                    job_kind=kind_str,
                    job_description=desc,
                    paused=False,
                )
                s.add(sched)
            await update.message.reply_text(
                f"Created schedule `{name}` (`{cron_expr}` → {kind_str})",
                parse_mode="Markdown",
            )
        except Exception as exc:
            if "unique" in str(exc).lower() or "duplicate" in str(exc).lower():
                await update.message.reply_text(f"Schedule `{name}` already exists.", parse_mode="Markdown")
            else:
                await update.message.reply_text(f"Error: {str(exc)[:200]}")

    elif sub == "pause" and len(args) >= 2:
        name = args[1]
        from src.db import session_scope
        async with session_scope() as s:
            result = await s.execute(
                sql_update(Schedule).where(Schedule.name == name).values(paused=True)
            )
            if result.rowcount == 0:
                await update.message.reply_text(f"No schedule named `{name}`.", parse_mode="Markdown")
                return
        await update.message.reply_text(f"Paused `{name}`.", parse_mode="Markdown")

    elif sub == "resume" and len(args) >= 2:
        name = args[1]
        from src.db import session_scope
        async with session_scope() as s:
            result = await s.execute(
                sql_update(Schedule).where(Schedule.name == name).values(paused=False)
            )
            if result.rowcount == 0:
                await update.message.reply_text(f"No schedule named `{name}`.", parse_mode="Markdown")
                return
        await update.message.reply_text(f"Resumed `{name}`.", parse_mode="Markdown")

    else:
        await update.message.reply_text(
            "Unknown subcommand. Use: list, add, pause, resume."
        )


# ── Done-notification listener ──────────────────────────────────────────────


# ── Task interaction commands ──────────────────────────────────────────────


async def _find_task_by_prefix(prefix: str) -> Task | None:
    """Find a task by UUID prefix. Returns None if ambiguous or not found."""
    async with async_session() as s:
        try:
            full_id = uuid.UUID(prefix)
            return await s.get(Task, full_id)
        except ValueError:
            pass
        from sqlalchemy import text
        result = await s.execute(
            text("SELECT id FROM tasks WHERE CAST(id AS TEXT) LIKE :p LIMIT 2"),
            {"p": f"{prefix}%"},
        )
        ids = [row[0] for row in result.fetchall()]
        if len(ids) != 1:
            return None
        return await s.get(Task, ids[0])


def _parse_callback(data: str) -> tuple[str, str | None, str | None]:
    """Parse 'action:task_prefix[:extra]' callback data."""
    parts = data.split(":", 2)
    action = parts[0]
    task_prefix = parts[1] if len(parts) > 1 else None
    extra = parts[2] if len(parts) > 2 else None
    return action, task_prefix, extra


async def cmd_reply(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Reply to a task: /reply <task_prefix> <response>"""
    chat_id = await _guard(update)
    if chat_id is None:
        return
    args = ctx.args or []
    if len(args) < 2:
        await update.message.reply_text("Usage: /reply <task_id> <your response>")
        return

    prefix = args[0]
    response_text = " ".join(args[1:])

    task = await _find_task_by_prefix(prefix)
    if not task:
        await update.message.reply_text(f"Task `{prefix}` not found.")
        return
    if task.status not in (TaskStatus.awaiting_user.value, TaskStatus.pending_approval.value):
        await update.message.reply_text(
            f"Task `{prefix}` is `{task.status}` — can only reply to awaiting_user or pending_approval tasks."
        )
        return

    # Record user turn
    from sqlalchemy import func as sqlfunc
    async with async_session() as s:
        max_turn = await s.execute(
            select(sqlfunc.max(TaskTurn.turn_number)).where(TaskTurn.task_id == task.id)
        )
        last = max_turn.scalar() or 0
        s.add(TaskTurn(
            task_id=task.id,
            turn_number=last + 1,
            role="user",
            content=response_text,
        ))
        await s.execute(
            sql_update(Task).where(Task.id == task.id).values(
                status=TaskStatus.active.value,
            )
        )
        await s.commit()

    # Enqueue continuation job with task context
    job = await enqueue_job(
        response_text,
        kind=JobKind.task.value,
        payload=None,
        created_by=f"telegram:{chat_id}",
    )
    async with async_session() as s:
        await s.execute(
            sql_update(Job).where(Job.id == job.id).values(task_id=task.id)
        )
        await s.commit()

    _job_to_chat[str(job.id)] = chat_id
    await update.message.reply_text(
        f"Continuing task `{str(task.id)[:8]}` → job `{str(job.id)[:8]}`",
        parse_mode="Markdown",
    )


async def cmd_approve(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Approve a completed task: /approve <task_prefix>"""
    chat_id = await _guard(update)
    if chat_id is None:
        return
    args = ctx.args or []
    if not args:
        await update.message.reply_text("Usage: /approve <task_id>")
        return

    task = await _find_task_by_prefix(args[0])
    if not task:
        await update.message.reply_text(f"Task `{args[0]}` not found.")
        return
    if task.status != TaskStatus.pending_approval.value:
        await update.message.reply_text(
            f"Task `{args[0]}` is `{task.status}` — can only approve pending_approval tasks."
        )
        return

    from sqlalchemy import func as sqlfunc
    async with async_session() as s:
        max_result = await s.execute(
            select(sqlfunc.max(TaskTurn.turn_number)).where(TaskTurn.task_id == task.id)
        )
        last = max_result.scalar() or 0
        s.add(TaskTurn(
            task_id=task.id,
            turn_number=last + 1,
            role="system",
            content="User approved task completion.",
        ))
        await s.execute(
            sql_update(Task).where(Task.id == task.id).values(
                status=TaskStatus.completed.value,
            )
        )
        await s.commit()

    await update.message.reply_text(
        f"Task `{str(task.id)[:8]}` marked complete. ✓",
        parse_mode="Markdown",
    )


async def cmd_tasks(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """List active tasks: /tasks"""
    chat_id = await _guard(update)
    if chat_id is None:
        return

    active_statuses = [
        TaskStatus.active.value,
        TaskStatus.awaiting_user.value,
        TaskStatus.pending_approval.value,
    ]
    async with async_session() as s:
        result = await s.execute(
            select(Task)
            .where(Task.status.in_(active_statuses))
            .order_by(Task.created_at.desc())
            .limit(15)
        )
        tasks = list(result.scalars().all())

    if not tasks:
        await update.message.reply_text("No active tasks.")
        return

    lines = [f"*Active tasks ({len(tasks)}):*\n"]
    for t in tasks:
        prefix = str(t.id)[:8]
        desc = _esc_md(t.description[:50])
        status_icon = {"active": "🔄", "awaiting_user": "❓", "pending_approval": "✋"}.get(t.status, "")
        line = f"`{prefix}` {status_icon} {t.status}: {desc}"
        if t.status == TaskStatus.awaiting_user.value:
            line += f"\n  → `/reply {prefix} <answer>`"
        elif t.status == TaskStatus.pending_approval.value:
            line += f"\n  → `/approve {prefix}` or `/reply {prefix} <feedback>`"
        elif t.status == TaskStatus.active.value:
            line += f"\n  → running, wait for result"
        lines.append(line)

    lines.append(f"\n`/jobs` to see individual job runs")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


@_error_safe
async def cmd_jobs(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """List recent jobs: /jobs [count]"""
    chat_id = await _guard(update)
    if chat_id is None:
        return
    args = ctx.args or []
    limit = 10
    if args and args[0].isdigit():
        limit = min(int(args[0]), 25)

    async with async_session() as s:
        result = await s.execute(
            select(Job)
            .order_by(Job.created_at.desc())
            .limit(limit)
        )
        jobs = list(result.scalars().all())

    if not jobs:
        await update.message.reply_text("No jobs yet.")
        return

    status_icons = {
        "queued": "⏳", "running": "🔄", "completed": "✅",
        "failed": "❌", "cancelled": "🚫", "awaiting_user": "❓",
    }

    lines = [f"*Recent jobs ({len(jobs)}):*\n"]
    for j in jobs:
        prefix = str(j.id)[:8]
        icon = status_icons.get(j.status, "")
        skill = j.resolved_skill or j.kind
        desc = _esc_md(j.description[:40])
        task_ref = f" (task `{str(j.task_id)[:8]}`)" if j.task_id else ""
        line = f"`{prefix}` {icon} {skill} — {desc}{task_ref}"
        if j.status == JobStatus.completed.value:
            line += f"\n  → `/rate {prefix} 1-5` or `/status {prefix}`"
        elif j.status == JobStatus.failed.value:
            line += f"\n  → `/status {prefix}` for error details"
        elif j.status in (JobStatus.queued.value, JobStatus.running.value):
            line += f"\n  → `/cancel {prefix}` to stop"
        lines.append(line)

    lines.append(f"\n`/tasks` to see task conversations")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


# ── Thread reply handler ───────────────────────────────────────────────────


@_error_safe
async def _handle_thread_reply(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """Route plain-text replies in task threads as task continuations."""
    chat_id = await _guard(update)
    if chat_id is None:
        return

    # Must be a reply to a message
    if not update.message.reply_to_message:
        return
    reply_msg_id = update.message.reply_to_message.message_id

    # Look up Task where thread_message_id matches
    async with async_session() as s:
        result = await s.execute(
            select(Task).where(Task.thread_message_id == reply_msg_id)
        )
        task = result.scalar_one_or_none()

    if not task:
        return  # Not a task thread — ignore

    if task.status in (TaskStatus.completed.value, TaskStatus.failed.value):
        await update.message.reply_text("This task is already finished.")
        return

    if task.status not in (
        TaskStatus.active.value,
        TaskStatus.awaiting_user.value,
        TaskStatus.pending_approval.value,
    ):
        return

    response_text = update.message.text.strip()
    if not response_text:
        return

    # Record user turn
    from sqlalchemy import func as sqlfunc
    async with async_session() as s:
        max_turn = await s.execute(
            select(sqlfunc.max(TaskTurn.turn_number)).where(TaskTurn.task_id == task.id)
        )
        last = max_turn.scalar() or 0
        s.add(TaskTurn(
            task_id=task.id,
            turn_number=last + 1,
            role="user",
            content=response_text,
        ))
        await s.execute(
            sql_update(Task).where(Task.id == task.id).values(
                status=TaskStatus.active.value,
            )
        )
        await s.commit()

    # Enqueue continuation job
    job = await enqueue_job(
        response_text,
        kind=JobKind.task.value,
        payload=None,
        created_by=f"telegram:{chat_id}",
    )
    async with async_session() as s:
        await s.execute(
            sql_update(Job).where(Job.id == job.id).values(task_id=task.id)
        )
        await s.commit()

    _job_to_chat[str(job.id)] = chat_id
    await update.message.reply_text("\U0001f504 Continuing...")


# ── Inline button handler ─────────────────────────────────────────────────


@_error_safe
async def _handle_button(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline keyboard button presses."""
    query = update.callback_query
    if not query:
        return
    await query.answer()

    # Auth check on the user pressing the button
    chat_id = update.effective_chat.id
    if not _is_authorized(chat_id):
        return

    action, task_prefix, extra = _parse_callback(query.data or "")
    if not task_prefix:
        return

    task = await _find_task_by_prefix(task_prefix)
    if not task:
        await query.edit_message_text("Task not found.")
        return

    prefix = str(task.id)[:8]

    if action == "approve":
        from sqlalchemy import func as sqlfunc
        async with async_session() as s:
            max_result = await s.execute(
                select(sqlfunc.max(TaskTurn.turn_number)).where(TaskTurn.task_id == task.id)
            )
            last = max_result.scalar() or 0
            s.add(TaskTurn(
                task_id=task.id,
                turn_number=last + 1,
                role="system",
                content="User approved task completion.",
            ))
            await s.execute(
                sql_update(Task).where(Task.id == task.id).values(
                    status=TaskStatus.completed.value,
                )
            )
            await s.commit()
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(f"\u2705 Task `{prefix}` approved.", parse_mode="Markdown")

    elif action == "cancel":
        # Find running job for this task and cancel it
        async with async_session() as s:
            result = await s.execute(
                select(Job).where(
                    Job.task_id == task.id,
                    Job.status.in_([JobStatus.queued.value, JobStatus.running.value]),
                ).order_by(Job.created_at.desc()).limit(1)
            )
            job = result.scalar_one_or_none()
        if job:
            await cancel_job(job.id)
        async with async_session() as s:
            await s.execute(
                sql_update(Task).where(Task.id == task.id).values(
                    status=TaskStatus.failed.value,
                )
            )
            await s.commit()
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(f"\U0001f6ab Task `{prefix}` cancelled.", parse_mode="Markdown")

    elif action == "feedback":
        await query.message.reply_text("Send your feedback as a reply to this message.")

    elif action == "details":
        async with async_session() as s:
            result = await s.execute(
                select(Job).where(Job.task_id == task.id)
                .order_by(Job.created_at.desc()).limit(1)
            )
            job = result.scalar_one_or_none()
        if not job:
            await query.message.reply_text("No jobs found for this task.")
            return
        lines = [f"Job `{str(job.id)[:8]}` — *{job.status}*"]
        if job.error_message:
            lines.append(f"Error: `{job.error_message[:200]}`")
        if job.result:
            summary = (job.result.get("summary") or "")[:600]
            if summary:
                lines.append(f"\n{summary}")
        await query.message.reply_text("\n".join(lines), parse_mode="Markdown")

    elif action == "rate" and extra:
        try:
            rating = int(extra)
        except ValueError:
            return
        if rating < 1 or rating > 5:
            return
        async with async_session() as s:
            result = await s.execute(
                select(Job).where(Job.task_id == task.id)
                .order_by(Job.created_at.desc()).limit(1)
            )
            job = result.scalar_one_or_none()
        if job:
            async with async_session() as s:
                await s.execute(
                    sql_update(Job).where(Job.id == job.id).values(user_rating=rating)
                )
                await s.commit()
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(f"Rated {rating}/5. Thanks!")

    elif action == "choice" and extra:
        # Record choice as user turn, enqueue continuation
        from sqlalchemy import func as sqlfunc
        async with async_session() as s:
            max_turn = await s.execute(
                select(sqlfunc.max(TaskTurn.turn_number)).where(TaskTurn.task_id == task.id)
            )
            last = max_turn.scalar() or 0
            s.add(TaskTurn(
                task_id=task.id,
                turn_number=last + 1,
                role="user",
                content=f"Selected option: {extra}",
            ))
            await s.execute(
                sql_update(Task).where(Task.id == task.id).values(
                    status=TaskStatus.active.value,
                )
            )
            await s.commit()
        job = await enqueue_job(
            f"User selected: {extra}",
            kind=JobKind.task.value,
            payload=None,
            created_by=f"telegram:{chat_id}",
        )
        async with async_session() as s:
            await s.execute(
                sql_update(Job).where(Job.id == job.id).values(task_id=task.id)
            )
            await s.commit()
        _job_to_chat[str(job.id)] = chat_id
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(f"\U0001f504 Continuing with choice: {extra}")


# ── Listeners ──────────────────────────────────────────────────────────────


async def _done_listener(app: Application) -> None:
    pubsub = redis.pubsub()
    await pubsub.psubscribe(f"{CHANNEL_JOB_DONE}:*")
    try:
        async for msg in pubsub.listen():
            if msg.get("type") != "pmessage":
                continue
            channel = msg.get("channel", "")
            job_id = channel.rsplit(":", 1)[-1]
            chat_id = _job_to_chat.pop(job_id, None)
            if not chat_id:
                continue
            try:
                payload = json.loads(msg.get("data", "{}"))
            except json.JSONDecodeError:
                payload = {}
            status = payload.get("status", "unknown")
            summary = (payload.get("summary") or "")[:1500]

            text = f"Job `{job_id[:8]}` *{status}*"
            if summary:
                text += f"\n\n{summary}"
            if status == JobStatus.completed.value:
                text += f"\n\n💡 `/rate {job_id[:8]} 1-5`"
            try:
                await app.bot.send_message(chat_id, text, parse_mode="Markdown")
            except Exception:
                logger.exception("failed to DM result", chat_id=chat_id, job_id=job_id)
    finally:
        await pubsub.punsubscribe(f"{CHANNEL_JOB_DONE}:*")


# ── Quota-pause notifier ────────────────────────────────────────────────────


async def _quota_notifier(app: Application) -> None:
    """Periodically check quota state; Telegram once on pause and once on resume."""
    last_state: tuple[bool, str] = (False, "")
    while True:
        await asyncio.sleep(60)
        try:
            paused, reset_at, reason = await quota.is_paused()
            state = (paused, reason[:80])
            if state == last_state:
                continue
            # State changed
            for chat_id in settings.allowed_chat_ids:
                try:
                    if paused:
                        reset_str = reset_at.strftime("%H:%M UTC") if reset_at else "unknown"
                        await app.bot.send_message(
                            chat_id,
                            f"⏸ Queue paused (subscription quota).\n"
                            f"Reset at {reset_str}.\n"
                            f"Reason: {reason[:200]}",
                        )
                    else:
                        await app.bot.send_message(chat_id, "▶️ Queue resumed.")
                except Exception:
                    logger.exception("failed to send quota notification")
            last_state = state
        except Exception:
            logger.exception("quota notifier tick failed")


# ── Main ────────────────────────────────────────────────────────────────────


async def _task_notifier(app: Application) -> None:
    """Listen for task lifecycle events and post in threads with inline buttons."""
    pubsub = redis.pubsub()
    await pubsub.subscribe("tasks:notify")
    try:
        async for msg in pubsub.listen():
            if msg.get("type") != "message":
                continue
            try:
                data = json.loads(msg.get("data", "{}"))
            except json.JSONDecodeError:
                continue

            task_id = data.get("task_id", "")
            notify_type = data.get("type", "")
            text_content = data.get("text", "")
            choices = data.get("choices", [])

            # Look up the task to get chat_id and thread_message_id
            task = await _find_task_by_prefix(task_id)
            if not task or not task.chat_id:
                continue

            prefix = str(task.id)[:8]

            try:
                if notify_type == "approval_request":
                    # Reply in thread with result + action buttons
                    # NOTE: text_content is AI-generated and may contain markdown
                    # that breaks Telegram's parser. Send WITHOUT parse_mode.
                    keyboard = InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton("Approve", callback_data=f"approve:{prefix}"),
                            InlineKeyboardButton("Send Feedback", callback_data=f"feedback:{prefix}"),
                            InlineKeyboardButton("View Details", callback_data=f"details:{prefix}"),
                        ],
                        [
                            InlineKeyboardButton("1", callback_data=f"rate:{prefix}:1"),
                            InlineKeyboardButton("2", callback_data=f"rate:{prefix}:2"),
                            InlineKeyboardButton("3", callback_data=f"rate:{prefix}:3"),
                            InlineKeyboardButton("4", callback_data=f"rate:{prefix}:4"),
                            InlineKeyboardButton("5", callback_data=f"rate:{prefix}:5"),
                        ],
                    ])
                    # Truncate long content for Telegram (4096 char limit)
                    content_truncated = text_content[:3500]
                    if len(text_content) > 3500:
                        content_truncated += "\n\n... (truncated — tap View Details for full)"
                    msg_text = (
                        f"Task {prefix} is done:\n\n"
                        f"{content_truncated}"
                    )
                    send_kwargs = dict(
                        chat_id=task.chat_id,
                        text=msg_text,
                        reply_markup=keyboard,
                    )
                    if task.thread_message_id:
                        send_kwargs["reply_to_message_id"] = task.thread_message_id
                    await app.bot.send_message(**send_kwargs)

                    # Also send short summary DM in main chat (not in thread)
                    await app.bot.send_message(
                        chat_id=task.chat_id,
                        text=f"Task \"{task.description[:40]}\" needs your approval — tap Approve in thread above",
                    )

                elif notify_type == "question":
                    msg_text = (
                        f"Task {prefix} needs your input:\n\n"
                        f"{text_content[:3500]}\n\n"
                        f"Reply to this message with your answer."
                    )
                    send_kwargs = dict(chat_id=task.chat_id, text=msg_text)
                    if task.thread_message_id:
                        send_kwargs["reply_to_message_id"] = task.thread_message_id
                    await app.bot.send_message(**send_kwargs)

                elif notify_type == "choices" and choices:
                    buttons = []
                    for i, choice in enumerate(choices[:8]):
                        buttons.append([InlineKeyboardButton(
                            choice[:40],
                            callback_data=f"choice:{prefix}:{i}",
                        )])
                    keyboard = InlineKeyboardMarkup(buttons)
                    question_text = data.get("question", "Pick one:")
                    msg_text = f"Task {prefix}:\n\n{question_text}"
                    send_kwargs = dict(
                        chat_id=task.chat_id,
                        text=msg_text,
                        reply_markup=keyboard,
                    )
                    if task.thread_message_id:
                        send_kwargs["reply_to_message_id"] = task.thread_message_id
                    await app.bot.send_message(**send_kwargs)

            except Exception:
                logger.exception("failed to send task notification", task_id=task_id)
    finally:
        await pubsub.unsubscribe("tasks:notify")


async def _post_init(app: Application) -> None:
    asyncio.create_task(_done_listener(app))
    asyncio.create_task(_task_notifier(app))
    asyncio.create_task(_quota_notifier(app))


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    if not settings.telegram_bot_token:
        raise SystemExit("TELEGRAM_BOT_TOKEN is not set. See .env.example.")

    app = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .post_init(_post_init)
        .build()
    )
    # Primary commands
    app.add_handler(CommandHandler("start", cmd_help))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("task", cmd_task))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("jobs", cmd_jobs))
    # Admin commands
    app.add_handler(CommandHandler("chat", cmd_chat))
    app.add_handler(CommandHandler("resume", cmd_resume))
    app.add_handler(CommandHandler("clear", cmd_clear))
    app.add_handler(CommandHandler("schedule", cmd_schedule))
    app.add_handler(CommandHandler("projects", cmd_projects))
    # Thread reply + inline button handlers
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.REPLY, _handle_thread_reply))
    app.add_handler(CallbackQueryHandler(_handle_button))

    logger.info("telegram bot starting")
    app.run_polling(close_loop=False)


if __name__ == "__main__":
    main()
