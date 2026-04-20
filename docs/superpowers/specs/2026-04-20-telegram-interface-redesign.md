# Telegram Interface Redesign

**Date**: 2026-04-20
**Status**: Approved design, ready for implementation planning

## Problem

The current Telegram interface has 16 slash commands, two ID systems (task prefixes and job prefixes), silent failures, and no conversational flow. Users must memorize commands and type UUIDs to interact. Errors crash silently. The gap between "submit a task" and "iterate on the result" is too wide.

## Design

### Thread-Based Conversations

Every `/task` creates a Telegram reply chain (thread). All interaction for that task happens in the thread.

**Starting a task:**
- User sends: `/task fix the login bug in market-tracker`
- Bot replies to that message (creating a thread): "Working on it..." + task summary
- Bot stores the root `message_id` on the Task DB row for future replies

**Replying to a task:**
- Any plain text reply in the thread is treated as user input to the task
- No `/reply <id>` needed — the bot detects it's a reply to a task thread via `message.reply_to_message`
- The reply creates a new turn + enqueues a continuation job with full context

**Multiple active tasks:**
- Each task is its own thread — no ambiguity about which task you're talking to
- `/status` lists all active tasks with enough context to find the right thread

### Inline Keyboard Buttons

Discrete actions use Telegram inline keyboard buttons. Three patterns:

**Approval prompt** (task completed):
```
[Approve]  [Send Feedback]  [View Details]
```

**Choice prompt** (task needs structured input):
```
[Option A]  [Option B]  [Option C]
```
Skills emit choices via a new `task_choices` audit event with a list of option strings.

**Progress update** (job running):
```
[Cancel]
```

Button callbacks are handled via `CallbackQueryHandler`. Each button encodes the action + task_id in its `callback_data` (e.g., `approve:abc12345`).

### Notifications

**In-thread**: Every state change posts in the thread:
- Job started: "Working... (skill-name)"
- Job completed: result + buttons
- Job failed: error + retry status

**Summary DM** (main chat, not in thread): When a task needs attention:
```
Task "fix the login bug" needs your approval — reply in thread above
```
Ensures visibility even when the thread isn't open.

### Slash Commands (reduced to 4)

| Command | Purpose |
|---------|---------|
| `/task <description>` | Start a new task (creates thread) |
| `/status` | List active tasks with status |
| `/jobs [N]` | List recent N jobs with status |
| `/help` | Explain the interface |

Everything else (reply, approve, cancel, rate, view details) happens via buttons or plain text in threads.

### Error Handling (4 levels)

1. **Immediate reply**: Every command failure replies to the user with the error. No silent crashes. All handlers wrapped in try/except.

2. **Auto-retry**: Transient errors (DB timeout, Redis, Telegram API) retry once after 2s. User sees "Retrying..."

3. **Self-diagnose dispatch**: If retry fails, auto-enqueue a `self-diagnose` job with the error context (message, stack trace, command). User sees "Auto-diagnosing... I'll DM you when resolved."

4. **Graceful degradation**: If self-diagnose can't be enqueued (total system failure), reply with plain error and manual recovery instructions.

### Database Changes

Add to `tasks` table:
- `thread_message_id: BigInteger NULL` — Telegram message ID of the root message (for replying in the right thread)

### Migration from Current Commands

Commands being removed (functionality moves to threads/buttons):
- `/reply` → plain text in thread
- `/approve` → [Approve] button
- `/tasks` → merged into `/status`
- `/cancel` → [Cancel] button
- `/rate` → [Rate 1-5] buttons after completion
- `/proposals` → accessible via `/status` or a button
- `/resume` → keep as admin-only (quota management)
- `/schedule` → keep as admin-only

Kept but not promoted in `/help`:
- `/chat` — one-shot conversation (no thread, no task tracking)
- `/resume` — admin: clear quota pause
- `/schedule` — admin: manage cron schedules

Final command set shown in `/help`: `/task`, `/status`, `/jobs`, `/help`
Full command set: `/task`, `/status`, `/jobs`, `/help`, `/chat`, `/resume`, `/schedule`

### Reply Detection Logic

```
message received
  ├── starts with "/" → route to command handler
  └── is reply to a message?
        ├── no → ignore (or treat as /chat)
        └── yes → look up Task by thread_message_id
              ├── found → treat as task continuation
              └── not found → ignore
```

### Inline Button Callback Data Format

```
action:task_id_prefix[:extra]
```

Examples:
- `approve:abc12345`
- `cancel:abc12345`
- `feedback:abc12345` (triggers "send your reply" prompt)
- `details:abc12345`
- `rate:abc12345:4` (rate 4/5)
- `choice:abc12345:2` (pick option index 2)

### New Audit Event Kinds

- `task_choices`: `{"kind": "task_choices", "job_id": "...", "question": "...", "options": ["A", "B", "C"]}`
  Emitted by skills that want to present structured choices to the user.
  Supersedes `task_question` when options are present — the runner checks
  for `task_choices` first, falls back to `task_question` for open-ended.

## Out of Scope

- Web dashboard redesign (this is Telegram-only)
- Telegram Bot API webhook mode (staying with polling)
- Group chat support (this is a 1:1 DM bot)
- Rich media in responses (images, files) — text only for now
