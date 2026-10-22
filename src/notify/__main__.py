"""
CLI for out-of-band alerters (launchd scripts, credential canary) and ops.

  python -m src.notify send --kind ops_alert --severity warn --text "runner down" [--subject job:<uuid>] [--target <chat>]
  python -m src.notify drain [--limit 20]

`send` tries a DIRECT Telegram HTTP send first (the bot may be the thing
that is down), then records the row as the alert history: `sent` with the
message id, or `failed` with the (token-free) error. Exit 0 only when the
DM was delivered; 1 otherwise, so bash callers (A7 `notify_send … ||
curl-fallback`) take their legacy curl path. A `failed` row is history, not
a retry queue — the fallback is the retry.

`drain` is the manual counterpart of the bot's outbox listener: it releases
rows stuck in `sending` past their lease, claims before sending (so it is
safe beside the running bot) and mirrors the bot's `legacy_mode` — with `NOTIFY_OUTBOX=0` the legacy listeners still
send job/task DMs, so those rows are marked `skipped`, never double-sent.

Secrets: everything this module records or prints passes through
`_redact`, which replaces the bot token with `[REDACTED]` — a second belt
behind `TelegramSendError`.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from src.config import settings
from src.notify.outbox import (
    OPS_NOTICE_KINDS,
    build_ops_notice,
    claim_notice,
    mark_failed,
    mark_sent,
    mark_skipped,
    pending_notices,
    record_notice,
    release_stuck_sending,
)
from src.notify.telegram import TelegramSendError, render_telegram, send_via_http


def _owner_chat_id() -> int | None:
    ids = settings.allowed_chat_ids
    return ids[0] if ids else None


def _redact(text: str) -> str:
    token = settings.telegram_bot_token
    return text.replace(token, "[REDACTED]") if token else text


def _safe_error(exc: BaseException) -> str:
    """TelegramSendError text is already token-free; anything else is reduced
    to its type name. Redacted again regardless."""
    text = str(exc) if isinstance(exc, TelegramSendError) else type(exc).__name__
    return _redact(text)[:300]


async def _send(args: argparse.Namespace) -> int:
    notice = build_ops_notice(kind=args.kind, severity=args.severity, text=args.text,
                              subject=args.subject, target=args.target)
    owner = _owner_chat_id()
    ref: str | None = None
    err: str | None = None
    if owner is not None and settings.telegram_bot_token:
        try:
            ref = str(await send_via_http(settings.telegram_bot_token,
                                          render_telegram(notice, owner_chat_id=owner)))
        except Exception as exc:  # noqa: BLE001
            err = _safe_error(exc)
    else:
        err = "telegram token / chat id not configured"
    row_id = None
    try:
        row_id = await record_notice(notice, status="sent" if ref else "failed",
                                     external_ref=ref, last_error=err)
    except Exception as exc:  # noqa: BLE001
        print(f"notify: row not recorded: {_safe_error(exc)}", file=sys.stderr)
    print(_redact(f"notice {row_id or '-'} {'sent' if ref else 'failed'}"
                  f"{(' (' + err + ')') if err else ''}"))
    return 0 if ref else 1


async def _drain(args: argparse.Namespace) -> int:
    owner = _owner_chat_id()
    if owner is None or not settings.telegram_bot_token:
        print("notify: telegram not configured", file=sys.stderr)
        return 1
    legacy_mode = not settings.notify_outbox
    # Same recovery as the bot's listener: a row another drainer left
    # `sending` past its lease is pending again before we select.
    try:
        released = await release_stuck_sending()
        if released:
            print(f"notify: released {released} stuck sending row(s)", file=sys.stderr)
    except Exception as exc:  # noqa: BLE001 — non-fatal, the drain still runs
        print(f"notify: release_stuck_sending failed: {_safe_error(exc)}", file=sys.stderr)
    rows = await pending_notices(limit=args.limit)
    sent = failed = skipped = 0
    for row in rows:
        attempts_before = row.attempts
        if not await claim_notice(row.id):
            skipped += 1          # the bot's listener took it between select and claim
            continue
        if legacy_mode and row.notice_kind not in OPS_NOTICE_KINDS:
            await mark_skipped(row.id, "legacy_mode")
            skipped += 1          # the legacy tasks:notify / jobs:done renderers cover it
            continue
        try:
            ref = await send_via_http(settings.telegram_bot_token,
                                      render_telegram(row, owner_chat_id=owner))
            await mark_sent(row.id, str(ref), subject_type=row.subject_type, subject_id=row.subject_id)
            sent += 1
        except Exception as exc:  # noqa: BLE001
            await mark_failed(row.id, _safe_error(exc), attempts_so_far=attempts_before,
                              subject_type=row.subject_type, subject_id=row.subject_id)
            failed += 1
    print(f"drained sent={sent} failed={failed} skipped={skipped} pending_before={len(rows)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m src.notify")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("send")
    s.add_argument("--kind", required=True, help=f"one of {', '.join(sorted(OPS_NOTICE_KINDS))}")
    s.add_argument("--severity", default="info", choices=("info", "warn", "critical"))
    s.add_argument("--text", required=True)
    s.add_argument("--subject", default=None, help="job:<uuid> | task:<uuid> | schedule:<name>")
    s.add_argument("--target", default=None, help="chat id; default owner")
    d = sub.add_parser("drain")
    d.add_argument("--limit", type=int, default=20)
    args = p.parse_args(argv)
    return asyncio.run(_send(args) if args.cmd == "send" else _drain(args))


if __name__ == "__main__":
    sys.exit(main())
