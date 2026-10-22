"""
Telegram renderer + senders for outbox rows (Observability Phase 1, A4).

The ONLY module that knows Telegram's limits: 4096 chars/message, 64
bytes/callback_data, ≤ 8 buttons. Text is sent WITHOUT parse_mode — the
legacy Markdown crash class (TROUBLESHOOTING.md "Can't parse entities")
cannot occur here.

`TelegramSendError` is the secrets chokepoint (Review Focus 8): httpx's own
exception messages carry the request URL, which carries the bot token, so
`send_via_http` never lets one escape — a non-2xx becomes
`telegram <status>: <API description>` and any other exception becomes its
bare type name.

NOTE on the module name: this file is `src.notify.telegram`, which shadows
the third-party `telegram` package (python-telegram-bot) if anything ever
puts `src/notify/` itself on sys.path. Absolute imports keep it unambiguous
in normal runs, and the third-party import is lazy inside `keyboard_markup`
on purpose — never make it a module-level import.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

TELEGRAM_TEXT_LIMIT = 4096
CALLBACK_LIMIT_BYTES = 64
MAX_BUTTONS = 8
_TRAILER = "\n… (truncated)"

_HEADERS: dict[str, str] = {
    "job_completed": "✅ done",
    "job_failed": "❌ failed",
    "task_approval_request": "✋ task needs your approval",
    "task_question": "❓ task needs your input — reply to this message",
    "task_choices": "\U0001f500 task — pick one",
    "task_plan": "\U0001f4cb plan (executing now)",
    "task_plan_approval": "\U0001f4cb plan — needs your approval",
    "task_completed": "✅ task completed and verified",
    "task_progress": "\U0001f504 progress",
    "task_failed": "❌ task failed",
    "task_review_flagged": "⚠️ post-review flagged",
    "ops_alert": "\U0001f6a8 ops",
    "credential_canary": "\U0001f511 credential canary",
    "quota_paused": "⏸ queue paused",
    "quota_resumed": "▶️ queue resumed",
    "schedule_deferred": "⏭ schedule deferred",
    "settings_override": "\U0001f6e1 settings override refused",
    "provider_enforcement": "\U0001f6ab provider refused",
}


class TelegramSendError(Exception):
    """A delivery failure whose text is safe to persist and print: never the
    request URL, never the token."""


@dataclass(frozen=True)
class TelegramMessage:
    chat_id: int
    text: str
    buttons: tuple[tuple[tuple[str, str], ...], ...] = ()
    reply_to_message_id: int | None = None


def validate_callback(data: str) -> str:
    if len(data.encode("utf-8")) > CALLBACK_LIMIT_BYTES:
        raise ValueError(f"callback_data exceeds {CALLBACK_LIMIT_BYTES} bytes: {data[:32]!r}…")
    return data


def fit_text(head: str, body: str, *, footer: str = "", limit: int = TELEGRAM_TEXT_LIMIT) -> str:
    """head + newline + body + footer, body clipped so the whole fits `limit`."""
    frame = len(head) + 1 + len(footer)
    room = limit - frame
    body = body or ""
    if len(body) <= room:
        return f"{head}\n{body}{footer}"
    clipped = body[: max(room - len(_TRAILER), 0)] + _TRAILER
    return f"{head}\n{clipped}{footer}"


def build_buttons(actions: dict[str, Any] | None) -> tuple[tuple[tuple[str, str], ...], ...]:
    rows_in = (actions or {}).get("buttons") or []
    rows_out: list[tuple[tuple[str, str], ...]] = []
    total = 0
    for row in rows_in:
        cells: list[tuple[str, str]] = []
        for label, cb in row:
            if total >= MAX_BUTTONS:
                break
            cells.append((str(label)[:40], validate_callback(str(cb))))
            total += 1
        if cells:
            rows_out.append(tuple(cells))
        if total >= MAX_BUTTONS:
            break
    return tuple(rows_out)


def _chat_id(target: str | None, owner_chat_id: int) -> int:
    try:
        return int(target) if target else owner_chat_id
    except (TypeError, ValueError):
        return owner_chat_id


def render_telegram(notice_like: Any, *, owner_chat_id: int) -> TelegramMessage:
    """Pure. Accepts a Notice or a Notification row (same attribute names)."""
    kind = getattr(notice_like, "notice_kind", "") or ""
    actions = getattr(notice_like, "actions", None) or {}
    head = _HEADERS.get(kind, kind or "notice")
    footer = ""
    if kind.startswith("job_") and actions.get("job8"):
        footer = f"\n/status {actions['job8']}"
    # Task cards name the task (the legacy renderer wrote `Task <prefix> …`;
    # a card with no thread to reply in is otherwise unattributable).
    prefix = actions.get("prefix") if kind.startswith("task_") else None
    if prefix:
        head = (head.replace("task", f"task {prefix}", 1) if " task " in f" {head} "
                else f"{head} · task {prefix}")
    thread = getattr(notice_like, "thread", None)
    reply_to = int(thread) if isinstance(thread, str) and thread.isdigit() else None
    return TelegramMessage(
        chat_id=_chat_id(getattr(notice_like, "target", None), owner_chat_id),
        text=fit_text(head, getattr(notice_like, "body", "") or "", footer=footer),
        buttons=build_buttons(actions),
        reply_to_message_id=reply_to,
    )


def keyboard_markup(buttons: tuple[tuple[tuple[str, str], ...], ...]):
    """python-telegram-bot markup or None. Lazy import: see the module note."""
    if not buttons:
        return None
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(label, callback_data=cb) for label, cb in row] for row in buttons]
    )


async def send_via_bot(bot: Any, msg: TelegramMessage) -> int:
    """Deliver through a running python-telegram-bot Bot; returns message_id.
    A reply target that no longer exists is retried once without reply_to."""
    kwargs: dict[str, Any] = dict(chat_id=msg.chat_id, text=msg.text,
                                  reply_markup=keyboard_markup(msg.buttons))
    if msg.reply_to_message_id:
        kwargs["reply_to_message_id"] = msg.reply_to_message_id
    try:
        sent = await bot.send_message(**kwargs)
    except Exception as exc:  # noqa: BLE001
        if msg.reply_to_message_id and "repl" in str(exc).lower():
            kwargs.pop("reply_to_message_id", None)
            sent = await bot.send_message(**kwargs)
        else:
            raise
    return int(sent.message_id)


async def send_via_http(token: str, msg: TelegramMessage, *, transport: Any = None) -> int:
    """Deliver straight to api.telegram.org (CLI / launchd alerters, where the
    bot process may be the thing that is down). Returns message_id.

    Raises only `TelegramSendError`: a non-2xx carries the API's
    `description` (else the reason phrase); anything else (connect error,
    timeout, a malformed body) carries its bare type name. `raise_for_status`
    is never called — its message would embed the token URL. `transport` is
    a test seam (`httpx.MockTransport`)."""
    import json

    import httpx

    payload: dict[str, Any] = {"chat_id": msg.chat_id, "text": msg.text}
    if msg.reply_to_message_id:
        payload["reply_to_message_id"] = msg.reply_to_message_id
    if msg.buttons:
        payload["reply_markup"] = json.dumps({"inline_keyboard": [
            [{"text": label, "callback_data": cb} for label, cb in row] for row in msg.buttons]})
    try:
        async with httpx.AsyncClient(timeout=10, transport=transport) as client:
            r = await client.post(f"https://api.telegram.org/bot{token}/sendMessage", data=payload)
            if r.status_code // 100 != 2:
                try:
                    description = str(r.json().get("description") or "")
                except Exception:  # noqa: BLE001 — non-JSON error page
                    description = ""
                raise TelegramSendError(
                    f"telegram {r.status_code}: {(description or r.reason_phrase)[:200]}")
            return int(r.json()["result"]["message_id"])
    except TelegramSendError:
        raise
    except Exception as exc:  # noqa: BLE001 — never let an httpx message (URL + token) out
        raise TelegramSendError(type(exc).__name__) from None
