"""
Telegram gateway. Commands: /task /status /cancel /chat /projects /rate /resume /help.

Flag syntax (parsed off the front of /task and /chat descriptions):
    /task --model=opus-4-7 --effort=high  fix the NaN bug in market-tracker
    /task --effort=max  design the props model schema

Flags land in job.payload and take precedence over skill frontmatter.

Run: `python -m src.gateway.telegram_bot`
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid

import structlog
from sqlalchemy import select, update as sql_update
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from src.config import settings
from src.db import CHANNEL_JOB_DONE, async_session, redis
from src.gateway.jobs import cancel_job, enqueue_job, find_job_by_prefix
from src.models import Job, JobKind, JobStatus, Project
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


async def cmd_help(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    if await _guard(update) is None:
        return
    await update.message.reply_text(
        "Commands:\n"
        "/task <description> — submit a task\n"
        "/chat <message> — one-shot conversation\n"
        "/status <id_prefix> — job status\n"
        "/cancel <id_prefix> — request cancellation\n"
        "/rate <id_prefix> <1-5> — rate a completed job (trains the tuner)\n"
        "/projects — list hosted projects\n"
        "/resume — clear a quota pause manually\n"
        "/help — this message\n\n"
        "Flags on /task: --model=opus|sonnet|haiku  --effort=low|medium|high|xhigh|max\n"
        "Example: /task --model=opus --effort=high  write me a FastAPI endpoint for X"
    )


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

    job = await enqueue_job(
        description,
        kind=kind,
        payload=flags or None,
        created_by=f"telegram:{chat_id}",
    )
    _job_to_chat[str(job.id)] = chat_id

    flag_summary = ""
    if flags:
        flag_summary = f"\n_flags: {', '.join(f'{k}={v}' for k, v in flags.items())}_"
    await update.message.reply_text(
        f"Queued as `{str(job.id)[:8]}`{flag_summary}\nI'll DM when it's done.",
        parse_mode="Markdown",
    )


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


async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if await _guard(update) is None:
        return
    if not ctx.args:
        await update.message.reply_text("Usage: /status <job_id_prefix>")
        return
    job = await find_job_by_prefix(ctx.args[0])
    if not job:
        await update.message.reply_text("Job not found (or prefix ambiguous).")
        return

    lines = [
        f"Job `{str(job.id)[:8]}` — *{job.status}*",
        f"Kind: {job.kind}" + (f"  →  skill: {job.resolved_skill}" if job.resolved_skill else ""),
    ]
    if job.resolved_model:
        effort = job.resolved_effort or "medium"
        lines.append(f"Model: {job.resolved_model} / {effort}")
    lines.append(f"Created: {job.created_at.strftime('%Y-%m-%d %H:%M UTC')}")

    if job.result:
        summary = (job.result.get("summary") or "")[:800]
        if summary:
            lines.append("")
            lines.append(summary)
            if len(job.result.get("summary", "")) > 800:
                lines.append("\n_(truncated — see web dashboard)_")
    if job.error_message:
        lines.append(f"\nError: `{job.error_message[:200]}`")

    if job.status == JobStatus.completed.value and job.user_rating is None:
        lines.append(f"\n💡 rate with `/rate {str(job.id)[:8]} 1-5` to train the tuner")

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


# ── Done-notification listener ──────────────────────────────────────────────


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


async def _post_init(app: Application) -> None:
    asyncio.create_task(_done_listener(app))
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
    app.add_handler(CommandHandler("start", cmd_help))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("task", cmd_task))
    app.add_handler(CommandHandler("chat", cmd_chat))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("cancel", cmd_cancel))
    app.add_handler(CommandHandler("rate", cmd_rate))
    app.add_handler(CommandHandler("projects", cmd_projects))
    app.add_handler(CommandHandler("resume", cmd_resume))

    logger.info("telegram bot starting")
    app.run_polling(close_loop=False)


if __name__ == "__main__":
    main()
