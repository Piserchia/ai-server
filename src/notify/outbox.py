"""
Notification outbox (Observability Phase 1, A4; spec §3 cards/eligibility,
§9 switch + rollback; design of record P0 plan Task 5).

Rows in `notifications` are the durable record of every owner-facing notice.
Producers (runner, bot, `python -m src.notify send`) only INSERT + nudge
`notify:outbox`; the bot's outbox listener (A6) and the CLI's `drain` claim,
deliver and stamp status/attempts/external_ref. A bot restart therefore
loses nothing: whatever is `pending` is picked up by the 30 s poll.

D-P1-10 — the switch is the bot's: NOTHING here reads the kill switch.
`enqueue_notice` always inserts the pending row; which renderer delivers it
is decided in gateway/telegram_bot.py (and mirrored by `__main__ drain`).

Pure builders (`build_*_notice`, `should_notify_job`, `lane_label`, retry
math) carry the policy and are tested without I/O; the async functions are
thin SQLAlchemy wrappers driven against a recording session in tests.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from sqlalchemy import select, update as sql_update

from src import audit_log
from src.db import CHANNEL_NOTIFY_OUTBOX, async_session, redis
from src.gateway.jobs import ORIGIN_CHANNELS
from src.models import Notification

logger = structlog.get_logger(__name__)

# The nine legacy `tasks:notify` types (telegram_bot._task_notifier), in order.
TASK_NOTIFY_TYPES: tuple[str, ...] = (
    "approval_request", "question", "choices", "plan", "plan_approval",
    "completed", "progress", "failed", "review_flagged",
)
JOB_NOTICE_KINDS: frozenset[str] = frozenset({"job_completed", "job_failed"})
TASK_NOTICE_KINDS: frozenset[str] = frozenset(f"task_{t}" for t in TASK_NOTIFY_TYPES)
# Out-of-band kinds: no legacy renderer covers these, so the bot delivers
# them in BOTH switch positions (A6 `legacy_mode`; `__main__ drain` mirrors).
OPS_NOTICE_KINDS: frozenset[str] = frozenset({
    "ops_alert",             # launchd alerters (healthcheck-all, schedule-monitor) — A7
    "quota_paused", "quota_resumed",   # the bot's quota notifier — A6
    "schedule_deferred",     # provisioning pre-check — D1
    "settings_override",     # project-scope settings override observed — E1
    "credential_canary",     # daily canary — E10
    "provider_enforcement",  # the fail-closed registry refused a lane — reserved
})
NOTICE_KINDS: frozenset[str] = JOB_NOTICE_KINDS | TASK_NOTICE_KINDS | OPS_NOTICE_KINDS
SEVERITIES: tuple[str, ...] = ("info", "warn", "critical")
# `sending` = claimed by one drainer (bot listener or `python -m src.notify
# drain`); next_attempt_at holds the lease expiry while a row is `sending`.
STATUSES: tuple[str, ...] = ("pending", "sending", "sent", "failed", "skipped")
MAX_ATTEMPTS = 5
SENDING_LEASE_SECONDS = 300
# Card eligibility (spec §3 "Card eligibility"). A completion DMs only when a
# HUMAN launched the job: Telegram, the web dashboard (spec §1/§2.2 count it
# as a human launch) or the CLI (spec §4.2; no Phase-1 producer emits it yet).
# `pwa` is not an origin channel until Phase 2. Machine launchers (scheduler,
# dispatch-mcp / event-trigger / escalation = "system") DM on failure only;
# every schedule row behaves as `notify=failures` in Phase 1.
COMPLETION_DM_CHANNELS: tuple[str, ...] = ("telegram", "web", "cli")
assert set(COMPLETION_DM_CHANNELS) <= set(ORIGIN_CHANNELS)


@dataclass(frozen=True)
class Notice:
    notice_kind: str
    body: str
    severity: str = "info"
    subject_type: str | None = None      # job | task | schedule | ops
    subject_id: str | None = None
    actions: dict[str, Any] | None = None  # {"buttons": [[[label, callback], ...], ...], ...}
    channel: str = "telegram"
    target: str | None = None            # chat id; None → owner
    thread: str | None = None            # Telegram message id to reply under


# ── Pure policy ─────────────────────────────────────────────────────────────


def notice_kind_for_task_type(notify_type: str) -> str:
    if notify_type not in TASK_NOTIFY_TYPES:
        raise ValueError(f"unknown tasks:notify type {notify_type!r}")
    return f"task_{notify_type}"


def should_notify_job(*, status: str, kind: str, task_id: Any,
                      origin_channel: str | None) -> bool:
    """Card eligibility, spec §3 — the only place that decides who gets a card.

    - internal kinds (`_writeback`, `_evaluate`, `_learning_apply`): never;
    - `failed`: always eligible (a scheduled failure was silent before), so
      the FailedCard is what a `notify=failures` row gets;
    - `completed`: only when no task card already covers it AND the launch
      channel is in COMPLETION_DM_CHANNELS — scheduler / dispatch /
      self-diagnose completions would otherwise be 10-20 DMs a day;
    - children (dispatch-MCP, escalation, self-diagnose) INHERIT the parent's
      eligibility: the caller (A5 `effective_origin_channel`) passes the
      parent job's origin_channel, so this function never sees the child's
      own "system".
    """
    if (kind or "").startswith("_"):
        return False
    if status == "failed":
        return True
    if status == "completed":
        return task_id is None and (origin_channel or "") in COMPLETION_DM_CHANNELS
    return False


def lane_label(provider: str | None, model: str | None,
               terminal_reason: str | None = None) -> str:
    """`provider/model` for the surfaces — THE definition (A6 makes
    `telegram_bot._lane_label` a thin alias). Pure. A pre-007 row (model, no
    provider) shows its model alone — never guessed to be Anthropic; a queued
    row (neither) shows nothing. A terminal reason other than `ok` is
    appended so a failed DM says WHY the lane ended."""
    if provider and model:
        lane = f"{provider}/{model}"
    else:
        lane = model or provider or ""
    if lane and terminal_reason and terminal_reason != "ok":
        lane += f" · {terminal_reason}"
    return lane


def _fmt_duration(seconds: float | None) -> str:
    if not seconds or seconds < 0:
        return ""
    m, s = divmod(int(seconds), 60)
    return f" · {m}m{s:02d}s" if m else f" · {s}s"


def build_job_notice(
    *, job_id: Any, status: str, kind: str, resolved_skill: str | None,
    summary: str | None, error_message: str | None, terminal_reason: str | None,
    origin_channel: str | None, origin_ref: str | None, origin_thread: str | None,
    created_by: str, task_id: Any = None, model_served: str | None = None,
    resolved_provider: str | None = None, resolved_model: str | None = None,
    num_turns: int | None = None, duration_seconds: float | None = None,
) -> Notice | None:
    """Pure. The DoneCard / FailedCard body for a job terminal, or None.

    The header is plain text (the renderer sends without parse_mode):
    `<job8> · <skill> · <duration> · <lane_label> · <turns>` and, on a
    failure, `· via <source>` where source is the schedule name when known,
    else the channel, else created_by — never "via None"."""
    if not should_notify_job(status=status, kind=kind, task_id=task_id,
                             origin_channel=origin_channel):
        return None
    job8 = str(job_id)[:8]
    label = resolved_skill or kind
    source = ((origin_ref if origin_channel == "scheduler" and origin_ref else None)
              or origin_channel or created_by)
    header = f"{job8} · {label}{_fmt_duration(duration_seconds)}"
    if status == "completed":
        lane = lane_label(resolved_provider, resolved_model or model_served, terminal_reason)
        if lane:
            header += f" · {lane}"
        if num_turns:
            header += f" · {num_turns} turns"
        body = f"{header}\n\n{(summary or '').strip() or '(no summary)'}"
        buttons: list[list[list[str]]] = []
        severity = "info"
    else:
        reason = terminal_reason or "error"
        # lane_label appends the reason itself when it has a lane to append
        # it to; a queued/pre-dispatch failure (no lane) still names it.
        lane = lane_label(resolved_provider, resolved_model or model_served, reason) or reason
        header += f" · {lane}"
        if num_turns:
            header += f" · {num_turns} turns"
        header += f" · via {source}"
        body = f"{header}\n\n{(error_message or 'unknown error').strip()}"
        buttons = [[["Details", f"jd:{job8}"]]]   # Phase-1 callback grammar (A6 answers it)
        severity = "warn"
    target = origin_ref if (origin_channel == "telegram" and origin_ref) else None
    return Notice(
        notice_kind=f"job_{status}", body=body, severity=severity,
        subject_type="job", subject_id=str(job_id),
        actions={"buttons": buttons, "job8": job8},
        target=target, thread=(origin_thread if target else None),
    )


def build_task_notice(
    *, task_id: Any, notify_type: str, text: str, question: str | None = None,
    choices: list[str] | None = None, target: str | None = None, thread: str | None = None,
) -> Notice:
    """Pure. One card per legacy tasks:notify type; callback strings are the
    ones `_handle_button` already parses. No rating rows (spec §4.1 — the
    legacy `_task_notifier` still emits `rate:` buttons; they leave with it)."""
    kind = notice_kind_for_task_type(notify_type)
    prefix = str(task_id)[:8]
    buttons: list[list[list[str]]] = []
    if notify_type == "approval_request":
        buttons = [[["Approve", f"approve:{prefix}"],
                    ["Send Feedback", f"feedback:{prefix}"],
                    ["View Details", f"details:{prefix}"]]]
    elif notify_type == "choices":
        buttons = [[[str(c)[:40], f"choice:{prefix}:{i}"]]
                   for i, c in enumerate((choices or [])[:8])]
    elif notify_type == "plan":
        buttons = [[["Cancel plan", f"cancel:{prefix}"]]]
    elif notify_type == "plan_approval":
        buttons = [[["Approve plan", f"approve_plan:{prefix}"], ["Cancel", f"cancel:{prefix}"]]]
    elif notify_type == "completed":
        buttons = [[["Reopen", f"reopen:{prefix}"], ["View Details", f"details:{prefix}"]]]
    body = (question or "Pick one:") if notify_type == "choices" else (text or "")
    severity = "warn" if notify_type in ("failed", "review_flagged") else "info"
    return Notice(
        notice_kind=kind, body=body, severity=severity,
        subject_type="task", subject_id=str(task_id),
        actions={"buttons": buttons, "prefix": prefix, "choices": list(choices or [])},
        target=target, thread=thread,
    )


def build_ops_notice(*, kind: str, severity: str, text: str,
                     subject: str | None = None, target: str | None = None) -> Notice:
    """Pure. Out-of-band alerts (launchd scripts, canary, quota notifier,
    provisioning pre-check). `kind` must be an OPS kind — job/task cards have
    their own builders."""
    if kind not in OPS_NOTICE_KINDS:
        raise ValueError(f"unknown ops notice kind {kind!r}")
    if severity not in SEVERITIES:
        raise ValueError(f"unknown severity {severity!r}")
    subject_type = subject_id = None
    if subject and ":" in subject:
        subject_type, subject_id = subject.split(":", 1)
    return Notice(notice_kind=kind, body=text, severity=severity,
                  subject_type=subject_type, subject_id=subject_id,
                  actions=None, target=target)


def retry_delay_seconds(attempts: int) -> int:
    """30 s · 2^(attempts-1), capped at 600 s."""
    return min(30 * (2 ** max(attempts - 1, 0)), 600)


def transition_after_failure(attempts_so_far: int, now: datetime) -> tuple[str, int, datetime]:
    """Pure. (status, attempts, next_attempt_at) after one failed delivery."""
    attempts = attempts_so_far + 1
    status = "failed" if attempts >= MAX_ATTEMPTS else "pending"
    return status, attempts, now + timedelta(seconds=retry_delay_seconds(attempts))


# ── Async wrappers ──────────────────────────────────────────────────────────


def _row(notice: Notice, *, status: str, external_ref: str | None = None,
         last_error: str | None = None, attempts: int = 0) -> Notification:
    # The id is minted here (not by the column default at flush) so the
    # nudge and the audit line can name the row without a refresh.
    return Notification(
        id=uuid.uuid4(),
        notice_kind=notice.notice_kind, subject_type=notice.subject_type,
        subject_id=notice.subject_id, severity=notice.severity, body=notice.body,
        actions=notice.actions, channel=notice.channel, target=notice.target,
        thread=notice.thread, status=status, attempts=attempts,
        external_ref=external_ref, last_error=last_error,
        sent_at=datetime.now(timezone.utc) if status == "sent" else None,
    )


def _audit(notice_subject_type: str | None, subject_id: str | None, kind: str, **fields: Any) -> None:
    if notice_subject_type == "job" and subject_id:
        try:
            audit_log.append(subject_id, kind, **fields)
        except Exception:  # noqa: BLE001 — audit is best-effort here
            logger.debug("notice audit append failed", kind=kind)


async def record_notice(notice: Notice, *, status: str, external_ref: str | None = None,
                        last_error: str | None = None) -> uuid.UUID | None:
    """Insert a row in a given status. The CLI calls this after a DIRECT send
    and the row is the alert history; `enqueue_notice` calls it with
    `pending`. Raises on a bad kind/status or a failed insert."""
    if notice.notice_kind not in NOTICE_KINDS:
        raise ValueError(f"unknown notice kind {notice.notice_kind!r}")
    if status not in STATUSES:
        raise ValueError(f"unknown status {status!r}")
    row = _row(notice, status=status, external_ref=external_ref, last_error=last_error,
               attempts=1 if status in ("sent", "failed") else 0)
    async with async_session() as s:
        s.add(row)
        await s.commit()
    # Audit the kind that matches what was written (spec §2.7 notice_*).
    if status == "sent":
        _audit(notice.subject_type, notice.subject_id, "notice_sent",
               notice_id=str(row.id), external_ref=external_ref or "")
    elif status == "failed":
        _audit(notice.subject_type, notice.subject_id, "notice_failed",
               notice_id=str(row.id), error=(last_error or "")[:200])
    else:
        _audit(notice.subject_type, notice.subject_id, "notice_queued",
               notice_id=str(row.id), notice_kind=notice.notice_kind)
    return row.id


async def enqueue_notice(notice: Notice) -> uuid.UUID | None:
    """ALWAYS insert a pending row and nudge the bot (D-P1-10: the switch is
    read by the deliverer, never here). None only when the insert failed
    (logged) — producers never raise on a notice."""
    try:
        row_id = await record_notice(notice, status="pending")
    except Exception:  # noqa: BLE001
        logger.exception("notice insert failed", kind=notice.notice_kind)
        return None
    try:
        await redis.publish(CHANNEL_NOTIFY_OUTBOX, str(row_id))
    except Exception:  # noqa: BLE001 — the 30 s poll delivers without the nudge
        logger.warning("outbox nudge failed — poll will deliver", notice_id=str(row_id))
    return row_id


async def pending_notices(limit: int = 20, now: datetime | None = None) -> list[Notification]:
    now = now or datetime.now(timezone.utc)
    async with async_session() as s:
        result = await s.execute(
            select(Notification)
            .where(Notification.status == "pending",
                   Notification.attempts < MAX_ATTEMPTS,
                   (Notification.next_attempt_at.is_(None)) | (Notification.next_attempt_at <= now))
            .order_by(Notification.created_at)
            .limit(limit)
        )
        return list(result.scalars())


async def claim_notice(notice_id: uuid.UUID, now: datetime | None = None) -> bool:
    """Take exclusive ownership of one pending row before sending. The bot's
    listener and a manual `python -m src.notify drain` both select the same
    `pending` rows; without this claim each could send the DM. Bumps
    `attempts` and parks the lease expiry in `next_attempt_at`. False when
    someone else already has it (rowcount 0) — the caller skips the row."""
    now = now or datetime.now(timezone.utc)
    async with async_session() as s:
        res = await s.execute(
            sql_update(Notification)
            .where(Notification.id == notice_id, Notification.status == "pending")
            .values(status="sending", attempts=Notification.attempts + 1,
                    next_attempt_at=now + timedelta(seconds=SENDING_LEASE_SECONDS))
        )
        await s.commit()
    return bool(res.rowcount)


async def release_stuck_sending(now: datetime | None = None) -> int:
    """Rows a crashed drainer left `sending` past their lease go back to
    `pending` (the bot listener calls this once at startup). Returns count."""
    now = now or datetime.now(timezone.utc)
    async with async_session() as s:
        res = await s.execute(
            sql_update(Notification)
            .where(Notification.status == "sending", Notification.next_attempt_at <= now)
            .values(status="pending", next_attempt_at=None)
        )
        await s.commit()
    return int(res.rowcount or 0)


async def mark_sent(notice_id: uuid.UUID, external_ref: str, *,
                    subject_type: str | None = None, subject_id: str | None = None) -> None:
    """`attempts` is NOT bumped here — claim_notice already counted this try."""
    async with async_session() as s:
        await s.execute(
            sql_update(Notification).where(Notification.id == notice_id).values(
                status="sent", external_ref=external_ref[:64],
                sent_at=datetime.now(timezone.utc), next_attempt_at=None, last_error=None)
        )
        await s.commit()
    _audit(subject_type, subject_id, "notice_sent", notice_id=str(notice_id), external_ref=external_ref)


async def mark_failed(notice_id: uuid.UUID, error: str, *, attempts_so_far: int,
                      subject_type: str | None = None, subject_id: str | None = None) -> str:
    """Returns the new status (`pending` with a backoff, or `failed` at
    MAX_ATTEMPTS). `attempts_so_far` is the value read BEFORE the claim.
    `error` must already be token-free (telegram.TelegramSendError is)."""
    status, attempts, next_at = transition_after_failure(attempts_so_far, datetime.now(timezone.utc))
    async with async_session() as s:
        await s.execute(
            sql_update(Notification).where(Notification.id == notice_id).values(
                status=status, attempts=attempts, last_error=error[:500], next_attempt_at=next_at)
        )
        await s.commit()
    if status == "failed":
        _audit(subject_type, subject_id, "notice_failed", notice_id=str(notice_id), error=error[:200])
    return status


async def mark_skipped(notice_id: uuid.UUID, reason: str) -> None:
    """Terminal `skipped`: a claimed row the drainer chose not to send (A6's
    `legacy_mode` for job/task kinds — the legacy listeners cover them)."""
    async with async_session() as s:
        await s.execute(
            sql_update(Notification).where(Notification.id == notice_id).values(
                status="skipped", last_error=reason[:500], next_attempt_at=None)
        )
        await s.commit()
