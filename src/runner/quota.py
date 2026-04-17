"""
Subscription-quota awareness. The runner consults this module before BLPOPing, and
writes to it when the SDK surfaces a rate_limit / quota signal from a session.

Shared state lives in Redis so restarts don't lose the pause window.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

import structlog

from src.config import settings
from src.db import redis

logger = structlog.get_logger(__name__)

# Redis keys
_KEY_PAUSED_UNTIL = "quota:paused_until"   # ISO timestamp, or missing if not paused
_KEY_LAST_REASON = "quota:last_reason"


class QuotaExhausted(Exception):
    def __init__(self, reset_at: datetime | None, reason: str = ""):
        self.reset_at = reset_at
        self.reason = reason
        super().__init__(f"Claude subscription quota exhausted; reset at {reset_at}")


def detect_quota_error(text: str) -> datetime | None | bool:
    """
    Heuristic parser for rate_limit / quota_exceeded text.

    Returns:
      - datetime: quota is exhausted and we know when it resets
      - True: quota is exhausted, reset time unknown (use default pause)
      - None: not a quota error
    """
    if not text:
        return None
    lowered = text.lower()
    hit = any(
        marker in lowered
        for marker in (
            "rate limit",
            "rate_limit",
            "quota exceeded",
            "quota_exceeded",
            "5-hour limit",
            "weekly limit",
            "session limit",
            "usage limit",
        )
    )
    if not hit:
        return None

    # Try to extract a reset timestamp: "resets at 2026-04-16T18:00" or "retry after 3600"
    iso = re.search(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?(Z|[+-]\d{2}:?\d{2})?)", text)
    if iso:
        try:
            return datetime.fromisoformat(iso.group(1).replace("Z", "+00:00"))
        except ValueError:
            pass
    retry_secs = re.search(r"retry\s+after\s+(\d+)", lowered)
    if retry_secs:
        secs = int(retry_secs.group(1))
        return datetime.now(timezone.utc) + timedelta(seconds=secs)

    return True  # quota hit, unknown reset


async def pause_queue(reset_at: datetime | None, reason: str) -> datetime:
    """Record a pause. If reset_at is None, uses settings.quota_pause_minutes."""
    if reset_at is None:
        reset_at = datetime.now(timezone.utc) + timedelta(minutes=settings.quota_pause_minutes)
    await redis.set(_KEY_PAUSED_UNTIL, reset_at.isoformat())
    await redis.set(_KEY_LAST_REASON, reason[:500])
    logger.warning("quota queue pause set", reset_at=reset_at.isoformat(), reason=reason[:120])
    return reset_at


async def is_paused() -> tuple[bool, datetime | None, str]:
    """Return (paused_now, reset_at, reason)."""
    raw = await redis.get(_KEY_PAUSED_UNTIL)
    if not raw:
        return (False, None, "")
    try:
        reset_at = datetime.fromisoformat(raw)
    except ValueError:
        await redis.delete(_KEY_PAUSED_UNTIL)
        return (False, None, "")
    if datetime.now(timezone.utc) >= reset_at:
        # Auto-resume
        await redis.delete(_KEY_PAUSED_UNTIL)
        reason = await redis.get(_KEY_LAST_REASON) or ""
        await redis.delete(_KEY_LAST_REASON)
        logger.info("quota pause expired — resuming", prior_reason=reason[:120])
        return (False, None, "")
    reason = await redis.get(_KEY_LAST_REASON) or ""
    return (True, reset_at, reason)


async def clear() -> None:
    """Manual /resume command."""
    await redis.delete(_KEY_PAUSED_UNTIL, _KEY_LAST_REASON)
