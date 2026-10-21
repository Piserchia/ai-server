"""
Subscription-quota awareness. The runner consults this module before BLPOPing, and
writes to it when the SDK surfaces a rate_limit / quota signal from a session.

Shared state lives in Redis so restarts don't lose the pause window.

Two scopes (cross-vendor writer slice T6, 2026-10-21):

- **Global** = Anthropic: `pause_queue` / `is_paused` / `clear` over the
  `quota:paused_until` pair. The job loop stops consuming the queue while it
  is set and the job that hit the limit is LPUSHed to the FRONT (INV-12).
  Unchanged by T6.
- **Per provider** (`codex`, …): `pause_provider` / `is_provider_paused` /
  `clear_provider` over `quota:provider:<p>:*`. Only that lane pauses; the
  loop keeps draining. A job whose provider is paused is HELD by
  `runner.main` (never run, `job_held` audited, requeued at the TAIL after a
  bounded delay — plan §4g). The Anthropic name delegates to the global
  functions, so one call answers for any provider, and a non-Anthropic
  rate limit can never touch the global key.

Nothing here imports the registry (module graph: config, db only); the
provider name is whatever the caller resolved.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone

import structlog

from src.config import settings
from src.db import (
    KEY_QUOTA_LAST_REASON,
    KEY_QUOTA_PAUSED_UNTIL,
    KEY_QUOTA_PROVIDER_PREFIX,
    redis,
)

logger = structlog.get_logger(__name__)

# Redis keys — the GLOBAL (Anthropic) pair; see src/db.py for the contract.
_KEY_PAUSED_UNTIL = KEY_QUOTA_PAUSED_UNTIL   # ISO timestamp, or missing if not paused
_KEY_LAST_REASON = KEY_QUOTA_LAST_REASON

#: The provider the global pair belongs to. Equal to
#: `registry.models.DEFAULT_PROVIDER` (asserted in tests; not imported so
#: this module keeps its config+db-only dependency row).
GLOBAL_PROVIDER = "anthropic"


def provider_keys(provider: str) -> tuple[str, str]:
    """`(paused_until_key, last_reason_key)` for a NON-Anthropic provider.
    Pure. Raises `ValueError` for the global provider (its keys are the
    legacy pair, not under the prefix), an empty name, or a name carrying
    the key separator / a slash (would alias another provider's keys)."""
    p = (provider or "").strip().lower()
    if not p:
        raise ValueError("provider name is empty")
    if ":" in p or "/" in p:
        raise ValueError(f"provider name {provider!r} must not contain ':' or '/'")
    if p == GLOBAL_PROVIDER:
        raise ValueError(f"{GLOBAL_PROVIDER!r} uses the global quota keys, not a provider key")
    return (f"{KEY_QUOTA_PROVIDER_PREFIX}{p}:paused_until",
            f"{KEY_QUOTA_PROVIDER_PREFIX}{p}:last_reason")


class QuotaExhausted(Exception):
    def __init__(self, reset_at: datetime | None, reason: str = ""):
        self.reset_at = reset_at
        self.reason = reason
        super().__init__(f"Claude subscription quota exhausted; reset at {reset_at}")


def detect_from_rate_limit(info) -> datetime | None | bool:
    """Typed detection from an SDK RateLimitInfo (preferred over the text
    heuristic below; the CLI emits RateLimitEvent on status transitions).

    Returns:
      - datetime: limit hit, reset time known (unix `resets_at`)
      - True: limit hit, reset time unknown (use default pause)
      - None: not exhausted (allowed / allowed_warning)
    """
    if getattr(info, "status", "") != "rejected":
        return None
    resets_at = getattr(info, "resets_at", None)
    if resets_at:
        try:
            return datetime.fromtimestamp(float(resets_at), tz=timezone.utc)
        except (TypeError, ValueError, OSError):
            pass
    return True


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


async def _write_pause(until_key: str, reason_key: str, reset_at: datetime | None,
                       reason: str) -> datetime:
    if reset_at is None:
        reset_at = datetime.now(timezone.utc) + timedelta(minutes=settings.quota_pause_minutes)
    await redis.set(until_key, reset_at.isoformat())
    await redis.set(reason_key, reason[:500])
    return reset_at


async def _read_pause(until_key: str, reason_key: str,
                      scope: str) -> tuple[bool, datetime | None, str]:
    """`(paused_now, reset_at, reason)` for one key pair; an expired or
    corrupt value is deleted and reported as not paused (auto-resume)."""
    raw = await redis.get(until_key)
    if not raw:
        return (False, None, "")
    try:
        reset_at = datetime.fromisoformat(raw)
    except ValueError:
        await redis.delete(until_key)
        return (False, None, "")
    if datetime.now(timezone.utc) >= reset_at:
        # Auto-resume
        await redis.delete(until_key)
        reason = await redis.get(reason_key) or ""
        await redis.delete(reason_key)
        logger.info("quota pause expired — resuming", scope=scope, prior_reason=reason[:120])
        return (False, None, "")
    reason = await redis.get(reason_key) or ""
    return (True, reset_at, reason)


# ── Global (Anthropic) pause — INV-12 semantics, unchanged ──────────────────


async def pause_queue(reset_at: datetime | None, reason: str) -> datetime:
    """Record a pause. If reset_at is None, uses settings.quota_pause_minutes."""
    reset_at = await _write_pause(_KEY_PAUSED_UNTIL, _KEY_LAST_REASON, reset_at, reason)
    logger.warning("quota queue pause set", reset_at=reset_at.isoformat(), reason=reason[:120])
    return reset_at


async def is_paused() -> tuple[bool, datetime | None, str]:
    """Return (paused_now, reset_at, reason)."""
    return await _read_pause(_KEY_PAUSED_UNTIL, _KEY_LAST_REASON, GLOBAL_PROVIDER)


async def clear() -> None:
    """Manual /resume command."""
    await redis.delete(_KEY_PAUSED_UNTIL, _KEY_LAST_REASON)


# ── Per-provider lane pause (T6) ────────────────────────────────────────────


async def pause_provider(provider: str, reset_at: datetime | None, reason: str) -> datetime:
    """Pause ONE provider's lane (`quota:provider:<p>:*`); the global key is
    never written. `reset_at=None` → `settings.quota_pause_minutes` ahead
    (the Codex stream carries no reset time). The Anthropic name delegates
    to `pause_queue` (global pair, INV-12)."""
    p = (provider or "").strip().lower()
    if p == GLOBAL_PROVIDER:
        return await pause_queue(reset_at, reason)
    until_key, reason_key = provider_keys(p)
    reset_at = await _write_pause(until_key, reason_key, reset_at, reason)
    logger.warning("provider lane paused", provider=p, reset_at=reset_at.isoformat(),
                   reason=reason[:120])
    return reset_at


async def is_provider_paused(provider: str) -> tuple[bool, datetime | None, str]:
    """`(paused_now, reset_at, reason)` for one provider; auto-resumes an
    expired pause. Anthropic → `is_paused()`."""
    p = (provider or "").strip().lower()
    if p == GLOBAL_PROVIDER:
        return await is_paused()
    until_key, reason_key = provider_keys(p)
    return await _read_pause(until_key, reason_key, p)


async def clear_provider(provider: str) -> None:
    """Manual `/resume <provider>`. Anthropic → `clear()`."""
    p = (provider or "").strip().lower()
    if p == GLOBAL_PROVIDER:
        await clear()
        return
    await redis.delete(*provider_keys(p))


async def paused_providers(providers: Iterable[str]) -> dict[str, tuple[datetime, str]]:
    """`{provider: (reset_at, reason)}` for those of `providers` that are
    paused right now, in the given order (the caller passes the registry's
    names; Anthropic reads the global pair)."""
    out: dict[str, tuple[datetime, str]] = {}
    for name in providers:
        paused, reset_at, reason = await is_provider_paused(name)
        if paused and reset_at is not None:
            out[name] = (reset_at, reason)
    return out
