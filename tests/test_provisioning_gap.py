"""
Scheduler `provisioning_gap` pre-check (Observability Phase 1, D1; design of
record P0 plan Task 21 with the re-cut plan's Deltas: payload `env_required`
is unioned with the manifest's (D-P1-7), the `.env` checked is the one
`provision_env_files` copies from (the canonical dev repo for dev-repo
topology), the stream lives under volumes/audit_log/schedules/, the DM is
one per PROJECT per UTC day and the day claim is taken only after the outbox
insert returned an id).

A due row whose project `.env` lacks a declared key is deferred (clock
advanced, no Job, no RPUSH) with a `schedule_deferred` record + one ops
notice, instead of running a full session that "completes" having produced
nothing. FAIL-OPEN everywhere else: no project, no manifest, an unreadable
manifest, an empty requirement list → the row runs exactly as today.

Pure: tmp_path .env / manifest fixtures, a fake session_scope, fake_redis.
No live atlas read, no DB, no SDK.

Run: PIPENV_DONT_LOAD_ENV=1 SERVER_ROOT="$PWD" pipenv run pytest tests/test_provisioning_gap.py -q -p no:cacheprovider
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src import audit_log
from src.config import settings
from src.db import KEY_SCHEDULE_GAP_NOTIFIED_PREFIX
from src.models import Project, Schedule
from src.registry.manifest import Manifest
from src.runner import audit_index, delivery
from src.runner import main as main_mod
from src.runner.main import (
    PROVISIONING_EXEMPT,
    env_keys_present,
    provisioning_gap,
    schedule_env_required,
)

ENV_TEXT = """\
# comment
DATABASE_URL=postgresql://localhost/atlas

export FRED_API_KEY=abc
EMPTY=
not a line
"""


# ── Pure helpers ────────────────────────────────────────────────────────────


class TestEnvKeys:
    def test_names_only_comments_and_export_handled(self, tmp_path):
        p = tmp_path / ".env"
        p.write_text(ENV_TEXT)
        assert env_keys_present(p) == {"DATABASE_URL", "FRED_API_KEY", "EMPTY"}

    def test_missing_file_is_an_empty_set(self, tmp_path):
        assert env_keys_present(tmp_path / "nope.env") == set()


class TestGap:
    def test_present_keys_are_not_a_gap(self):
        assert provisioning_gap(["DATABASE_URL"], {"DATABASE_URL"}) == []

    def test_missing_keys_are_reported_sorted(self):
        assert provisioning_gap(["TRADIER_SANDBOX_TOKEN", "FINNHUB_TOKEN"], {"DATABASE_URL"}) \
            == ["FINNHUB_TOKEN", "TRADIER_SANDBOX_TOKEN"]

    def test_the_inv3_name_atlas_already_declares_is_exempt(self):
        # VERIFIED ON PROD (2026-10-21): projects/atlas/manifest.yml declares
        # env_required: [DATABASE_URL, ANTHROPIC_API_KEY], and ANTHROPIC_API_KEY
        # is absent from the atlas .env BY DESIGN (INV-3, subscription auth
        # only). Without this exemption the pre-check would defer every atlas
        # row on its first tick.
        assert "ANTHROPIC_API_KEY" in PROVISIONING_EXEMPT
        assert provisioning_gap(["DATABASE_URL", "ANTHROPIC_API_KEY"], {"DATABASE_URL"}) == []

    def test_anthropic_prefix_is_exempt(self):
        # The runner refuses the whole vendor-auth set in its own environment,
        # so a project can never be "missing" one: the three named keys plus
        # anything under the ANTHROPIC_ prefix. A local set on purpose — NOT
        # codex_cli.DENIED_ENV_*, which denies exactly the keys this check
        # must look for.
        for name in ("ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN"):
            assert name in PROVISIONING_EXEMPT
            assert provisioning_gap([name], set()) == []
        assert provisioning_gap(["ANTHROPIC_BASE_URL", "ANTHROPIC_MODEL"], set()) == []
        # The prefix rule is a prefix rule, not a substring rule.
        assert provisioning_gap(["MY_ANTHROPIC_THING"], set()) == ["MY_ANTHROPIC_THING"]
        assert provisioning_gap(["TRADIER_SANDBOX_TOKEN"], set()) == ["TRADIER_SANDBOX_TOKEN"]

    def test_empty_requirements_never_defer(self):
        assert provisioning_gap([], set()) == []
        assert provisioning_gap([], {"X"}) == []
        assert provisioning_gap(None, set()) == []

    def test_payload_env_required_is_unioned(self):
        # D-P1-7: a schedule row may declare its own keys in job_payload.
        mf = _manifest(env_required=["DATABASE_URL"])
        sched = _sched(payload={"project_slug": "atlas", "env_required": ["TRADIER_SANDBOX_TOKEN"]})
        assert schedule_env_required(sched, mf) == ["DATABASE_URL", "TRADIER_SANDBOX_TOKEN"]
        # Manifest only / payload only / neither.
        assert schedule_env_required(_sched(payload={"project_slug": "atlas"}), mf) == ["DATABASE_URL"]
        assert schedule_env_required(sched, None) == ["TRADIER_SANDBOX_TOKEN"]
        assert schedule_env_required(_sched(payload=None), None) == []
        # Duplicates collapse; a bare string is one name; junk is ignored.
        dup = _sched(payload={"env_required": ["DATABASE_URL", "DATABASE_URL"]})
        assert schedule_env_required(dup, mf) == ["DATABASE_URL"]
        assert schedule_env_required(_sched(payload={"env_required": "FINNHUB_TOKEN"}), None) \
            == ["FINNHUB_TOKEN"]
        assert schedule_env_required(_sched(payload={"env_required": 7}), None) == []


# ── Scheduler integration ───────────────────────────────────────────────────


def _manifest(slug: str = "atlas", env_required: list[str] | None = None,
              delivery_block: dict | None = None) -> Manifest:
    data = {
        "slug": slug, "name": slug, "type": "static", "subdomain": f"{slug}.example",
        "description": "fixture", "env_required": env_required or [],
    }
    if delivery_block is not None:
        data["delivery"] = delivery_block
    mf = Manifest.from_dict(data)
    mf.validate()
    return mf


def _sched(name: str = "atlas-swing-trade-edt", payload: dict | None = None,
           project_id: uuid.UUID | None = None, now: datetime | None = None) -> SimpleNamespace:
    now = now or datetime.now(timezone.utc)
    return SimpleNamespace(
        id=uuid.uuid4(), name=name, cron_expression="45 19 * * 1-5",
        job_kind="atlas-swing-trade", job_description="fixture", job_payload=payload,
        project_id=project_id, paused=False,
        next_run_at=now - timedelta(seconds=5), last_run_at=None,
    )


class _TickSession:
    """`session_scope()` stand-in for _tick_schedules: `execute` yields the
    due rows, `get` answers Project lookups, `add` records the Job."""

    def __init__(self, due: list, projects: dict | None = None):
        self.due = due
        self.projects = projects or {}
        self.added: list = []
        self.gets: list = []

    def __call__(self):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def execute(self, stmt):
        return SimpleNamespace(scalars=lambda: iter(self.due))

    async def get(self, model, key):
        self.gets.append((model.__name__, key))
        return self.projects.get(key)

    def add(self, obj):
        if getattr(obj, "id", None) is None:
            obj.id = uuid.uuid4()
        self.added.append(obj)

    async def flush(self):
        return None


@pytest.fixture
async def tick(monkeypatch, tmp_path, fake_redis):
    """Wire _tick_schedules to tmp_path + fakes. Returns a builder."""
    root = tmp_path / "root"
    (root / "projects").mkdir(parents=True)
    monkeypatch.setattr(settings, "server_root", root)
    monkeypatch.setattr(main_mod, "redis", fake_redis)
    enqueue = AsyncMock(return_value=uuid.uuid4())
    monkeypatch.setattr(main_mod, "enqueue_notice", enqueue)
    manifests: dict[str, Manifest | None] = {}

    def _load(slug: str):
        v = manifests.get(slug)
        if isinstance(v, Exception):
            raise v
        return v
    monkeypatch.setattr(delivery, "load_project_manifest", _load)

    def build(due: list, projects: dict | None = None) -> _TickSession:
        s = _TickSession(due, projects)
        monkeypatch.setattr(main_mod, "session_scope", s)
        return s

    def env(slug: str, *names: str, where: Path | None = None) -> Path:
        d = where or (root / "projects" / slug)
        d.mkdir(parents=True, exist_ok=True)
        p = d / ".env"
        p.write_text("".join(f"{n}=x\n" for n in names))
        return p

    return SimpleNamespace(root=root, redis=fake_redis, enqueue=enqueue,
                           manifests=manifests, build=build, env=env)


def _deferrals(sched_id) -> list[dict]:
    return [e for e in audit_log.read_schedule_events(sched_id) if e["kind"] == "schedule_deferred"]


SWING_PAYLOAD = {"project_slug": "atlas", "env_required": ["TRADIER_SANDBOX_TOKEN"]}


class TestSchedulerIntegration:
    async def test_tick_defers_and_notifies_but_does_not_enqueue(self, tick):
        tick.manifests["atlas"] = _manifest(env_required=["DATABASE_URL"])
        env_path = tick.env("atlas", "DATABASE_URL")
        sched = _sched(payload=SWING_PAYLOAD)
        before = sched.next_run_at
        s = tick.build([sched])

        await main_mod._tick_schedules()

        assert s.added == [] and await tick.redis.llen("jobs:queue") == 0
        assert sched.last_run_at is not None and sched.next_run_at > before
        events = _deferrals(sched.id)
        assert len(events) == 1
        ev = events[0]
        assert ev["reason"] == "provisioning_gap"
        assert ev["missing"] == ["TRADIER_SANDBOX_TOKEN"]
        assert ev["project"] == "atlas" and ev["schedule"] == sched.name
        assert ev["env_file"] == str(env_path)
        assert ev["schedule_id"] == str(sched.id)
        # One ops notice, warn, naming the row, the file and the key.
        assert tick.enqueue.await_count == 1
        notice = tick.enqueue.await_args.args[0]
        assert notice.notice_kind == "schedule_deferred" and notice.severity == "warn"
        assert notice.subject_type == "schedule" and notice.subject_id == str(sched.id)
        assert sched.name in notice.body and str(env_path) in notice.body
        assert "TRADIER_SANDBOX_TOKEN" in notice.body
        # Names only — the value never reaches the row or the stream.
        assert "=x" not in notice.body and "=x" not in json.dumps(ev)

    async def test_tick_runs_the_row_when_nothing_is_missing(self, tick):
        tick.manifests["atlas"] = _manifest(env_required=["DATABASE_URL"])
        tick.env("atlas", "DATABASE_URL", "TRADIER_SANDBOX_TOKEN")
        sched = _sched(payload=SWING_PAYLOAD)
        s = tick.build([sched])

        await main_mod._tick_schedules()

        assert len(s.added) == 1 and await tick.redis.llen("jobs:queue") == 1
        assert s.added[0].origin_channel == "scheduler"
        assert _deferrals(sched.id) == []
        assert tick.enqueue.await_count == 0

    async def test_slug_comes_from_payload_before_project_id(self, tick):
        pid = uuid.uuid4()
        tick.manifests["atlas"] = _manifest(env_required=[])
        tick.manifests["other"] = _manifest("other", env_required=["OTHER_KEY"])
        tick.env("atlas", "DATABASE_URL")                 # lacks TRADIER → defers
        tick.env("other", "OTHER_KEY")                    # complete
        project = SimpleNamespace(id=pid, slug="other")

        # payload slug wins: atlas is checked, "other" is never looked up
        sched = _sched(payload=SWING_PAYLOAD, project_id=pid)
        s = tick.build([sched], {pid: project})
        await main_mod._tick_schedules()
        assert s.added == [] and s.gets == []
        assert _deferrals(sched.id)[0]["project"] == "atlas"

        # no payload slug: project_id → Project.slug via s.get in the open session
        tick.env("other")                                 # now lacks OTHER_KEY
        sched2 = _sched(name="other-row", payload=None, project_id=pid)
        s2 = tick.build([sched2], {pid: project})
        await main_mod._tick_schedules()
        assert s2.added == [] and s2.gets == [("Project", pid)]
        assert _deferrals(sched2.id)[0]["project"] == "other"
        assert _deferrals(sched2.id)[0]["missing"] == ["OTHER_KEY"]

    async def test_a_row_with_no_project_runs(self, tick):
        # No project_slug, no project_id → nothing to check, even with a
        # payload env_required: fail-open.
        sched = _sched(payload={"env_required": ["TRADIER_SANDBOX_TOKEN"]}, project_id=None)
        s = tick.build([sched])
        await main_mod._tick_schedules()
        assert len(s.added) == 1 and await tick.redis.llen("jobs:queue") == 1
        assert _deferrals(sched.id) == [] and tick.enqueue.await_count == 0

    async def test_an_unreadable_manifest_runs_the_row(self, tick):
        tick.manifests["atlas"] = RuntimeError("yaml exploded")
        tick.env("atlas")                                 # lacks everything
        sched = _sched(payload=SWING_PAYLOAD)
        s = tick.build([sched])
        await main_mod._tick_schedules()
        assert len(s.added) == 1 and await tick.redis.llen("jobs:queue") == 1
        assert _deferrals(sched.id) == [] and tick.enqueue.await_count == 0

    async def test_a_missing_manifest_still_honours_the_payload_keys(self, tick):
        # D-P1-7 without a manifest: load_project_manifest → None is not an
        # error; the payload's keys are checked against projects/<slug>/.env.
        tick.manifests["atlas"] = None
        env_path = tick.env("atlas", "DATABASE_URL")
        sched = _sched(payload=SWING_PAYLOAD)
        s = tick.build([sched])
        await main_mod._tick_schedules()
        assert s.added == []
        assert _deferrals(sched.id)[0]["env_file"] == str(env_path)

    async def test_checks_the_canonical_dev_repo_not_the_runtime_clone(self, tick, tmp_path):
        # dev-repo topology (atlas): provision_env_files copies from the dev
        # clone, so that is the .env the pre-check reads — the runtime clone's
        # complete .env must not mask a gap in the canonical one.
        dev = tmp_path / "dev-atlas"
        dev.mkdir()
        tick.manifests["atlas"] = _manifest(env_required=["DATABASE_URL"], delivery_block={
            "topology": "dev-repo", "dev_repo": str(dev), "runtime_clone": "pull-only",
            "deployable": False, "env_files": [".env"],
        })
        tick.env("atlas", "DATABASE_URL", "TRADIER_SANDBOX_TOKEN")   # runtime clone: complete
        dev_env = tick.env("atlas", "DATABASE_URL", where=dev)        # canonical: lacks it
        sched = _sched(payload=SWING_PAYLOAD)
        s = tick.build([sched])
        await main_mod._tick_schedules()
        assert s.added == []
        ev = _deferrals(sched.id)[0]
        assert ev["env_file"] == str(dev_env)
        assert str(dev_env) in tick.enqueue.await_args.args[0].body

    async def test_deferral_is_unconditional_once_missing(self, tick, monkeypatch):
        # The audit append and the notice are each best-effort; neither
        # failing may run the row or stop the clock.
        tick.manifests["atlas"] = _manifest(env_required=[])
        tick.env("atlas")
        monkeypatch.setattr(audit_log, "append_schedule_event",
                            lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")))
        tick.enqueue.side_effect = RuntimeError("outbox exploded")
        sched = _sched(payload=SWING_PAYLOAD)
        before = sched.next_run_at
        s = tick.build([sched])
        await main_mod._tick_schedules()
        assert s.added == [] and await tick.redis.llen("jobs:queue") == 0
        assert sched.next_run_at > before and sched.last_run_at is not None

    async def test_one_dm_per_project_per_day(self, tick):
        tick.manifests["atlas"] = _manifest(env_required=[])
        tick.env("atlas")
        a = _sched(name="atlas-swing-trade-edt", payload=SWING_PAYLOAD)
        b = _sched(name="atlas-swing-supervise-edt", payload=SWING_PAYLOAD)
        tick.build([a, b])
        await main_mod._tick_schedules()
        # a second tick of the same rows, same UTC day
        a.next_run_at = b.next_run_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        await main_mod._tick_schedules()

        assert len(_deferrals(a.id)) == 2 and len(_deferrals(b.id)) == 2
        assert tick.enqueue.await_count == 1
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        key = f"{KEY_SCHEDULE_GAP_NOTIFIED_PREFIX}atlas:{today}"
        assert await tick.redis.get(key) == "1"
        ttl = await tick.redis.ttl(key)
        assert 0 < ttl <= 129600

    async def test_day_claim_not_burned_when_notice_dropped(self, tick):
        tick.manifests["atlas"] = _manifest(env_required=[])
        tick.env("atlas")
        tick.enqueue.return_value = None                  # insert failed
        sched = _sched(payload=SWING_PAYLOAD)
        tick.build([sched])
        await main_mod._tick_schedules()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        assert await tick.redis.get(f"{KEY_SCHEDULE_GAP_NOTIFIED_PREFIX}atlas:{today}") is None

        tick.enqueue.return_value = uuid.uuid4()          # outbox back
        sched.next_run_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        await main_mod._tick_schedules()
        assert tick.enqueue.await_count == 2
        assert await tick.redis.get(f"{KEY_SCHEDULE_GAP_NOTIFIED_PREFIX}atlas:{today}") == "1"

    async def test_deferred_stream_is_not_indexed_as_a_job(self, tick):
        tick.manifests["atlas"] = _manifest(env_required=[])
        tick.env("atlas")
        sched = _sched(payload=SWING_PAYLOAD)
        tick.build([sched])
        await main_mod._tick_schedules()
        stream = audit_log.schedule_log_path(sched.id)
        assert stream.exists()
        assert stream.parent == settings.audit_log_dir / "schedules"
        # rebuild_index globs the top level only: the stream is not a job.
        assert audit_index.rebuild_index(settings.audit_log_dir) == 0
        assert not (settings.audit_log_dir / f"{sched.id}.jsonl").exists()


# ── /status surfaces the deferred rows ──────────────────────────────────────


class _SchedDB:
    def __init__(self, rows):
        self.rows = rows

    def __call__(self):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def execute(self, stmt):
        # cmd_status runs two selects: Task (active tasks) and Schedule.
        ent = stmt.column_descriptions[0]["entity"]
        rows = self.rows if ent is Schedule else []
        return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: rows))


class TestStatusLine:
    async def test_status_lists_each_deferred_row(self, monkeypatch, tmp_path, fake_redis):
        from src.gateway import telegram_bot as tg
        monkeypatch.setattr(settings, "server_root", tmp_path)
        monkeypatch.setattr(tg, "_is_authorized", lambda chat_id: True)
        deferred = _sched(name="atlas-swing-trade-edt", payload=SWING_PAYLOAD)
        deferred.cron_expression = "* * * * *"
        fine = _sched(name="atlas-daily-brief", payload=None)
        audit_log.append_schedule_event(deferred.id, "schedule_deferred", schedule=deferred.name,
                                        reason="provisioning_gap",
                                        missing=["TRADIER_SANDBOX_TOKEN"], project="atlas",
                                        env_file="/x/.env")
        monkeypatch.setattr(tg, "async_session", _SchedDB([deferred, fine]))
        msg = SimpleNamespace(text="/status", reply_text=AsyncMock())
        upd = SimpleNamespace(effective_chat=SimpleNamespace(id=1), message=msg)

        await tg.cmd_status(upd, SimpleNamespace(args=[]))

        text = msg.reply_text.call_args.args[0]
        assert "deferred: atlas-swing-trade-edt (provisioning_gap:" in text
        assert "TRADIER_SANDBOX_TOKEN" in text
        assert "atlas-daily-brief" not in text
