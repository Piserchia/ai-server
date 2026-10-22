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


# ═══════════════════════════════════════════════════════════════════════════
# Per-provider quota keys (cross-vendor writer slice T6, 2026-10-21)
#
# The global key pair (`quota:paused_until` / `quota:last_reason`) keeps its
# Anthropic meaning and INV-12 front-requeue semantics; every other provider
# gets its own pair under `quota:provider:<p>:`. A Codex 429 must never touch
# the global key, and a job whose provider is paused is held: NOT marked
# running, audited `job_held`, and requeued at the TAIL (plan §4g) after a
# bounded delay — never spinning the loop, never pinning a concurrency slot.
# ═══════════════════════════════════════════════════════════════════════════

import asyncio
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src import audit_log
from src.config import settings
from src.db import KEY_QUOTA_LAST_REASON, KEY_QUOTA_PAUSED_UNTIL, KEY_QUOTA_PROVIDER_PREFIX, QUEUE_JOBS
from src.registry import models as reg
from src.registry.skills import SkillConfig, SkillFrontmatterError


def _future(minutes: int = 30) -> datetime:
    return datetime.now(timezone.utc) + timedelta(minutes=minutes)


# ── keys ─────────────────────────────────────────────────────────────────────


class TestProviderKeys:
    def test_global_constants_are_the_legacy_strings(self):
        # The Anthropic pair is a parsing/ops contract (healthcheck, runbooks).
        assert KEY_QUOTA_PAUSED_UNTIL == "quota:paused_until"
        assert KEY_QUOTA_LAST_REASON == "quota:last_reason"
        assert quota._KEY_PAUSED_UNTIL == KEY_QUOTA_PAUSED_UNTIL
        assert quota._KEY_LAST_REASON == KEY_QUOTA_LAST_REASON

    def test_provider_keys_shape(self):
        until, reason = quota.provider_keys("codex")
        assert until == f"{KEY_QUOTA_PROVIDER_PREFIX}codex:paused_until"
        assert reason == f"{KEY_QUOTA_PROVIDER_PREFIX}codex:last_reason"
        assert until != KEY_QUOTA_PAUSED_UNTIL and reason != KEY_QUOTA_LAST_REASON

    def test_provider_keys_normalise(self):
        assert quota.provider_keys(" Codex ") == quota.provider_keys("codex")

    @pytest.mark.parametrize("bad", ["", "   ", "a:b", "a/b", "anthropic"])
    def test_provider_keys_refuse_bad_names(self, bad):
        # The global provider has no key under the prefix; a name with the
        # key separator in it would alias another provider's keys.
        with pytest.raises(ValueError):
            quota.provider_keys(bad)

    def test_global_provider_name_matches_registry_default(self):
        # quota.py does not import the registry (module graph); the literal
        # must still agree with it.
        assert quota.GLOBAL_PROVIDER == reg.DEFAULT_PROVIDER == "anthropic"


# ── pause / resume per provider (fakeredis) ─────────────────────────────────


class TestProviderPauseResume:
    async def test_not_paused_initially(self, fake_redis):
        assert await quota.is_provider_paused("codex") == (False, None, "")

    async def test_pause_then_reflected(self, fake_redis):
        reset = _future(30)
        got = await quota.pause_provider("codex", reset, "429 slow_down")
        assert got == reset
        paused, reset_at, reason = await quota.is_provider_paused("codex")
        assert paused is True and reason == "429 slow_down"
        assert reset_at == reset

    async def test_provider_keys_are_independent_of_the_global_key(self, fake_redis):
        # Codex paused → Anthropic NOT paused, global key absent.
        await quota.pause_provider("codex", _future(), "codex 429")
        assert await fake_redis.get(KEY_QUOTA_PAUSED_UNTIL) is None
        assert await fake_redis.get(KEY_QUOTA_LAST_REASON) is None
        assert (await quota.is_paused())[0] is False
        # Anthropic paused → Codex unaffected, and vice versa on clear.
        await quota.pause_queue(_future(), "anthropic 5-hour")
        assert (await quota.is_provider_paused("codex"))[2] == "codex 429"
        await quota.clear()
        assert (await quota.is_provider_paused("codex"))[0] is True
        assert (await quota.is_paused())[0] is False
        await quota.clear_provider("codex")
        assert (await quota.is_provider_paused("codex"))[0] is False

    async def test_two_providers_are_independent(self, fake_redis):
        await quota.pause_provider("codex", _future(), "x")
        assert (await quota.is_provider_paused("gemini"))[0] is False
        await quota.clear_provider("gemini")          # no-op, never raises
        assert (await quota.is_provider_paused("codex"))[0] is True

    async def test_expired_pause_auto_resumes_and_clears_keys(self, fake_redis):
        await quota.pause_provider("codex", datetime.now(timezone.utc) - timedelta(seconds=1), "old")
        assert (await quota.is_provider_paused("codex"))[0] is False
        until_key, reason_key = quota.provider_keys("codex")
        assert await fake_redis.get(until_key) is None
        assert await fake_redis.get(reason_key) is None

    async def test_pause_defaults_window_when_reset_none(self, fake_redis):
        reset = await quota.pause_provider("codex", None, "no reset in the stream")
        assert reset > datetime.now(timezone.utc) + timedelta(minutes=1)
        assert (await quota.is_provider_paused("codex"))[0] is True

    async def test_corrupt_value_is_treated_as_not_paused(self, fake_redis):
        until_key, _ = quota.provider_keys("codex")
        await fake_redis.set(until_key, "not-a-timestamp")
        assert (await quota.is_provider_paused("codex"))[0] is False
        assert await fake_redis.get(until_key) is None

    async def test_reason_is_truncated(self, fake_redis):
        await quota.pause_provider("codex", _future(), "x" * 2000)
        assert len((await quota.is_provider_paused("codex"))[2]) == 500

    async def test_anthropic_delegates_to_the_global_functions(self, fake_redis):
        # One call answers for any provider: the Anthropic name reads and
        # writes the GLOBAL pair (INV-12 semantics unchanged), never a
        # `quota:provider:anthropic:*` key.
        await quota.pause_provider("anthropic", _future(), "global via provider api")
        assert await fake_redis.get(KEY_QUOTA_PAUSED_UNTIL) is not None
        assert (await quota.is_paused())[2] == "global via provider api"
        assert (await quota.is_provider_paused("anthropic"))[2] == "global via provider api"
        assert not [k async for k in fake_redis.scan_iter(f"{KEY_QUOTA_PROVIDER_PREFIX}*")]
        await quota.clear_provider("anthropic")
        assert (await quota.is_paused())[0] is False

    async def test_paused_providers_lists_only_paused_ones(self, fake_redis):
        await quota.pause_provider("codex", _future(), "429")
        got = await quota.paused_providers(["anthropic", "codex", "gemini"])
        assert list(got) == ["codex"]
        assert got["codex"][1] == "429" and got["codex"][0] > datetime.now(timezone.utc)
        await quota.pause_queue(_future(), "anthropic too")
        got = await quota.paused_providers(["anthropic", "codex"])
        assert list(got) == ["anthropic", "codex"]


# ── main: cheap pre-resolution (pure) ───────────────────────────────────────


def _cfg(model: str = "") -> SkillConfig:
    return SkillConfig(name="demo", body="Do the thing.", model=model)


class TestPreresolveProvider:
    def test_payload_model_wins(self):
        from src.runner import main as runner_main
        got = runner_main.preresolve_provider(
            "demo", "x", {"model": "codex/gpt-6-luna"},
            load=lambda name: _cfg("claude-sonnet-4-6"), route=lambda d: None)
        assert got == "codex"

    def test_payload_resolves_through_the_registry(self):
        # Aliases and case/whitespace go through `registry.resolve`, exactly
        # as the session will resolve them — never a string compare.
        from src.runner import main as runner_main
        alias = next(k for k in reg.alias_table() if "/" not in k)      # an Anthropic alias
        assert runner_main.preresolve_provider("demo", "x", {"model": alias},
                                               load=lambda n: None, route=lambda d: None) == "anthropic"
        assert runner_main.preresolve_provider("demo", "x", {"model": " Codex/GPT-6-Luna "},
                                               load=lambda n: None, route=lambda d: None) == "codex"

    def test_explicit_kind_uses_the_skill_pin(self):
        from src.runner import main as runner_main
        seen = []

        def load(name):
            seen.append(name)
            return _cfg("codex/gpt-6-luna")

        assert runner_main.preresolve_provider("research_report", "x", {}, load=load,
                                               route=lambda d: None) == "codex"
        assert seen == ["research-report"]            # same mapping as _resolve_skill

    def test_internal_kind_keeps_leading_underscore(self):
        from src.runner import main as runner_main
        seen = []
        runner_main.preresolve_provider("_writeback", "x", {},
                                        load=lambda n: seen.append(n), route=lambda d: None)
        assert seen == ["_writeback"]

    def test_task_kind_uses_the_rule_router_only(self):
        from src.runner import main as runner_main
        got = runner_main.preresolve_provider(
            "task", "fix the flaky test", {},
            load=lambda name: _cfg("codex/gpt-6-luna") if name == "pinned" else None,
            route=lambda d: "pinned")
        assert got == "codex"
        # No rule match → settings.default_model (Anthropic); the LLM router
        # is NOT consulted here (it is not cheap) — the session resolves for real.
        got = runner_main.preresolve_provider("task", "whatever", {},
                                              load=lambda name: None, route=lambda d: None)
        assert got == "anthropic"

    def test_default_model_is_anthropic(self):
        from src.runner import main as runner_main
        assert runner_main.preresolve_provider("demo", "x", {}, load=lambda n: None,
                                               route=lambda d: None) == "anthropic"
        assert runner_main.preresolve_provider("demo", "x", None, load=lambda n: None,
                                               route=lambda d: None) == "anthropic"

    def test_unknown_model_or_corrupt_skill_is_none(self):
        # Never a refusal here — the session raises the real ProviderRefused /
        # SkillResolutionError with its audit; None just means "cannot hold".
        from src.runner import main as runner_main
        assert runner_main.preresolve_provider("demo", "x", {"model": "nope/zzz"},
                                               load=lambda n: None, route=lambda d: None) is None

        def corrupt(name):
            raise SkillFrontmatterError("bad yaml")

        assert runner_main.preresolve_provider("demo", "x", {}, load=corrupt,
                                               route=lambda d: None) is None

    def test_disabled_provider_still_preresolves(self, monkeypatch):
        # Pre-resolution is about WHICH lane, not whether it may run (the
        # session's resolve_enabled refuses a disabled provider properly).
        from src.runner import main as runner_main
        monkeypatch.setattr(settings, "router_providers_enabled", "anthropic")
        assert runner_main.preresolve_provider("demo", "x", {"model": "codex/gpt-6-luna"},
                                               load=lambda n: None, route=lambda d: None) == "codex"


class TestHoldDelay:
    def test_bounded_by_recheck_and_remaining_window(self):
        from src.runner import main as runner_main
        now = datetime.now(timezone.utc)
        assert runner_main.hold_delay(now + timedelta(hours=1), now) == runner_main.HOLD_RECHECK_SECONDS
        assert runner_main.hold_delay(now + timedelta(seconds=5), now) == 5.0
        assert runner_main.hold_delay(now - timedelta(seconds=5), now) == 0.0
        assert runner_main.hold_delay(None, now) == runner_main.HOLD_RECHECK_SECONDS
        assert 0 < runner_main.HOLD_RECHECK_SECONDS <= 60


# ── main: held → tail requeue with audit; Codex 429 → lane pause + front ───


class _FakeDB:
    """`async_session()` / `session_scope()` stand-in: `get` returns the job,
    `execute` records UPDATE values."""

    def __init__(self, job):
        self.job = job
        self.executed: list = []
        self.commits = 0

    def __call__(self):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, model, job_id):
        return self.job

    async def execute(self, stmt):
        self.executed.append(stmt)

    async def commit(self):
        self.commits += 1


def _job(**kw) -> SimpleNamespace:
    base = dict(id=uuid.uuid4(), kind="demo", description="fix the flaky test",
                payload={"model": "codex/gpt-6-luna"}, task_id=None, status="queued",
                started_at=None, resolved_skill=None, resolved_provider=None,
                error_message=None, created_by="telegram:1")
    base.update(kw)
    return SimpleNamespace(**base)


def _kinds(job_id) -> list[str]:
    return [e["kind"] for e in audit_log.read(str(job_id))]


def _event(job_id, kind) -> dict:
    found = [e for e in audit_log.read(str(job_id)) if e["kind"] == kind]
    assert found, f"no {kind} event"
    return found[-1]


def _update_values(stmt) -> dict:
    # SQLAlchemy Update → the VALUES mapping it carries (bind params unwrapped).
    return {c.name: getattr(v, "value", v) for c, v in stmt._values.items()}


@pytest.fixture
def main_harness(tmp_path, monkeypatch, fake_redis):
    from src.runner import main as runner_main
    from src.runner import plans as runner_plans
    monkeypatch.setattr(settings, "server_root", tmp_path / "root")
    (tmp_path / "root").mkdir()
    monkeypatch.setattr(runner_main, "redis", fake_redis, raising=False)
    monkeypatch.setattr(runner_main, "HOLD_RECHECK_SECONDS", 0.0)
    runner_main._held_audited.clear()

    def build(*, session_exc: BaseException | None = None, job=None):
        job = job or _job()
        h = SimpleNamespace(job=job, db=_FakeDB(job), finished=[], escalated=[],
                            notified=[], sessions=[])

        async def fake_run_session(j):
            h.sessions.append(j)
            if session_exc is not None:
                raise session_exc
            return {"summary": "ok", "provider": "codex", "terminal_reason": "ok"}

        async def fake_preflight(j, log):
            return None

        async def fake_finish(job_id, status, **kw):
            h.finished.append({"job_id": job_id, "status": status, **kw})

        async def fake_refetch(job_id, fallback, log):
            return fallback

        async def fake_escalate(j):
            h.escalated.append(j)

        async def fake_notify(task_id, kind, **fields):
            h.notified.append((task_id, kind, fields))

        async def fake_promote(j):
            return 0

        monkeypatch.setattr(runner_main, "async_session", h.db)
        monkeypatch.setattr(runner_main, "session_scope", h.db)
        monkeypatch.setattr(runner_main, "_preflight_check", fake_preflight)
        monkeypatch.setattr(runner_main.session_mod, "run_session", fake_run_session)
        monkeypatch.setattr(runner_main, "_finish_job", fake_finish)
        monkeypatch.setattr(runner_main, "_refetch_job", fake_refetch)
        monkeypatch.setattr(runner_main, "_maybe_escalate", fake_escalate)
        monkeypatch.setattr(runner_main, "_notify_task", fake_notify)
        monkeypatch.setattr(runner_main, "_maybe_review", AsyncMock())
        monkeypatch.setattr(runner_main, "_verify_writeback", AsyncMock())
        monkeypatch.setattr(runner_main, "maybe_extract_learning", AsyncMock())
        monkeypatch.setattr(runner_main, "_JOB_FETCH_DELAYS", (0.0,))
        # Deferred-dependent promotion runs for EVERY completing job and
        # plans.py binds its own `async_session`; without this stub it opens
        # a real asyncpg connection (the "coroutine 'Connection._cancel' was
        # never awaited" warning at GC time).
        monkeypatch.setattr(runner_plans, "promote_deferred_for", fake_promote)
        # The cheap pre-resolution must not touch the (prod-pointing) skills
        # dir: `preresolve_provider` resolves `load` at call time, so this
        # module-level patch is what it sees; `settings.server_root` above
        # is the second line of defence.
        monkeypatch.setattr(runner_main, "load_skill", lambda name: None)
        return h

    return build


async def _drain_held(runner_main):
    tasks = list(runner_main._held_requeues)
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


class TestHeldJob:
    async def test_paused_provider_holds_the_job_to_the_tail(self, main_harness, fake_redis):
        from src.models import JobStatus
        from src.runner import main as runner_main
        h = main_harness()
        until = await quota.pause_provider("codex", _future(45), "429 slow_down")
        await fake_redis.rpush(QUEUE_JOBS, "other-job")       # someone else is waiting

        await runner_main._process_job(h.job.id)
        await _drain_held(runner_main)

        assert h.sessions == []                                # no session, no process
        assert h.finished == [] and h.escalated == []
        assert h.job.status == JobStatus.queued.value          # never flipped to running
        assert h.db.commits == 0 and h.db.executed == []       # no DB write at all
        assert await fake_redis.lrange(QUEUE_JOBS, 0, -1) == ["other-job", str(h.job.id)]  # TAIL
        held = _event(h.job.id, "job_held")
        assert held["provider"] == "codex" and held["reason"] == "429 slow_down"
        assert held["until"] == until.isoformat()
        assert "job_started" not in _kinds(h.job.id)
        # The global pause is untouched by a lane hold.
        assert (await quota.is_paused())[0] is False

    async def test_hold_audit_is_deduped_per_pause_window(self, main_harness, fake_redis):
        from src.runner import main as runner_main
        h = main_harness()
        await quota.pause_provider("codex", _future(45), "429")
        for _ in range(3):
            await runner_main._process_job(h.job.id)
            await _drain_held(runner_main)
            assert await fake_redis.lrange(QUEUE_JOBS, 0, -1) == [str(h.job.id)]
            await fake_redis.lpop(QUEUE_JOBS)                   # what the loop's BLPOP does
        assert _kinds(h.job.id).count("job_held") == 1
        # A NEW pause window audits again.
        await quota.pause_provider("codex", _future(90), "429 again")
        await runner_main._process_job(h.job.id)
        await _drain_held(runner_main)
        assert _kinds(h.job.id).count("job_held") == 2

    async def test_stamped_provider_wins_over_preresolution(self, main_harness, fake_redis):
        # A job requeued after a Codex 429 carries `resolved_provider` from the
        # session's stamp — the hold must honour it even when the payload says
        # nothing (e.g. a task-kind job whose skill came from the LLM router).
        from src.runner import main as runner_main
        h = main_harness(job=_job(kind="task", payload={}, resolved_provider="codex"))
        await quota.pause_provider("codex", _future(45), "429")
        await runner_main._process_job(h.job.id)
        await _drain_held(runner_main)
        assert h.sessions == [] and "job_held" in _kinds(h.job.id)

    async def test_anthropic_job_is_never_held_by_a_lane_pause(self, main_harness, fake_redis):
        from src.runner import main as runner_main
        h = main_harness(job=_job(payload={}))               # default model → anthropic
        await quota.pause_provider("codex", _future(45), "429")
        await runner_main._process_job(h.job.id)
        assert len(h.sessions) == 1 and "job_held" not in _kinds(h.job.id)
        assert await fake_redis.llen(QUEUE_JOBS) == 0

    async def test_unpaused_provider_runs(self, main_harness, fake_redis):
        from src.models import JobStatus
        from src.runner import main as runner_main
        h = main_harness()
        await runner_main._process_job(h.job.id)
        assert len(h.sessions) == 1 and h.job.status == JobStatus.running.value
        assert "job_held" not in _kinds(h.job.id)

    async def test_expired_lane_pause_runs(self, main_harness, fake_redis):
        from src.runner import main as runner_main
        h = main_harness()
        await quota.pause_provider("codex", datetime.now(timezone.utc) - timedelta(seconds=1), "old")
        await runner_main._process_job(h.job.id)
        assert len(h.sessions) == 1

    async def test_redis_failure_on_the_hold_check_fails_open_to_the_session(
            self, main_harness, monkeypatch):
        # A Redis blip must not strand the job: the executor's own 429 path
        # re-pauses if the lane really is red.
        from src.runner import main as runner_main

        async def boom(provider):
            raise ConnectionError("redis down")

        monkeypatch.setattr(runner_main.quota, "is_provider_paused", boom)
        h = main_harness()
        await runner_main._process_job(h.job.id)
        assert len(h.sessions) == 1

    async def test_held_requeue_on_cancel_pushes_immediately(self, main_harness, fake_redis):
        # Graceful shutdown cancels the delayed pushes; the id must land in
        # Redis rather than be stranded until the next startup reconcile.
        from src.runner import main as runner_main
        monkeypatch_delay = 60.0
        task = runner_main._schedule_held_requeue("job-x", monkeypatch_delay)
        await asyncio.sleep(0)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        assert await fake_redis.lrange(QUEUE_JOBS, 0, -1) == ["job-x"]
        assert task not in runner_main._held_requeues


class TestCodexRateLimited:
    async def test_rate_limited_pauses_the_lane_and_requeues_at_the_front(
            self, main_harness, fake_redis):
        from src.models import JobStatus
        from src.runner import main as runner_main
        from src.runner.session import ExecutorFailed
        h = main_harness(session_exc=ExecutorFailed(
            "codex", "gpt-6-luna", "rate_limited", "429 slow_down: usage limit reached"))
        await fake_redis.rpush(QUEUE_JOBS, "other-job")

        await runner_main._process_job(h.job.id)

        # Lane paused, global key untouched.
        paused, until, reason = await quota.is_provider_paused("codex")
        assert paused is True and "429" in reason
        assert await fake_redis.get(KEY_QUOTA_PAUSED_UNTIL) is None
        assert (await quota.is_paused())[0] is False
        # FRONT requeue (INV-12 shape), job back to queued, not failed.
        assert await fake_redis.lrange(QUEUE_JOBS, 0, -1) == [str(h.job.id), "other-job"]
        assert h.finished == [] and h.escalated == [] and h.notified == []
        values = _update_values(h.db.executed[-1])
        assert values["status"] == JobStatus.queued.value
        assert "codex" in values["error_message"] and "quota" in values["error_message"]
        kinds = _kinds(h.job.id)
        assert "job_failed" not in kinds
        ev = _event(h.job.id, "job_requeued_for_quota")
        assert ev["provider"] == "codex" and ev["until"] == until.isoformat()
        assert "429" in ev["reason"]

    @pytest.mark.parametrize("terminal_reason", ["auth_expired", "api_error", "timeout", "interrupted"])
    async def test_other_executor_failures_stay_terminal(self, main_harness, fake_redis,
                                                         terminal_reason):
        from src.models import JobStatus
        from src.runner import main as runner_main
        from src.runner.session import ExecutorFailed
        h = main_harness(session_exc=ExecutorFailed("codex", "gpt-6-luna", terminal_reason, "x"))
        await runner_main._process_job(h.job.id)
        assert (await quota.is_provider_paused("codex"))[0] is False
        assert await fake_redis.llen(QUEUE_JOBS) == 0
        assert len(h.finished) == 1 and h.finished[0]["status"] is JobStatus.failed
        assert h.finished[0]["terminal_reason"] == terminal_reason
        assert _event(h.job.id, "job_failed")["error_category"] == terminal_reason

    async def test_anthropic_quota_path_is_unchanged(self, main_harness, fake_redis):
        # Control: QuotaExhausted still pauses the GLOBAL key and never a
        # provider key.
        from src.runner import main as runner_main
        h = main_harness(session_exc=quota.QuotaExhausted(_future(10), "5-hour limit"),
                         job=_job(payload={}))
        await runner_main._process_job(h.job.id)
        assert (await quota.is_paused())[0] is True
        assert not [k async for k in fake_redis.scan_iter(f"{KEY_QUOTA_PROVIDER_PREFIX}*")]
        assert await fake_redis.lrange(QUEUE_JOBS, 0, -1) == [str(h.job.id)]
        ev = _event(h.job.id, "job_requeued_for_quota")
        assert "provider" not in ev                             # existing shape untouched (C14)


# ── surfaces: /api/quota per-provider map, /status lane line, /resume <p> ──


@pytest.fixture()
def web_client():
    from fastapi.testclient import TestClient
    from src.gateway import web
    web.app.dependency_overrides[web._check_auth] = lambda: None
    try:
        yield TestClient(web.app)
    finally:
        web.app.dependency_overrides.pop(web._check_auth, None)


class TestWebQuota:
    def test_shape_keeps_global_fields_and_adds_providers(self, web_client, fake_redis):
        body = web_client.get("/api/quota").json()
        assert body["paused"] is False and body["reset_at"] is None and body["reason"] == ""
        assert "anthropic" not in body["providers"]             # the global fields ARE anthropic
        assert set(body["providers"]) == set(reg.providers()) - {"anthropic"}
        assert body["providers"]["codex"] == {"paused": False, "reset_at": None, "reason": ""}

    async def test_paused_lane_is_reported(self, web_client, fake_redis):
        until = await quota.pause_provider("codex", _future(20), "429")
        body = web_client.get("/api/quota").json()
        assert body["paused"] is False                           # global untouched
        assert body["providers"]["codex"] == {
            "paused": True, "reset_at": until.isoformat(), "reason": "429"}


def _tg_update(text: str = "/status") -> SimpleNamespace:
    msg = SimpleNamespace(text=text, reply_text=AsyncMock())
    return SimpleNamespace(effective_chat=SimpleNamespace(id=1), message=msg)


class _NoTasksDB:
    def __call__(self):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def execute(self, stmt):
        return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: []))


class TestTelegramSurfaces:
    @pytest.fixture(autouse=True)
    def _auth(self, monkeypatch):
        from src.gateway import telegram_bot as tg
        monkeypatch.setattr(tg, "_is_authorized", lambda chat_id: True)
        monkeypatch.setattr(tg, "async_session", _NoTasksDB())

    async def test_status_lists_each_paused_provider(self, fake_redis):
        from src.gateway import telegram_bot as tg
        until = await quota.pause_provider("codex", _future(20), "429 slow_down")
        upd = _tg_update()
        await tg.cmd_status(upd, SimpleNamespace(args=[]))
        text = upd.message.reply_text.call_args.args[0]
        assert "codex" in text and "paused" in text.lower()
        assert until.strftime("%H:%M") in text
        assert "429 slow" in text

    async def test_status_has_no_lane_line_when_nothing_is_paused(self, fake_redis):
        from src.gateway import telegram_bot as tg
        upd = _tg_update()
        await tg.cmd_status(upd, SimpleNamespace(args=[]))
        text = upd.message.reply_text.call_args.args[0]
        assert "paused" not in text.lower()

    async def test_resume_provider_clears_only_that_lane(self, fake_redis):
        from src.gateway import telegram_bot as tg
        await quota.pause_provider("codex", _future(20), "429")
        await quota.pause_queue(_future(20), "anthropic 5-hour")
        upd = _tg_update("/resume codex")
        await tg.cmd_resume(upd, SimpleNamespace(args=["codex"]))
        assert (await quota.is_provider_paused("codex"))[0] is False
        assert (await quota.is_paused())[0] is True                # global untouched
        assert "codex" in upd.message.reply_text.call_args.args[0]

    async def test_resume_without_args_keeps_the_global_meaning(self, fake_redis):
        from src.gateway import telegram_bot as tg
        await quota.pause_provider("codex", _future(20), "429")
        await quota.pause_queue(_future(20), "anthropic 5-hour")
        upd = _tg_update("/resume")
        await tg.cmd_resume(upd, SimpleNamespace(args=[]))
        assert (await quota.is_paused())[0] is False
        assert (await quota.is_provider_paused("codex"))[0] is True

    async def test_resume_unknown_provider_is_refused(self, fake_redis):
        from src.gateway import telegram_bot as tg
        upd = _tg_update("/resume nope")
        await tg.cmd_resume(upd, SimpleNamespace(args=["nope"]))
        text = upd.message.reply_text.call_args.args[0]
        assert "nope" in text and "unknown" in text.lower()

    async def test_resume_provider_that_is_not_paused(self, fake_redis):
        from src.gateway import telegram_bot as tg
        upd = _tg_update("/resume codex")
        await tg.cmd_resume(upd, SimpleNamespace(args=["codex"]))
        assert "not paused" in upd.message.reply_text.call_args.args[0].lower()


# ═══════════════════════════════════════════════════════════════════════════
# A3 (Observability Phase 1, 2026-10-21): the reset time is labelled by its
# source. A pause's reset time is "vendor" ONLY when a RateLimitEvent carried
# it (`detect_from_rate_limit` returned a datetime); the text heuristic and the
# default pause window are "estimated". The source lives beside the global
# pair in Redis (`quota:last_source`) and is forgotten with it (clear /
# auto-resume), so the bot's quota_paused DM can never claim a vendor-sourced
# window figure that no vendor event produced (spec §2.8 / review #4).
# ═══════════════════════════════════════════════════════════════════════════

from src.db import KEY_QUOTA_LAST_SOURCE


class TestPauseSource:
    def test_key_constant_is_the_contract_string(self):
        assert KEY_QUOTA_LAST_SOURCE == "quota:last_source"

    async def test_default_source_is_estimated(self, fake_redis):
        await quota.pause_queue(_future(5), "x")
        assert await quota.last_source() == "estimated"
        assert await fake_redis.get(KEY_QUOTA_LAST_SOURCE) == "estimated"

    async def test_unset_source_reads_as_estimated(self, fake_redis):
        # No pause at all → the label is still a valid value, never None/"".
        assert await quota.last_source() == "estimated"

    async def test_vendor_source_round_trips(self, fake_redis):
        await quota.pause_queue(_future(5), "x", source="vendor")
        assert await quota.last_source() == "vendor"

    async def test_clear_forgets_source(self, fake_redis):
        await quota.pause_queue(_future(5), "x", source="vendor")
        await quota.clear()
        assert await quota.last_source() == "estimated"
        assert await fake_redis.get(KEY_QUOTA_LAST_SOURCE) is None

    async def test_auto_resume_forgets_source(self, fake_redis):
        await quota.pause_queue(_future(-1), "expired", source="vendor")
        paused, _, _ = await quota.is_paused()
        assert paused is False
        assert await quota.last_source() == "estimated"
        assert await fake_redis.get(KEY_QUOTA_LAST_SOURCE) is None

    async def test_corrupt_pause_forgets_source(self, fake_redis):
        await quota.pause_queue(_future(5), "x", source="vendor")
        await fake_redis.set(KEY_QUOTA_PAUSED_UNTIL, "not-a-timestamp")
        paused, _, _ = await quota.is_paused()
        assert paused is False
        assert await quota.last_source() == "estimated"

    async def test_provider_pause_never_writes_the_source(self, fake_redis):
        # The per-provider lanes carry no reset time (Codex) and never raise
        # QuotaExhausted; the label belongs to the global pair only.
        await quota.pause_provider("codex", _future(5), "429")
        assert await fake_redis.get(KEY_QUOTA_LAST_SOURCE) is None

    async def test_anthropic_provider_pause_defaults_to_estimated(self, fake_redis):
        await quota.pause_provider("anthropic", _future(5), "x")
        assert await quota.last_source() == "estimated"

    def test_exception_carries_source(self):
        assert quota.QuotaExhausted(None, "r").source == "estimated"
        assert quota.QuotaExhausted(None, "r", source="vendor").source == "vendor"


class TestSessionPassesVendorOnlyForRateLimitEvent:
    def test_three_raise_sites_are_labelled(self):
        import ast
        import inspect

        from src.runner import session
        src = inspect.getsource(session._run_in_process)
        raises = [ast.unparse(n) for n in ast.walk(ast.parse(src))
                  if isinstance(n, ast.Raise) and "QuotaExhausted" in ast.unparse(n)]
        assert len(raises) == 3, raises
        vendor = [r for r in raises if 'source="vendor"' in r or "source='vendor'" in r]
        assert len(vendor) == 1, "exactly the RateLimitEvent path may claim a vendor reset"
        assert all("source=" in r for r in raises)

    def test_vendor_claim_is_conditional_on_a_real_reset_time(self):
        # The RateLimitEvent branch claims 'vendor' only when `reset_at` is a
        # datetime; a rejected event without `resets_at` is 'estimated'.
        import inspect

        from src.runner import session
        src = inspect.getsource(session._run_in_process)
        assert 'source="vendor" if reset_at is not None else "estimated"' in src


class TestMainPassesTheSourceToThePause:
    async def test_pause_queue_receives_the_exception_source(self, main_harness, fake_redis):
        from src.runner import main as runner_main
        exc = quota.QuotaExhausted(_future(10), "rate limit rejected (window=five_hour)",
                                   source="vendor")
        h = main_harness(session_exc=exc, job=_job(payload={}))
        await runner_main._process_job(h.job.id)
        assert (await quota.is_paused())[0] is True
        assert await quota.last_source() == "vendor"

    async def test_estimated_exception_pauses_as_estimated(self, main_harness, fake_redis):
        from src.runner import main as runner_main
        h = main_harness(session_exc=quota.QuotaExhausted(None, "5-hour limit"),
                         job=_job(payload={}))
        await runner_main._process_job(h.job.id)
        assert (await quota.is_paused())[0] is True
        assert await quota.last_source() == "estimated"


class TestQuotaNoticeLabelsTheSource:
    """Spec §2.8 / review #4: a reset time is 'vendor' only when a RateLimitEvent
    carried it; the text heuristic and the default window are 'estimated'."""

    def test_reset_line_names_the_source(self):
        from src.gateway import telegram_bot as tg
        at = datetime(2026, 9, 25, 14, 0, tzinfo=timezone.utc)
        assert "Reset at 14:00 UTC (vendor)" in tg.quota_paused_text(at, "rate limit rejected", "vendor")
        assert "Reset at 14:00 UTC (estimated)" in tg.quota_paused_text(at, "x", "estimated")
        assert "Reset at unknown (estimated)" in tg.quota_paused_text(None, "x", "vendor")   # no time → never 'vendor'

    def test_unknown_source_value_is_never_vendor(self):
        from src.gateway import telegram_bot as tg
        at = datetime(2026, 9, 25, 14, 0, tzinfo=timezone.utc)
        assert "(estimated)" in tg.quota_paused_text(at, "x", "")
        assert "(estimated)" in tg.quota_paused_text(at, "x", "VENDOR")

    def test_body_keeps_the_legacy_lines_and_clips_the_reason(self):
        from src.gateway import telegram_bot as tg
        text = tg.quota_paused_text(None, "r" * 500, "estimated")
        assert text.startswith("⏸ Queue paused (subscription quota).\n")
        assert "Reason: " + "r" * 200 in text and "r" * 201 not in text

    def test_notifier_reads_last_source(self):
        import inspect

        from src.gateway import telegram_bot as tg
        src = inspect.getsource(tg._quota_notifier)
        assert "quota.last_source()" in src
        assert "quota_paused_text(" in src
