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
from datetime import datetime, timezone

import structlog
from sqlalchemy import select, update as sql_update
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from src import audit_log
from src.config import settings
from src.db import CHANNEL_JOB_DONE, CHANNEL_NOTIFY_OUTBOX, async_session, redis
from src.gateway.jobs import cancel_job, enqueue_job, find_job_by_prefix
from src.models import Job, JobKind, JobStatus, Project, Schedule, Task, TaskStatus, TaskTurn
from src.notify.outbox import (
    OPS_NOTICE_KINDS,
    build_ops_notice,
    claim_notice,
    enqueue_notice,
    lane_label,
    mark_failed,
    mark_sent,
    mark_skipped,
    pending_notices,
    release_stuck_sending,
)
from src.notify.telegram import TelegramSendError, render_telegram, send_via_bot
from src.registry import models as models_registry
from src.runner import quota, schedule_adherence

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

# Model alias expansion — accepts short names on the command line.
# Fed from the repo-root `models.yml` via the registry (cross-vendor writer
# slice T1, 2026-10-21): alias → canonical id, bare for Anthropic
# (`opus` → `claude-opus-4-7`, as before) and `provider/alias` →
# `provider/model_id` for any other provider, exactly the keys
# `registry.models.resolve()` accepts. Add or move an alias in models.yml,
# not here. Retired models never appear in the registry; their aliases live
# in _RETIRED_MODEL_ALIASES below and resolve to the replacement. Whatever
# the alias tables yield is then resolved THROUGH the registry (T7,
# 2026-10-21): the stored value is always the canonical `[provider/]model_id`
# and an unknown provider or model is refused at parse time
# (`ModelFlagRefused`, carrying the registry's reason) — a bad id never
# reaches `job.payload` for the session to fail later.
_MODEL_ALIASES = models_registry.alias_table()

# Aliases of retired models, typed from muscle memory. Resolved to the current
# replacement so a retired (or bare, unknown) id never lands in job.payload.
# Haiku 4.5 retirement window opened 2026-10-15 (T0, 2026-10-21).
_RETIRED_MODEL_ALIASES = {
    "haiku": "claude-sonnet-4-6",
    "haiku-4-5": "claude-sonnet-4-6",
}

_VALID_EFFORTS = {"low", "medium", "high", "xhigh", "max"}
_VALID_PERMISSIONS = {"default", "acceptEdits", "bypassPermissions", "plan"}


class ModelFlagRefused(ValueError):
    """`--model=<raw>` names something the models registry does not know
    (T7, 2026-10-21). `reason` is the registry's own wording. Raised by
    `parse_flags`; the command handlers catch it via
    `_parse_flags_or_reply`, reply with the reason and create nothing. A
    caller that forgets to catch it trips `_error_safe` — loud, never a
    silently-passed-through id."""

    def __init__(self, raw: str, reason: str):
        self.raw = raw
        self.reason = reason
        super().__init__(f"--model={raw} refused: {reason}")


def parse_flags(text: str) -> tuple[str, dict]:
    """
    Extract --flag=value tokens from the front of a description.
    Returns (cleaned_description, flags_dict).

    Supported flags: --model, --effort, --permission, --project, --kind.
    Unknown flags are left in the description (caller can decide to reject).
    `--model` is resolved through the registry and stored canonical; an
    unknown `[provider/]model_id` raises `ModelFlagRefused` (T7).
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
            alias = val.lower()
            candidate = _MODEL_ALIASES.get(
                alias, _RETIRED_MODEL_ALIASES.get(alias, val))
            try:
                flags["model"] = models_registry.resolve(candidate).canonical
            except models_registry.ProviderRefused as exc:
                raise ModelFlagRefused(val, exc.reason) from exc
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


def _model_flag_help() -> str:
    """What `--model=` accepts right now: Anthropic aliases bare, every
    other ENABLED provider's ids qualified. Plain text (no Markdown)."""
    enabled = models_registry.enabled_providers()
    parts: list[str] = []
    for provider in models_registry.providers():
        if provider not in enabled:
            continue
        for m in models_registry.list_models(provider):
            if provider == models_registry.DEFAULT_PROVIDER:
                parts.extend(m.aliases or (m.model_id,))
            else:
                parts.append(m.ref.canonical)
    return ", ".join(parts)


async def _parse_flags_or_reply(update: Update, raw: str) -> tuple[str, dict] | None:
    """`parse_flags` for a command handler: a `--model` the registry does not
    know, or whose provider is not in ROUTER_PROVIDERS_ENABLED, is answered
    with the reason and `None` — no Task row, no job (T7, 2026-10-21; the
    web's 422 is the same rule). Plain-text reply: the raw value is user
    text and must not be parsed as Markdown."""
    try:
        description, flags = parse_flags(raw)
        if flags.get("model"):
            models_registry.resolve_enabled(flags["model"])
    except (ModelFlagRefused, models_registry.ProviderRefused) as exc:
        await update.message.reply_text(
            f"\u274c --model={exc.raw} refused: {exc.reason}.\n"
            f"Accepted: {_model_flag_help()}."
        )
        return None
    return description, flags


# `provider/model` for the surfaces (T7). Since A6 a thin alias of the one
# definition in src/notify/outbox.py so the done DM, /jobs and the outbox
# cards can never disagree.
_lane_label = lane_label


# ── Commands ────────────────────────────────────────────────────────────────


@_error_safe
async def cmd_help(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    if await _guard(update) is None:
        return
    await update.message.reply_text(
        "*Just text me what you want* — no command needed.\n"
        "_\"update the bingo app to support dark mode\" works as-is. "
        "Multi-step asks get decomposed into a plan, executed, and verified. "
        "Questions get a direct answer._\n\n"
        "*Commands (still work):*\n\n"
        "/task <description> — start a new task explicitly\n"
        "  _Reply in the thread to continue. Buttons for actions._\n\n"
        "/status — see active tasks\n"
        "/jobs — see recent job runs\n"
        "/help — this message\n\n"
        "_Admin: /god, /chat, /resume, /clear, /schedule_",
        parse_mode="Markdown",
    )


def triage_plain_text(text: str) -> str:
    """Classify a bare (non-command) message: 'chat' or 'task'. Pure function.

    Conservative: anything the rule router recognizes is a task; otherwise
    short interrogative messages are chat, and everything else is a task
    (the runner's LLM routing fallback handles ambiguity from there).
    """
    from src.runner.router import route as _route

    stripped = text.strip()
    if _route(stripped):
        return "task"
    lowered = stripped.lower()
    question_starts = ("what", "who", "when", "where", "how", "why", "is ",
                       "are ", "can ", "could ", "should ", "do ", "does ",
                       "did ", "will ", "would ")
    if len(stripped) <= 240 and (
        stripped.endswith("?") or lowered.startswith(question_starts)
    ):
        return "chat"
    return "task"


async def _create_task_with_job(
    update: Update,
    chat_id: int,
    description: str,
    *,
    kind: str,
    flags: dict | None,
    banner: str,
) -> None:
    """Shared task+job creation used by /task, /god, and plain-text asks."""
    task = Task(
        description=description,
        created_by=f"telegram:{chat_id}",
        chat_id=chat_id,
        origin_channel="telegram",
        origin_ref=str(chat_id),
    )
    async with async_session() as s:
        s.add(task)
        await s.commit()
        await s.refresh(task)

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
        task_id=task.id,
        origin_channel="telegram",
        origin_ref=str(chat_id),
    )
    _job_to_chat[str(job.id)] = chat_id

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("Cancel", callback_data=f"cancel:{str(task.id)[:8]}"),
    ]])
    reply = await update.message.reply_text(
        f"{banner} ({_esc_md(description[:60])})",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )
    # The root reply's id is the thread every later card posts under: the
    # legacy column AND origin_thread on both rows (A2, migration 008).
    async with async_session() as s:
        await s.execute(sql_update(Task).where(Task.id == task.id).values(
            thread_message_id=reply.message_id,
            origin_thread=str(reply.message_id)))
        await s.execute(sql_update(Job).where(Job.id == job.id).values(
            origin_thread=str(reply.message_id)))
        await s.commit()


@_error_safe
async def cmd_task(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = await _guard(update)
    if chat_id is None:
        return
    raw = " ".join(ctx.args).strip()
    if not raw:
        await update.message.reply_text("Usage: /task [flags] <what you want me to do>")
        return

    parsed = await _parse_flags_or_reply(update, raw)
    if parsed is None:
        return
    description, flags = parsed
    if not description:
        await update.message.reply_text(
            "Flags parsed but no description remaining. Put the task after the flags."
        )
        return

    # Optional kind override from flags (e.g., --kind=research_deep)
    kind = flags.pop("kind_override", JobKind.task.value)
    if kind.strip().lower() == "god":
        # /god is the single break-glass door (2026-08-31,
        # EVALUATION_2026-08-30 F1.3) — /task must not be a second one.
        await update.message.reply_text(
            "`--kind=god` is not accepted on /task — use /god <description> "
            "for break-glass work.", parse_mode="Markdown")
        return
    await _create_task_with_job(
        update, chat_id, description,
        kind=kind, flags=flags,
        banner="\U0001f504 Working on it...",
    )


@_error_safe
async def _handle_plain_text(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """NL-first ingestion (P2): a bare message — no /command, not a thread
    reply — is a first-class ask. Short questions become chat jobs; anything
    else becomes a task (router + LLM fallback pick the skill, `plan`
    decomposes multi-step asks)."""
    chat_id = await _guard(update)
    if chat_id is None:
        return
    text = (update.message.text or "").strip()
    if not text:
        return

    if triage_plain_text(text) == "chat":
        job = await enqueue_job(
            text,
            kind=JobKind.chat.value,
            created_by=f"telegram:{chat_id}",
            origin_channel="telegram",
            origin_ref=str(chat_id),
        )
        _job_to_chat[str(job.id)] = chat_id
        await update.message.reply_text(f"Thinking... ({str(job.id)[:8]})")
        return

    await _create_task_with_job(
        update, chat_id, text,
        kind=JobKind.task.value, flags=None,
        banner="\U0001f504 On it...",
    )


@_error_safe
async def cmd_chat(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = await _guard(update)
    if chat_id is None:
        return
    raw = " ".join(ctx.args).strip()
    if not raw:
        await update.message.reply_text("Usage: /chat <your message>")
        return

    parsed = await _parse_flags_or_reply(update, raw)
    if parsed is None:
        return
    description, flags = parsed
    job = await enqueue_job(
        description,
        kind=JobKind.chat.value,
        payload=flags or None,
        created_by=f"telegram:{chat_id}",
        origin_channel="telegram",
        origin_ref=str(chat_id),
    )
    _job_to_chat[str(job.id)] = chat_id
    await update.message.reply_text(f"Thinking... ({str(job.id)[:8]})")


@_error_safe
async def cmd_god(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Full-context, full-permission god-mode session."""
    chat_id = await _guard(update)
    if chat_id is None:
        return
    raw = " ".join(ctx.args).strip()
    if not raw:
        await update.message.reply_text("Usage: /god <what you want done — full system access>")
        return

    parsed = await _parse_flags_or_reply(update, raw)
    if parsed is None:
        return
    description, flags = parsed
    if not description:
        await update.message.reply_text("Put the task description after any flags.")
        return

    # Create task (same as /task but with kind="god")
    task = Task(description=description, created_by=f"telegram:{chat_id}", chat_id=chat_id,
                origin_channel="telegram", origin_ref=str(chat_id))
    async with async_session() as s:
        s.add(task)
        await s.commit()
        await s.refresh(task)

    async with async_session() as s:
        s.add(TaskTurn(task_id=task.id, turn_number=1, role="user", content=description))
        await s.commit()

    job = await enqueue_job(
        description,
        kind="god",
        payload=flags or None,
        created_by=f"telegram:{chat_id}",
        origin_channel="telegram",
        origin_ref=str(chat_id),
    )
    async with async_session() as s:
        await s.execute(sql_update(Job).where(Job.id == job.id).values(task_id=task.id))
        await s.commit()

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("Cancel", callback_data=f"cancel:{str(task.id)[:8]}"),
    ]])
    reply = await update.message.reply_text(
        f"\u26a1 God mode: {_esc_md(description[:60])}",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )
    async with async_session() as s:
        await s.execute(sql_update(Task).where(Task.id == task.id).values(
            thread_message_id=reply.message_id,
            origin_thread=str(reply.message_id)))
        await s.execute(sql_update(Job).where(Job.id == job.id).values(
            origin_thread=str(reply.message_id)))
        await s.commit()


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

    # One line per paused provider LANE (T6, 2026-10-21): a held lane is
    # otherwise invisible - its jobs cycle to the queue tail silently.
    # The global (Anthropic) pause has its own notifier; it is not repeated here.
    # Plus one line per schedule row the provisioning pre-check deferred at
    # its latest slot (D1): the row ran no session and is not dark.
    lane_lines = await _paused_lane_lines() + await _deferred_schedule_lines()

    if not tasks:
        await update.message.reply_text(
            "\n".join(lane_lines + ["No active tasks. Start one with /task."]),
            parse_mode="Markdown" if lane_lines else None,
        )
        return

    status_icons = {"active": "\U0001f504", "awaiting_user": "\u2753", "pending_approval": "\u270b"}
    lines = lane_lines + [f"*Active tasks ({len(tasks)}):*\n"]
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


async def _paused_lane_lines() -> list[str]:
    """Markdown lines, one per paused NON-Anthropic provider lane (T6)."""
    names = [p for p in models_registry.providers() if p != models_registry.DEFAULT_PROVIDER]
    paused = await quota.paused_providers(names)
    return [
        f"⏸ `{_esc_md(name)}` lane paused until {reset_at.strftime('%H:%M UTC')} "
        f"— its jobs are held ({_esc_md(reason[:80]) or 'no reason recorded'}). "
        f"`/resume {_esc_md(name)}` to lift."
        for name, (reset_at, reason) in paused.items()
    ]


async def _deferred_schedule_lines() -> list[str]:
    """Markdown lines, one per unpaused schedule whose newest
    `schedule_deferred` record (volumes/audit_log/schedules/<id>.jsonl)
    covers its latest cron slot (D1). Best-effort: never breaks /status."""
    try:
        now = datetime.now(timezone.utc)
        async with async_session() as s:
            rows = list((await s.execute(
                select(Schedule).where(Schedule.paused.is_(False)).order_by(Schedule.name)
            )).scalars().all())
        lines: list[str] = []
        for r in rows:
            at, missing = schedule_adherence.latest_deferral(audit_log.read_schedule_events(r.id))
            if schedule_adherence.is_deferred(r.cron_expression, at, now):
                keys = ", ".join(f"`{m}`" for m in missing) or "?"
                lines.append(f"⏸ deferred: {_esc_md(r.name)} (provisioning_gap: {keys})")
        return lines
    except Exception as exc:  # noqa: BLE001
        logger.warning("deferred-schedule lines skipped", error=str(exc)[:120])
        return []


@_error_safe
async def cmd_resume(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """`/resume` lifts the global (Anthropic) pause as before; `/resume
    <provider>` lifts ONE provider lane's pause (T6, 2026-10-21) and leaves
    the global key alone."""
    if await _guard(update) is None:
        return
    args = [a.strip().lower() for a in (ctx.args or []) if a.strip()]
    if args:
        name = args[0]
        if name not in models_registry.providers():
            await update.message.reply_text(
                f"Unknown provider '{name}'. Known: {', '.join(models_registry.providers())}."
            )
            return
        paused, _reset_at, reason = await quota.is_provider_paused(name)
        if not paused:
            await update.message.reply_text(f"{name} lane is not paused.")
            return
        await quota.clear_provider(name)
        await update.message.reply_text(
            f"{name} lane manually resumed (was paused for: {reason[:100]})."
        )
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


def format_job_status(job) -> str:
    """Pure. The `[Details]` button (A6) and `/status <prefix>` (Phase 2).
    Plain text — sent WITHOUT parse_mode: skill names with `_` crash
    Markdown (TROUBLESHOOTING.md). Lane via the one `lane_label` definition;
    the terminal reason is its own line, so the lane carries none here."""
    lines = [f"Job {str(job.id)[:8]} — {job.status}", f"kind: {job.resolved_skill or job.kind}"]
    lane = lane_label(getattr(job, "resolved_provider", None),
                      job.model_served or job.resolved_model)
    if lane:
        lines.append(f"lane: {lane}")
    if job.terminal_reason:
        lines.append(f"terminal: {job.terminal_reason}")
    if job.num_turns is not None:
        lines.append(f"turns: {job.num_turns}")
    if job.output_tokens is not None:
        lines.append(f"tokens: in {job.input_tokens or 0} · out {job.output_tokens or 0} "
                     f"· cache-read {job.cache_read_tokens or 0}")
    if job.duration_api_ms:
        lines.append(f"api time: {job.duration_api_ms / 1000:.1f}s")
    if job.cost_usd_list is not None:
        lines.append(f"list-equiv cost: ${float(job.cost_usd_list):.4f}")
    if job.origin_channel:
        ref = f":{job.origin_ref}" if job.origin_ref else ""
        lines.append(f"origin: {job.origin_channel}{ref}")
    if job.error_message:
        lines.append(f"error: {job.error_message[:300]}")
    summary = job.result.get("summary") if isinstance(job.result, dict) else None
    if summary:
        lines.append("")
        lines.append(summary[:600])
    return "\n".join(lines)[:4000]


def provider_paused_text(provider: str, reset_at: datetime | None, reason: str) -> str:
    """The quota_paused body for a NON-Anthropic lane (pure; A6). Per-provider
    pauses (T6) carry no vendor/estimated source — the reset time is the
    executor's backoff window — so the line is not labelled."""
    reset_str = reset_at.strftime("%H:%M UTC") if reset_at else "unknown"
    return (f"⏸ {provider} lane paused until {reset_str} — its jobs are held.\n"
            f"Reason: {reason[:200] or 'no reason recorded'}\n"
            f"/resume {provider} to lift.")



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
        # Which lane ran it (T7): `provider/model`; nothing while queued.
        lane = _lane_label(getattr(j, "resolved_provider", None), j.resolved_model)
        lane_ref = f" `{lane}`" if lane else ""
        line = f"`{prefix}` {icon} {skill}{lane_ref} — {desc}{task_ref}"
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
                awaiting_since=None,
            )
        )
        await s.commit()

    # Look up the task's original skill to inherit for continuation
    original_skill = None
    async with async_session() as s:
        result = await s.execute(
            select(Job.resolved_skill)
            .where(Job.task_id == task.id)
            .where(Job.resolved_skill.isnot(None))
            .order_by(Job.created_at)
            .limit(1)
        )
        row = result.first()
        if row:
            original_skill = row[0]

    # Use the original skill as kind so the runner resolves to the same
    # model/effort/permission. Fall back to generic task if no skill found.
    continuation_kind = original_skill or JobKind.task.value
    continuation_payload = {"project_slug": task.description.split(":")[0].strip()} if original_skill else None

    # Enqueue continuation job
    job = await enqueue_job(
        response_text,
        kind=continuation_kind,
        payload=continuation_payload,
        created_by=f"telegram:{chat_id}",
        origin_channel="telegram",
        origin_ref=str(chat_id),
        origin_thread=str(task.thread_message_id) if task.thread_message_id else None,
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

    # Job-level callbacks (A6 outbox cards) — the prefix is a JOB id, not a
    # task id. Plain text: format_job_status is not Markdown-safe by design.
    if action == "jd":
        job = await find_job_by_prefix(task_prefix)
        await query.message.reply_text(format_job_status(job) if job else "Job not found.")
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
        # Cancel the running job, and fail any queued/deferred siblings
        # (a cancelled plan must not keep spawning its DAG).
        async with async_session() as s:
            result = await s.execute(
                select(Job).where(
                    Job.task_id == task.id,
                    Job.status.in_([
                        JobStatus.queued.value,
                        JobStatus.deferred.value,
                        JobStatus.running.value,
                    ]),
                ).order_by(Job.created_at.desc())
            )
            open_jobs = list(result.scalars())
        for job in open_jobs:
            if job.status == JobStatus.running.value:
                await cancel_job(job.id)
        async with async_session() as s:
            await s.execute(
                sql_update(Job).where(
                    Job.task_id == task.id,
                    Job.status.in_([JobStatus.queued.value, JobStatus.deferred.value]),
                ).values(status=JobStatus.cancelled.value,
                         error_message="task cancelled by user")
            )
            await s.execute(
                sql_update(Task).where(Task.id == task.id).values(
                    status=TaskStatus.failed.value,
                )
            )
            await s.commit()
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(f"\U0001f6ab Task `{prefix}` cancelled.", parse_mode="Markdown")

    elif action == "approve_plan":
        # Manual plan approval (PLAN_AUTO_APPROVE=false): spawn the DAG now
        if not task.plan:
            await query.message.reply_text("No stored plan on this task.")
            return
        from src.runner import plans as plans_mod
        await plans_mod.spawn_plan_jobs(task.id, task.plan, created_by=f"telegram:{chat_id}")
        async with async_session() as s:
            from sqlalchemy import func as sqlfunc
            max_turn = await s.execute(
                select(sqlfunc.max(TaskTurn.turn_number)).where(TaskTurn.task_id == task.id)
            )
            last = max_turn.scalar() or 0
            s.add(TaskTurn(task_id=task.id, turn_number=last + 1, role="system",
                           content="User approved the plan; spawning subtasks."))
            await s.execute(
                sql_update(Task).where(Task.id == task.id).values(
                    status=TaskStatus.active.value, awaiting_since=None)
            )
            await s.commit()
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(f"▶️ Plan approved — executing ({prefix}).")

    elif action == "reopen":
        # Re-open an auto-closed task: user disagrees with the evaluator
        async with async_session() as s:
            await s.execute(
                sql_update(Task).where(Task.id == task.id).values(
                    status=TaskStatus.awaiting_user.value,
                    awaiting_since=datetime.now(timezone.utc))
            )
            await s.commit()
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(
            f"\U0001f513 Task `{prefix}` reopened — reply to this thread with "
            "what's wrong and I'll continue.", parse_mode="Markdown")

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
        lane = _lane_label(getattr(job, "resolved_provider", None), job.resolved_model,
                           getattr(job, "terminal_reason", None))
        lines = [f"Job `{str(job.id)[:8]}` — *{job.status}*"
                 + (f" \u00b7 `{lane}`" if lane else "")]
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
                    awaiting_since=None,
                )
            )
            await s.commit()
        job = await enqueue_job(
            f"User selected: {extra}",
            kind=JobKind.task.value,
            payload=None,
            created_by=f"telegram:{chat_id}",
            origin_channel="telegram",
            origin_ref=str(chat_id),
            origin_thread=str(task.thread_message_id) if task.thread_message_id else None,
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


def _done_dm_text(job_id: str, status: str, summary: str, lane: str) -> str:
    """The done/failed DM. Pure. `lane` is `_lane_label(...)` — appended to
    the headline when known (T7) so the owner sees which provider ran the
    job without opening /jobs; empty keeps the pre-T7 text byte-identical."""
    text = f"Job `{job_id[:8]}` *{status}*"
    if lane:
        text += f" \u00b7 `{lane}`"
    if summary:
        text += f"\n\n{summary}"
    if status == JobStatus.completed.value:
        text += f"\n\n💡 `/rate {job_id[:8]} 1-5`"
    return text


async def _job_lane(job_id: str) -> str:
    """Lane of a finished job from its row: the session stamps
    `resolved_provider`/`resolved_model` before the process starts, so every
    terminal path (timeout, refusal, executor failure) has them by the time
    `jobs:done` fires — the row, not the done payload, is the source of
    truth. Any lookup failure yields "" — the DM is never blocked on it."""
    try:
        async with async_session() as s:
            job = await s.get(Job, uuid.UUID(job_id))
    except Exception:  # noqa: BLE001 — surface-only; the DM still goes out
        logger.warning("could not read job row for done DM", job_id=job_id[:8])
        return ""
    if job is None:
        return ""
    return _lane_label(getattr(job, "resolved_provider", None), job.resolved_model,
                       getattr(job, "terminal_reason", None))


async def _deliver_done(app: Application, chat_id: int, job_id: str, payload: dict) -> None:
    status = payload.get("status", "unknown")
    summary = (payload.get("summary") or "")[:1500]
    lane = await _job_lane(job_id)
    text = _done_dm_text(job_id, status, summary, lane)
    await app.bot.send_message(chat_id, text, parse_mode="Markdown")


async def _handle_done_message(app: Application, channel: str, data: str) -> bool:
    """One `jobs:done:<id>` message (A6). Legacy renderer: sends only while
    the outbox is OFF — the runner publishes in both modes (A5 dual-write)
    and with the switch on the DoneCard comes from `_outbox_listener`. The
    `_job_to_chat` entry is popped either way so the dict never leaks.
    Returns True when a DM was sent."""
    job_id = channel.rsplit(":", 1)[-1]
    chat_id = _job_to_chat.pop(job_id, None)
    if not chat_id or settings.notify_outbox:
        return False
    try:
        payload = json.loads(data or "{}")
    except json.JSONDecodeError:
        payload = {}
    try:
        await _deliver_done(app, chat_id, job_id, payload)
    except Exception:
        logger.exception("failed to DM result", chat_id=chat_id, job_id=job_id)
        return False
    return True


async def _done_listener(app: Application) -> None:
    pubsub = redis.pubsub()
    await pubsub.psubscribe(f"{CHANNEL_JOB_DONE}:*")
    try:
        async for msg in pubsub.listen():
            if msg.get("type") != "pmessage":
                continue
            await _handle_done_message(app, msg.get("channel", ""), msg.get("data", "{}"))
    finally:
        await pubsub.punsubscribe(f"{CHANNEL_JOB_DONE}:*")


# ── Quota-pause notifier ────────────────────────────────────────────────────


def quota_paused_text(reset_at: datetime | None, reason: str, source: str) -> str:
    """The quota_paused DM body (pure). A reset time is labelled 'vendor' ONLY
    when a RateLimitEvent carried it (spec §2.8: the SDK emits resets_at on
    status transitions, never a 5h/7d gauge); the text heuristic and the
    default pause window are 'estimated'. No time → always 'estimated'."""
    label = "vendor" if (reset_at is not None and source == "vendor") else "estimated"
    reset_str = reset_at.strftime("%H:%M UTC") if reset_at else "unknown"
    return (f"⏸ Queue paused (subscription quota).\nReset at {reset_str} ({label}).\n"
            f"Reason: {reason[:200]}")


async def _quota_notifier(app: Application, *, poll_seconds: float = 60.0) -> None:
    """Periodically check quota state; one notice on pause and one on resume,
    per lane. Since A6 the notice is an OPS outbox row (`quota_paused` /
    `quota_resumed`, delivered in BOTH switch positions — D-P1-10), never a
    direct DM: the global Anthropic pause (A3: the reset line names its
    source) and every enabled non-Anthropic lane (T6 `is_provider_paused`,
    named in the body). `app` is kept for the `_post_init` call shape."""
    # lane → (paused, reason[:80]); a lane first seen paused notifies once.
    last_state: dict[str, tuple[bool, str]] = {}
    while True:
        await asyncio.sleep(poll_seconds)
        try:
            lanes: dict[str, tuple[bool, datetime | None, str]] = {
                models_registry.DEFAULT_PROVIDER: await quota.is_paused(),
            }
            for name in sorted(models_registry.enabled_providers()):
                if name != models_registry.DEFAULT_PROVIDER:
                    lanes[name] = await quota.is_provider_paused(name)
            for lane, (paused, reset_at, reason) in lanes.items():
                state = (paused, reason[:80])
                if state == last_state.get(lane, (False, "")):
                    continue
                if lane == models_registry.DEFAULT_PROVIDER:
                    text = (quota_paused_text(reset_at, reason, await quota.last_source())
                            if paused else "▶️ Queue resumed.")
                else:
                    text = (provider_paused_text(lane, reset_at, reason)
                            if paused else f"▶️ {lane} lane resumed.")
                await enqueue_notice(build_ops_notice(
                    kind="quota_paused" if paused else "quota_resumed",
                    severity="warn" if paused else "info",
                    text=text, subject=f"quota:{lane}"))
                last_state[lane] = state
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
            if settings.notify_outbox:
                continue     # renderer-side switch (A6): _outbox_listener sends these cards

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

                elif notify_type == "plan":
                    # Auto-approved plan (informational) — Cancel is the only gate
                    keyboard = InlineKeyboardMarkup([[
                        InlineKeyboardButton("Cancel plan", callback_data=f"cancel:{prefix}"),
                    ]])
                    send_kwargs = dict(
                        chat_id=task.chat_id,
                        text=f"📋 Plan for task {prefix} (executing now):\n\n{text_content[:3200]}",
                        reply_markup=keyboard,
                    )
                    if task.thread_message_id:
                        send_kwargs["reply_to_message_id"] = task.thread_message_id
                    await app.bot.send_message(**send_kwargs)

                elif notify_type == "plan_approval":
                    # Manual mode (PLAN_AUTO_APPROVE=false): explicit gate
                    keyboard = InlineKeyboardMarkup([[
                        InlineKeyboardButton("Approve plan", callback_data=f"approve_plan:{prefix}"),
                        InlineKeyboardButton("Cancel", callback_data=f"cancel:{prefix}"),
                    ]])
                    send_kwargs = dict(
                        chat_id=task.chat_id,
                        text=f"📋 Plan for task {prefix} — needs your approval:\n\n{text_content[:3200]}",
                        reply_markup=keyboard,
                    )
                    if task.thread_message_id:
                        send_kwargs["reply_to_message_id"] = task.thread_message_id
                    await app.bot.send_message(**send_kwargs)

                elif notify_type == "completed":
                    # Evaluator passed → task auto-closed with evidence.
                    # Reopen lets the human overrule the machine's verdict.
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("Reopen", callback_data=f"reopen:{prefix}"),
                         InlineKeyboardButton("View Details", callback_data=f"details:{prefix}")],
                        [
                            InlineKeyboardButton("1", callback_data=f"rate:{prefix}:1"),
                            InlineKeyboardButton("2", callback_data=f"rate:{prefix}:2"),
                            InlineKeyboardButton("3", callback_data=f"rate:{prefix}:3"),
                            InlineKeyboardButton("4", callback_data=f"rate:{prefix}:4"),
                            InlineKeyboardButton("5", callback_data=f"rate:{prefix}:5"),
                        ],
                    ])
                    send_kwargs = dict(
                        chat_id=task.chat_id,
                        text=f"✅ Task {prefix} completed and verified:\n\n{text_content[:3200]}",
                        reply_markup=keyboard,
                    )
                    if task.thread_message_id:
                        send_kwargs["reply_to_message_id"] = task.thread_message_id
                    await app.bot.send_message(**send_kwargs)

                elif notify_type == "progress":
                    # Informational update — no buttons, just a note in the thread
                    send_kwargs = dict(
                        chat_id=task.chat_id,
                        text=f"🔄 {text_content[:500]}",
                    )
                    if task.thread_message_id:
                        send_kwargs["reply_to_message_id"] = task.thread_message_id
                    await app.bot.send_message(**send_kwargs)

                elif notify_type == "failed":
                    # Terminal failure — notify in thread
                    send_kwargs = dict(
                        chat_id=task.chat_id,
                        text=f"❌ {text_content[:1000]}",
                    )
                    if task.thread_message_id:
                        send_kwargs["reply_to_message_id"] = task.thread_message_id
                    await app.bot.send_message(**send_kwargs)

                elif notify_type == "review_flagged":
                    # Post-session code review flagged a blocker/error on an
                    # already-completed (and pushed) job — surface it in-thread
                    # so it isn't buried under the completion message.
                    send_kwargs = dict(
                        chat_id=task.chat_id,
                        text=f"⚠️ {text_content[:1000]}",
                    )
                    if task.thread_message_id:
                        send_kwargs["reply_to_message_id"] = task.thread_message_id
                    await app.bot.send_message(**send_kwargs)

            except Exception:
                logger.exception("failed to send task notification", task_id=task_id)
    finally:
        await pubsub.unsubscribe("tasks:notify")


# ── Outbox delivery (Observability Phase 1, A6) ─────────────────────────────

_OUTBOX_POLL_SECONDS = 30


def _safe_send_error(exc: BaseException) -> str:
    """Token-free text for `notifications.last_error` (§4 secrets rule).
    `TelegramSendError` is safe by construction; anything else keeps its
    type name and message with the bot token redacted. ≤ 300 chars."""
    text = str(exc) if isinstance(exc, TelegramSendError) else f"{type(exc).__name__}: {exc}"
    token = settings.telegram_bot_token
    if token:
        text = text.replace(token, "[REDACTED]")
    return text[:300]


async def _drain_outbox(app: Application, *, legacy_mode: bool) -> tuple[int, int, int]:
    """Deliver every pending outbox row once. Returns (sent, failed, skipped).
    Each row is CLAIMED first (status → sending, attempts+1): a concurrent
    `python -m src.notify drain` selects the same pending rows, and without
    the claim both would send the DM. In `legacy_mode` (NOTIFY_OUTBOX=0,
    D-P1-10) job/task rows are marked `skipped` — the legacy `jobs:done` /
    `tasks:notify` renderers cover them — and only the OPS kinds (quota,
    schedule_deferred, ops_alert, …), which have no legacy path, are sent.
    `skipped` counts both those rows and rows another drainer claimed."""
    ids = settings.allowed_chat_ids
    if not ids:
        return 0, 0, 0
    owner = ids[0]
    sent = failed = skipped = 0
    for row in await pending_notices(limit=20):
        attempts_before = row.attempts          # claim bumps it; mark_failed re-derives from this
        if not await claim_notice(row.id):
            skipped += 1                        # someone else has it
            continue
        if legacy_mode and row.notice_kind not in OPS_NOTICE_KINDS:
            await mark_skipped(row.id, "legacy_mode")
            skipped += 1
            continue
        try:
            ref = await send_via_bot(app.bot, render_telegram(row, owner_chat_id=owner))
            await mark_sent(row.id, str(ref), subject_type=row.subject_type, subject_id=row.subject_id)
            sent += 1
        except Exception as exc:  # noqa: BLE001 — recorded on the row, retried with backoff
            err = _safe_send_error(exc)
            await mark_failed(row.id, err, attempts_so_far=attempts_before,
                              subject_type=row.subject_type, subject_id=row.subject_id)
            failed += 1
            logger.warning("outbox delivery failed", notice_id=str(row.id), error=err[:120])
    return sent, failed, skipped


async def _outbox_listener(app: Application, *, legacy_mode: bool) -> None:
    """Drain on every `notify:outbox` nudge and at least every 30 s. The poll
    is what makes a bot restart lossless: rows written while we were down
    are still `pending` (exit criterion 'bot restart loses no DM'). Rows a
    crashed drainer left `sending` past their lease are released first.
    Runs in BOTH switch positions; `legacy_mode` only narrows what it sends."""
    try:
        released = await release_stuck_sending()
        if released:
            logger.warning("outbox: released stuck sending rows", count=released)
    except Exception:
        logger.exception("outbox: release_stuck_sending failed (continuing)")
    pubsub = redis.pubsub()
    await pubsub.subscribe(CHANNEL_NOTIFY_OUTBOX)
    try:
        while True:
            try:
                await pubsub.get_message(ignore_subscribe_messages=True,
                                         timeout=_OUTBOX_POLL_SECONDS)
                await _drain_outbox(app, legacy_mode=legacy_mode)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("outbox listener iteration failed (continuing)")
                await asyncio.sleep(2)
    finally:
        await pubsub.unsubscribe(CHANNEL_NOTIFY_OUTBOX)


async def _post_init(app: Application) -> None:
    # Every listener always runs (the runner dual-writes). The switch is
    # renderer-side (D-P1-10): on → the outbox listener delivers every row and
    # the legacy renderers are gated off; off → legacy_mode, where the
    # listener still delivers the ops kinds. Flipping it = bot-only restart.
    asyncio.create_task(_done_listener(app))
    asyncio.create_task(_task_notifier(app))
    asyncio.create_task(_quota_notifier(app))
    asyncio.create_task(_outbox_listener(app, legacy_mode=not settings.notify_outbox))


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    # httpx logs one INFO line per getUpdates long-poll (~every 10s, forever).
    # That was ~46MB of bot.err.log with no rotation (EVALUATION_2026-08-30
    # F7.3). WARNING keeps real transport errors visible.
    logging.getLogger("httpx").setLevel(logging.WARNING)
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
    app.add_handler(CommandHandler("tasks", cmd_status))  # alias
    app.add_handler(CommandHandler("jobs", cmd_jobs))
    # Admin commands
    app.add_handler(CommandHandler("chat", cmd_chat))
    app.add_handler(CommandHandler("god", cmd_god))
    app.add_handler(CommandHandler("resume", cmd_resume))
    app.add_handler(CommandHandler("clear", cmd_clear))
    app.add_handler(CommandHandler("schedule", cmd_schedule))
    app.add_handler(CommandHandler("projects", cmd_projects))
    # Thread reply + inline button handlers
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.REPLY, _handle_thread_reply))
    # NL-first (P2): bare messages are asks — no /task prefix needed
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.REPLY, _handle_plain_text))
    app.add_handler(CallbackQueryHandler(_handle_button))

    logger.info("telegram bot starting")
    app.run_polling(close_loop=False)


if __name__ == "__main__":
    main()
