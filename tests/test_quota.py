"""
Quota detection + pause/resume — the single largest blast radius in the runner
(a false positive pauses ALL jobs; a false negative hammers a spent quota and
crash-loops every job), and it had ZERO coverage before 2026-07-28.

Detection is pure (no infra). Pause/resume round-trips against fakeredis.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from src.runner import quota


# ── detect_quota_error (pure, heuristic fallback) ───────────────────────────


class TestDetectQuotaError:
    def test_none_for_non_quota_text(self):
        assert quota.detect_quota_error("some unrelated error") is None
        assert quota.detect_quota_error("") is None

    def test_true_for_quota_markers(self):
        for text in ("rate limit exceeded", "rate_limit hit", "quota exceeded",
                     "you hit the 5-hour limit", "weekly limit reached",
                     "usage limit"):
            assert quota.detect_quota_error(text) is not None, text

    def test_extracts_iso_reset_time(self):
        got = quota.detect_quota_error("rate limit; resets at 2026-08-01T12:00:00Z")
        assert isinstance(got, datetime)
        assert got.year == 2026 and got.month == 8 and got.day == 1

    def test_extracts_retry_after_seconds(self):
        got = quota.detect_quota_error("rate limit — retry after 3600")
        assert isinstance(got, datetime)
        # ~1 hour out
        assert got > datetime.now(timezone.utc) + timedelta(minutes=50)

    def test_true_when_hit_but_no_reset(self):
        # Marker present, no parseable time → True (use default pause window).
        assert quota.detect_quota_error("usage limit reached") is True


# ── detect_from_rate_limit (typed, preferred path) ──────────────────────────


@dataclass
class _Info:
    status: str
    resets_at: float | None = None
    rate_limit_type: str | None = None


class TestDetectFromRateLimit:
    def test_none_when_not_rejected(self):
        assert quota.detect_from_rate_limit(_Info(status="allowed")) is None
        assert quota.detect_from_rate_limit(_Info(status="allowed_warning")) is None

    def test_datetime_when_rejected_with_reset(self):
        ts = (datetime.now(timezone.utc) + timedelta(hours=2)).timestamp()
        got = quota.detect_from_rate_limit(_Info(status="rejected", resets_at=ts))
        assert isinstance(got, datetime)
        assert abs((got - datetime.fromtimestamp(ts, tz=timezone.utc)).total_seconds()) < 1

    def test_true_when_rejected_without_reset(self):
        assert quota.detect_from_rate_limit(_Info(status="rejected")) is True

    def test_true_when_reset_unparseable(self):
        assert quota.detect_from_rate_limit(_Info(status="rejected", resets_at="nonsense")) is True


# ── pause / resume round-trip (fakeredis) ───────────────────────────────────


class TestPauseResume:
    async def test_not_paused_initially(self, fake_redis):
        paused, reset_at, reason = await quota.is_paused()
        assert paused is False and reset_at is None

    async def test_pause_then_reflected(self, fake_redis):
        reset = datetime.now(timezone.utc) + timedelta(minutes=30)
        await quota.pause_queue(reset, "hit the 5-hour limit")
        paused, reset_at, reason = await quota.is_paused()
        assert paused is True
        assert reason == "hit the 5-hour limit"
        assert reset_at is not None

    async def test_clear_resumes(self, fake_redis):
        await quota.pause_queue(datetime.now(timezone.utc) + timedelta(minutes=30), "x")
        await quota.clear()
        paused, _, _ = await quota.is_paused()
        assert paused is False

    async def test_expired_pause_auto_resumes(self, fake_redis):
        # reset already in the past → is_paused must auto-clear and report resumed.
        await quota.pause_queue(datetime.now(timezone.utc) - timedelta(seconds=1), "expired")
        paused, reset_at, reason = await quota.is_paused()
        assert paused is False

    async def test_pause_defaults_window_when_reset_none(self, fake_redis):
        reset = await quota.pause_queue(None, "unknown reset")
        # Falls back to settings.quota_pause_minutes ahead of now.
        assert reset > datetime.now(timezone.utc) + timedelta(minutes=1)
        paused, _, _ = await quota.is_paused()
        assert paused is True
