# Telegram Interface Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the 16-command Telegram interface with thread-based conversations, inline buttons, and 4-level error handling.

**Architecture:** Each `/task` creates a reply chain (thread). User replies in the thread are detected via `reply_to_message` and routed as task continuations. Discrete actions (approve, cancel, rate) use inline keyboard buttons with `CallbackQueryHandler`. All handlers wrapped in error-safe decorators with retry + self-diagnose.

**Tech Stack:** python-telegram-bot (InlineKeyboardButton, InlineKeyboardMarkup, CallbackQueryHandler, MessageHandler), SQLAlchemy (migration for thread_message_id), existing Redis pub/sub for notifications.

---

### File Structure

| File | Responsibility | Change |
|------|---------------|--------|
| `alembic/versions/004_task_thread_message_id.py` | Add `thread_message_id` to tasks table | CREATE |
| `src/models.py` | Add `thread_message_id` field to Task model | MODIFY |
| `src/gateway/telegram_bot.py` | Full rewrite of command handlers + add thread/button/error logic | MODIFY (major) |
| `src/runner/main.py` | Update `_update_task_after_job` to detect `task_choices` events | MODIFY |
| `src/audit_log.py` | Document `task_choices` event kind | MODIFY |
| `tests/test_telegram_commands.py` | Tests for error wrapper, button callback parser, reply detection | MODIFY |
| `.context/modules/gateway/CONTEXT.md` | Update commands list, public interface | MODIFY |
| `.context/modules/gateway/CHANGELOG.md` | New entry | MODIFY |
| `.context/modules/db/CONTEXT.md` | Update schema count | MODIFY |
| `.context/modules/db/CHANGELOG.md` | New entry | MODIFY |

---

### Task 1: Migration + Model — Add thread_message_id

**Files:**
- Create: `alembic/versions/004_task_thread_message_id.py`
- Modify: `src/models.py`

- [ ] **Step 1: Write the migration**

```python
# alembic/versions/004_task_thread_message_id.py
"""Add thread_message_id to tasks table.

Revision ID: 004
Revises: 003
Create Date: 2026-04-20
"""
from __future__ import annotations
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column("tasks", sa.Column("thread_message_id", sa.BigInteger, nullable=True))

def downgrade() -> None:
    op.drop_column("tasks", "thread_message_id")
```

- [ ] **Step 2: Add field to Task model in `src/models.py`**

After the `chat_id` field on the Task class, add:

```python
thread_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
# ^ Telegram message ID of the bot's root reply — used to post in the right thread
```

- [ ] **Step 3: Apply migration**

Run: `cd "/Users/alfredbot.ai.butler/Library/Application Support/ai-server" && pipenv run alembic upgrade head`
Expected: `Running upgrade 003 -> 004`

- [ ] **Step 4: Verify column exists**

Run: `psql assistant -c "\d tasks" | grep thread_message_id`
Expected: `thread_message_id | bigint`

- [ ] **Step 5: Run tests**

Run: `SERVER_ROOT=$(pwd) POSTGRES_DSN="postgresql+asyncpg://x:y@localhost/x" PYTHONPATH=. python3 -m pytest tests/ -q`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add alembic/versions/004_task_thread_message_id.py src/models.py
git commit -m "feat: add thread_message_id to tasks table for Telegram threads"
```

---

### Task 2: Error-safe handler decorator

**Files:**
- Modify: `src/gateway/telegram_bot.py`
- Test: `tests/test_telegram_commands.py`

- [ ] **Step 1: Write tests for the error decorator**

```python
# In tests/test_telegram_commands.py, add:

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

class TestErrorSafeDecorator:
    def test_successful_handler_passes_through(self):
        """error_safe should not interfere with normal execution."""
        from src.gateway.telegram_bot import _error_safe
        calls = []
        @_error_safe
        async def handler(update, ctx):
            calls.append(1)
        update = MagicMock()
        update.effective_chat.id = 123
        update.message.reply_text = AsyncMock()
        asyncio.run(handler(update, None))
        assert calls == [1]

    def test_exception_sends_error_reply(self):
        """error_safe should reply with error message on exception."""
        from src.gateway.telegram_bot import _error_safe
        @_error_safe
        async def handler(update, ctx):
            raise ValueError("test boom")
        update = MagicMock()
        update.effective_chat.id = 123
        update.message.reply_text = AsyncMock()
        asyncio.run(handler(update, None))
        update.message.reply_text.assert_called()
        msg = update.message.reply_text.call_args[0][0]
        assert "Something went wrong" in msg
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=. python3 -m pytest tests/test_telegram_commands.py::TestErrorSafeDecorator -v`
Expected: FAIL — `_error_safe` doesn't exist yet

- [ ] **Step 3: Implement the error-safe decorator**

Add to `src/gateway/telegram_bot.py` after the `_esc_md` helper:

```python
import functools
import traceback

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
                    f"⚠️ Retrying... ({type(first_exc).__name__})"
                )
                await asyncio.sleep(1)
                return await handler(update, ctx)
            except Exception as retry_exc:
                # Level 3: Dispatch self-diagnose
                tb = traceback.format_exc()
                try:
                    diag_job = await enqueue_job(
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
                        f"⚠️ Failed after retry. Auto-diagnosing...\n"
                        f"I've dispatched a self-diagnose job to investigate."
                    )
                except Exception:
                    # Level 4: Graceful degradation
                    await update.message.reply_text(
                        f"⚠️ System error: {type(retry_exc).__name__}\n"
                        f"Try again in a few minutes."
                    )
    return wrapper
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=. python3 -m pytest tests/test_telegram_commands.py::TestErrorSafeDecorator -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/gateway/telegram_bot.py tests/test_telegram_commands.py
git commit -m "feat: add _error_safe decorator with 4-level error handling"
```

---

### Task 3: Thread-based /task command

**Files:**
- Modify: `src/gateway/telegram_bot.py` (rewrite `cmd_task`)

- [ ] **Step 1: Rewrite cmd_task to create thread**

Replace the existing `cmd_task` with a version that:
1. Creates Task + user turn (same as now)
2. Replies to the user's message (creating the thread) instead of sending a standalone message
3. Stores `thread_message_id` on the Task
4. Sends a [Cancel] inline button with the reply
5. Wraps in `@_error_safe`

Key change: use `update.message.reply_text(..., reply_to_message_id=update.message.message_id)` to create the reply chain, and save the returned `Message.message_id` as `thread_message_id`.

```python
@_error_safe
async def cmd_task(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = await _guard(update)
    if chat_id is None:
        return
    raw = " ".join(ctx.args).strip()
    if not raw:
        await update.message.reply_text("Usage: /task <what you want me to do>")
        return

    description, flags = parse_flags(raw)
    if not description:
        await update.message.reply_text("Put the task description after any flags.")
        return

    kind = flags.pop("kind_override", JobKind.task.value)

    # Create task
    task = Task(description=description, created_by=f"telegram:{chat_id}", chat_id=chat_id)
    async with async_session() as s:
        s.add(task)
        await s.commit()
        await s.refresh(task)

    # Record user turn
    async with async_session() as s:
        s.add(TaskTurn(task_id=task.id, turn_number=1, role="user", content=description))
        await s.commit()

    # Enqueue job
    job = await enqueue_job(description, kind=kind, payload=flags or None,
                            created_by=f"telegram:{chat_id}")
    async with async_session() as s:
        await s.execute(sql_update(Job).where(Job.id == job.id).values(task_id=task.id))
        await s.commit()

    # Reply to user message (creates thread) with cancel button
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("Cancel", callback_data=f"cancel:{str(task.id)[:8]}"),
    ]])
    reply = await update.message.reply_text(
        f"🔄 Working on it... ({_esc_md(description[:60])})",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )

    # Store thread message ID
    async with async_session() as s:
        await s.execute(sql_update(Task).where(Task.id == task.id).values(
            thread_message_id=reply.message_id,
        ))
        await s.commit()
```

- [ ] **Step 2: Run full test suite**

Run: `SERVER_ROOT=$(pwd) POSTGRES_DSN="postgresql+asyncpg://x:y@localhost/x" PYTHONPATH=. python3 -m pytest tests/ -q`
Expected: all pass

- [ ] **Step 3: Commit**

```bash
git add src/gateway/telegram_bot.py
git commit -m "feat: thread-based /task command with inline cancel button"
```

---

### Task 4: Plain text reply detection

**Files:**
- Modify: `src/gateway/telegram_bot.py` (add MessageHandler + reply router)

- [ ] **Step 1: Write test for reply detection helper**

```python
# In tests/test_telegram_commands.py, add:

class TestReplyDetection:
    def test_extract_task_id_from_callback(self):
        from src.gateway.telegram_bot import _parse_callback
        action, task_prefix, extra = _parse_callback("approve:abc12345")
        assert action == "approve"
        assert task_prefix == "abc12345"
        assert extra is None

    def test_extract_with_extra(self):
        from src.gateway.telegram_bot import _parse_callback
        action, task_prefix, extra = _parse_callback("rate:abc12345:4")
        assert action == "rate"
        assert task_prefix == "abc12345"
        assert extra == "4"

    def test_malformed_callback(self):
        from src.gateway.telegram_bot import _parse_callback
        action, task_prefix, extra = _parse_callback("garbage")
        assert action == "garbage"
        assert task_prefix is None
```

- [ ] **Step 2: Implement the reply handler and callback parser**

Add `_parse_callback` helper:

```python
def _parse_callback(data: str) -> tuple[str, str | None, str | None]:
    """Parse 'action:task_prefix[:extra]' callback data."""
    parts = data.split(":", 2)
    action = parts[0]
    task_prefix = parts[1] if len(parts) > 1 else None
    extra = parts[2] if len(parts) > 2 else None
    return action, task_prefix, extra
```

Add plain text reply handler:

```python
@_error_safe
async def _handle_thread_reply(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle plain text replies in task threads."""
    chat_id = await _guard(update)
    if chat_id is None:
        return
    if not update.message.reply_to_message:
        return  # not a reply — ignore

    reply_msg_id = update.message.reply_to_message.message_id

    # Look up task by thread_message_id
    async with async_session() as s:
        result = await s.execute(
            select(Task).where(Task.thread_message_id == reply_msg_id)
        )
        task = result.scalar_one_or_none()

    if not task:
        # Maybe replying to a bot message within the thread (not the root).
        # Try looking up by chat_id + active status.
        return

    if task.status in (TaskStatus.completed.value, TaskStatus.failed.value):
        await update.message.reply_text("This task is already finished.")
        return

    user_text = update.message.text.strip()
    if not user_text:
        return

    # Record user turn
    from sqlalchemy import func as sqlfunc
    async with async_session() as s:
        max_r = await s.execute(
            select(sqlfunc.max(TaskTurn.turn_number)).where(TaskTurn.task_id == task.id)
        )
        last = max_r.scalar() or 0
        s.add(TaskTurn(task_id=task.id, turn_number=last + 1, role="user", content=user_text))
        await s.execute(sql_update(Task).where(Task.id == task.id).values(
            status=TaskStatus.active.value))
        await s.commit()

    # Enqueue continuation job
    job = await enqueue_job(user_text, kind=JobKind.task.value, payload=None,
                            created_by=f"telegram:{chat_id}")
    async with async_session() as s:
        await s.execute(sql_update(Job).where(Job.id == job.id).values(task_id=task.id))
        await s.commit()

    await update.message.reply_text("🔄 Continuing...")
```

Register in `main()`:

```python
from telegram.ext import MessageHandler, filters, CallbackQueryHandler
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.REPLY, _handle_thread_reply))
```

- [ ] **Step 3: Run tests**

Run: `PYTHONPATH=. python3 -m pytest tests/test_telegram_commands.py -v`
Expected: all pass

- [ ] **Step 4: Commit**

```bash
git add src/gateway/telegram_bot.py tests/test_telegram_commands.py
git commit -m "feat: plain text reply detection in task threads"
```

---

### Task 5: Inline button callback handler

**Files:**
- Modify: `src/gateway/telegram_bot.py` (add CallbackQueryHandler)

- [ ] **Step 1: Implement the callback handler**

```python
@_error_safe
async def _handle_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline keyboard button presses."""
    query = update.callback_query
    await query.answer()  # acknowledge the button press

    action, task_prefix, extra = _parse_callback(query.data or "")
    if not task_prefix:
        return

    task = await _find_task_by_prefix(task_prefix)
    if not task:
        await query.edit_message_text("Task not found.")
        return

    if action == "approve":
        from sqlalchemy import func as sqlfunc
        async with async_session() as s:
            max_r = await s.execute(
                select(sqlfunc.max(TaskTurn.turn_number)).where(TaskTurn.task_id == task.id))
            last = max_r.scalar() or 0
            s.add(TaskTurn(task_id=task.id, turn_number=last + 1,
                          role="system", content="User approved."))
            await s.execute(sql_update(Task).where(Task.id == task.id).values(
                status=TaskStatus.completed.value))
            await s.commit()
        await query.edit_message_reply_markup(reply_markup=None)  # remove buttons
        await query.message.reply_text("✅ Task approved and complete.")

    elif action == "cancel":
        # Find the running job for this task
        async with async_session() as s:
            result = await s.execute(
                select(Job).where(Job.task_id == task.id)
                .where(Job.status.in_([JobStatus.queued.value, JobStatus.running.value]))
                .order_by(Job.created_at.desc()).limit(1))
            job = result.scalar_one_or_none()
        if job:
            await cancel_job(job.id)
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text("🚫 Cancelled.")

    elif action == "feedback":
        await query.message.reply_text("Send your feedback as a reply to this message.")

    elif action == "details":
        # Fetch latest job for this task
        async with async_session() as s:
            result = await s.execute(
                select(Job).where(Job.task_id == task.id)
                .order_by(Job.created_at.desc()).limit(1))
            job = result.scalar_one_or_none()
        if job:
            from src import audit_log
            summary = audit_log.read(job.id, limit=5)
            detail_lines = [f"*Job* `{str(job.id)[:8]}` — {job.status}"]
            if job.error_message:
                detail_lines.append(f"Error: {_esc_md(job.error_message[:300])}")
            if job.result and job.result.get("summary"):
                detail_lines.append(f"\n{_esc_md(job.result['summary'][:500])}")
            await query.message.reply_text("\n".join(detail_lines), parse_mode="Markdown")
        else:
            await query.message.reply_text("No job found for this task.")

    elif action == "rate" and extra:
        try:
            rating = int(extra)
        except ValueError:
            return
        async with async_session() as s:
            result = await s.execute(
                select(Job).where(Job.task_id == task.id)
                .order_by(Job.created_at.desc()).limit(1))
            job = result.scalar_one_or_none()
        if job:
            async with async_session() as s:
                await s.execute(sql_update(Job).where(Job.id == job.id).values(user_rating=rating))
                await s.commit()
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(f"Rated {rating}/5. Thanks!")

    elif action == "choice" and extra:
        try:
            choice_idx = int(extra)
        except ValueError:
            return
        # Record as user turn with the choice text from the button
        button_text = query.message.reply_markup.inline_keyboard[0][choice_idx].text if query.message.reply_markup else f"Choice {choice_idx}"
        from sqlalchemy import func as sqlfunc
        async with async_session() as s:
            max_r = await s.execute(
                select(sqlfunc.max(TaskTurn.turn_number)).where(TaskTurn.task_id == task.id))
            last = max_r.scalar() or 0
            s.add(TaskTurn(task_id=task.id, turn_number=last + 1,
                          role="user", content=button_text))
            await s.execute(sql_update(Task).where(Task.id == task.id).values(
                status=TaskStatus.active.value))
            await s.commit()
        job = await enqueue_job(button_text, kind=JobKind.task.value, payload=None,
                                created_by=f"telegram:{task.chat_id}")
        async with async_session() as s:
            await s.execute(sql_update(Job).where(Job.id == job.id).values(task_id=task.id))
            await s.commit()
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(f"🔄 Continuing with: {_esc_md(button_text)}")
```

Register in `main()`:

```python
app.add_handler(CallbackQueryHandler(_handle_button))
```

- [ ] **Step 2: Run full tests**

Run: `SERVER_ROOT=$(pwd) POSTGRES_DSN="postgresql+asyncpg://x:y@localhost/x" PYTHONPATH=. python3 -m pytest tests/ -q`
Expected: all pass

- [ ] **Step 3: Commit**

```bash
git add src/gateway/telegram_bot.py
git commit -m "feat: inline button callback handler for approve/cancel/rate/details/choice"
```

---

### Task 6: Update task notification to use threads + buttons

**Files:**
- Modify: `src/gateway/telegram_bot.py` (rewrite `_task_notifier`)
- Modify: `src/runner/main.py` (detect `task_choices` events)

- [ ] **Step 1: Update _task_notifier to reply in threads with buttons**

Rewrite `_task_notifier` to:
1. Look up the task's `thread_message_id`
2. Reply in the thread (not DM separately)
3. Attach inline buttons based on notification type
4. Also send a short summary DM in the main chat

For `approval_request`: attach `[Approve] [Send Feedback] [View Details] [Rate 1-5]` buttons.
For `question`: attach text prompt (or `[Option]` buttons if choices provided).
For `task_choices`: attach option buttons.

- [ ] **Step 2: Update `_update_task_after_job` in main.py to detect task_choices**

Add detection for `task_choices` events before `task_question`:

```python
choices_event = None
for evt in events:
    if evt.get("kind") == "task_choices":
        choices_event = evt
    elif evt.get("kind") == "task_question":
        question = evt.get("question", "")
    elif evt.get("kind") == "task_complete":
        is_complete = True

if choices_event:
    # Publish with choices for button rendering
    await redis.publish("tasks:notify", json.dumps({
        "task_id": str(job.task_id),
        "type": "choices",
        "question": choices_event.get("question", ""),
        "options": choices_event.get("options", []),
    }))
```

- [ ] **Step 3: Document task_choices in audit_log.py**

Already partially done. Verify `task_choices` is listed in the docstring.

- [ ] **Step 4: Run full tests**

Run: `SERVER_ROOT=$(pwd) POSTGRES_DSN="postgresql+asyncpg://x:y@localhost/x" PYTHONPATH=. python3 -m pytest tests/ -q`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add src/gateway/telegram_bot.py src/runner/main.py src/audit_log.py
git commit -m "feat: thread-based notifications with inline buttons"
```

---

### Task 7: Rewrite /status, /jobs, /help + remove old commands

**Files:**
- Modify: `src/gateway/telegram_bot.py`

- [ ] **Step 1: Rewrite /help to show 4 primary commands**

```python
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
        "_Admin: /chat, /resume, /schedule_",
        parse_mode="Markdown",
    )
```

- [ ] **Step 2: Rewrite /status to show active tasks with thread context**

Show active tasks with description, status, and prompt to "find the thread above to continue."

- [ ] **Step 3: Keep /jobs as-is** (already works well with action hints)

- [ ] **Step 4: Remove old command handlers**

Remove registration of: `cmd_reply`, `cmd_approve`, `cmd_tasks`, `cmd_cancel`, `cmd_rate`, `cmd_proposals`.
Keep the functions temporarily (dead code) or delete — the functionality now lives in buttons and threads.

- [ ] **Step 5: Update module docstring**

```python
"""
Telegram gateway. Commands: /task /status /jobs /help /chat /resume /schedule.
Thread-based: reply in task threads to continue. Inline buttons for actions.
"""
```

- [ ] **Step 6: Apply @_error_safe to all remaining handlers**

Wrap `cmd_status`, `cmd_jobs`, `cmd_chat`, `cmd_resume`, `cmd_schedule` with `@_error_safe`.

- [ ] **Step 7: Run full tests + lint**

Run: `python3 scripts/lint_docs.py && SERVER_ROOT=$(pwd) POSTGRES_DSN="postgresql+asyncpg://x:y@localhost/x" PYTHONPATH=. python3 -m pytest tests/ -q`
Expected: all pass

- [ ] **Step 8: Commit**

```bash
git add src/gateway/telegram_bot.py
git commit -m "feat: rewrite /help, /status + remove old slash commands"
```

---

### Task 8: Documentation updates

**Files:**
- Modify: `.context/modules/gateway/CONTEXT.md`
- Modify: `.context/modules/gateway/CHANGELOG.md`
- Modify: `.context/modules/db/CONTEXT.md`
- Modify: `.context/modules/db/CHANGELOG.md`

- [ ] **Step 1: Update gateway CONTEXT.md**

Replace Telegram commands list with:
```
- Telegram commands: `/task`, `/status`, `/jobs`, `/help`, `/chat`, `/resume`, `/schedule`
- Thread-based interaction: plain text replies in task threads auto-route as continuations
- Inline keyboard buttons: approve, cancel, rate, view details, structured choices
- CallbackQueryHandler: parses `action:task_prefix[:extra]` callback data
```

- [ ] **Step 2: Update gateway CHANGELOG.md** with redesign entry

- [ ] **Step 3: Update db CONTEXT.md** — note `thread_message_id` on tasks table

- [ ] **Step 4: Update db CHANGELOG.md** with migration entry

- [ ] **Step 5: Run lint**

Run: `python3 scripts/lint_docs.py`
Expected: 8/8 PASS

- [ ] **Step 6: Commit**

```bash
git add .context/modules/gateway/ .context/modules/db/
git commit -m "docs: update gateway + db CONTEXT/CHANGELOG for interface redesign"
```

---

### Task 9: Restart services + manual smoke test

- [ ] **Step 1: Apply migration**

```bash
pipenv run alembic upgrade head
```

- [ ] **Step 2: Restart bot and runner**

```bash
launchctl kickstart -k gui/$(id -u)/com.assistant.bot
launchctl kickstart -k gui/$(id -u)/com.assistant.runner
```

- [ ] **Step 3: Smoke test in Telegram**

1. Send `/help` — should show 4 commands
2. Send `/task test the new thread interface` — should reply in-thread with cancel button
3. Reply in the thread with plain text — should route as continuation
4. When task completes, should see approve/feedback/details buttons
5. Tap [Approve] — should mark complete
6. Send `/status` — should show no active tasks
7. Send `/jobs` — should list the test jobs

- [ ] **Step 4: Push all changes**

```bash
git push origin main
```
