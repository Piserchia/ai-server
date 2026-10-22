"""
Cross-vendor writer slice T4 — dispatch at the single executor call site
(`docs/superpowers/plans/2026-10-21-cross-vendor-writer-slice.md` §5 T4;
old spec §2.4 / §2.6 / §5.3 belt 3b).

What is covered, pure/fixture style (no network, no SDK, no DB, no Redis,
no `codex` process — the executor is a fake injected through
`session._EXECUTORS`):

1. The fail-closed lane refusals, each one, as a pure predicate and through
   `run_session` (raised BEFORE the workspace clone exists).
2. Model precedence `payload > pin > default` with the audited reason.
3. The Codex branch: what the executor is called with, the audit events
   around it (`provider_selected`, `job_started.provider`,
   `job_completed{provider, model_served, terminal_reason}`), the DB stamp,
   the marker protocol on the executor's final text, no `env_files`, no
   ff-sync, clone kept for the T5 gate.
4. Executor failures surface as `ExecutorFailed` (terminal in main, never
   escalated) and `interrupt()` reaches the executor.
7. (Review round 1) No failure on a non-Anthropic lane — session timeout,
   pre-process executor error, generic exception — ever escalates onto the
   skill's Anthropic `on_failure` model; the executor's own deadline sits
   strictly below main's ceiling.
5. The Anthropic path is behaviourally unchanged: same helpers, same
   sync/cleanup, plus the additive provider fields.
"""

from __future__ import annotations

import ast
import asyncio
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

from src import audit_log
from src.config import settings
from src.registry import models as reg
from src.registry.skills import SkillConfig
from src.runner import session, workspaces
from src.runner.executors.codex_cli import CodexNotFound, ExecResult
from src.runner.result_capture import ResultCapture

REPO = Path(__file__).resolve().parents[1]

CODEX = reg.ModelRef("codex", "gpt-6-luna")
ANTH = reg.ModelRef("anthropic", "claude-sonnet-4-6")


def _skill(name: str = "demo", **kw) -> SkillConfig:
    kw.setdefault("body", "Do the thing.")
    return SkillConfig(name=name, **kw)


# ── 1. Pure refusal predicates ────────────────────────────────────────────


def test_code_server_set_matches_plan():
    assert session.CODE_SERVER_SKILLS == frozenset({
        "server-patch", "server-deploy", "new-skill", "deploy-director",
        "atlas-redeploy", "project-redeploy",
    })


@pytest.mark.parametrize("created_by, owner", [
    ("telegram:123456", True),
    ("web", True),
    ("cli", True),
    ("cli:laptop", True),
    ("scheduler", False),
    ("escalation:abcd1234", False),
    ("dispatch-mcp", False),
    ("event-trigger:idle-queue", False),
    ("plan:abcd1234", False),
    ("evaluator:abcd1234", False),
    ("", False),
    (None, False),
    ("webhook", False),          # prefix match would be a hole
    ("bot-error-handler", False),
])
def test_is_owner_origin(created_by, owner):
    assert session.is_owner_origin(created_by) is owner


def _refusal(ref=CODEX, *, skill_name="demo", skill_cfg=None, isolation="workspace",
             payload=None, created_by="telegram:1", code_server_providers=frozenset({"anthropic"})):
    return session.lane_refusal(
        ref, skill_name=skill_name, skill_cfg=skill_cfg, isolation=isolation,
        payload=payload, created_by=created_by,
        code_server_providers=code_server_providers)


def test_lane_refusal_anthropic_is_never_refused():
    # Every rule below is a non-Anthropic rule; the Anthropic path is untouched.
    assert _refusal(ANTH, isolation="none", skill_cfg=_skill(subagents=["x"],
                    tags=["needs-dispatch-mcp"]), skill_name="server-patch",
                    created_by="scheduler", payload={"model": "opus"}) is None


def test_lane_refusal_allows_a_clean_workspace_job():
    assert _refusal(skill_cfg=_skill(isolation="workspace", model="codex/gpt-6-luna")) is None
    # Generic task (no skill) on the forced workspace tier.
    assert _refusal(skill_name="", skill_cfg=None, payload={"model": "codex/gpt-6-luna"}) is None


@pytest.mark.parametrize("tier", ["none", "host"])
def test_lane_refusal_requires_workspace_tier(tier):
    reason = _refusal(isolation=tier, skill_cfg=_skill(isolation=tier))
    assert reason and "isolation" in reason and tier in reason


def test_lane_refusal_subagents():
    reason = _refusal(skill_cfg=_skill(subagents=["code-review"]))
    assert reason and "subagents" in reason


@pytest.mark.parametrize("tag", ["needs-projects-mcp", "needs-dispatch-mcp"])
def test_lane_refusal_mcp_tags(tag):
    reason = _refusal(skill_cfg=_skill(tags=["x", tag]))
    assert reason and tag in reason


@pytest.mark.parametrize("name", sorted(session.CODE_SERVER_SKILLS))
def test_lane_refusal_code_server_set_pinned_by_setting(name):
    # D-A default: only anthropic may touch the server's own repo.
    reason = _refusal(skill_name=name, skill_cfg=_skill(name))
    assert reason and "code-server" in reason and "ROUTER_CODE_SERVER_PROVIDERS" in reason
    # The mechanism exists; the flip is one setting.
    assert _refusal(skill_name=name, skill_cfg=_skill(name),
                    code_server_providers=frozenset({"anthropic", "codex"})) is None


def test_lane_refusal_payload_override_on_non_owner_job_for_anthropic_pinned_skill():
    pinned = _skill(model="claude-opus-5")
    payload = {"model": "codex/gpt-6-luna"}
    # Scheduler / escalation / dispatch-mcp: refused.
    for origin in ("scheduler", "escalation:abcd1234", "dispatch-mcp", "", None):
        reason = _refusal(skill_cfg=pinned, payload=payload, created_by=origin)
        assert reason and "override" in reason, origin
    # The owner may override from Telegram / web / CLI.
    for origin in ("telegram:1", "web", "cli"):
        assert _refusal(skill_cfg=pinned, payload=payload, created_by=origin) is None
    # No pin on the skill → a schedule row may carry the model (plan §2).
    assert _refusal(skill_cfg=_skill(), payload=payload, created_by="scheduler") is None
    # The skill itself pins codex → the payload only repeats it.
    assert _refusal(skill_cfg=_skill(model="codex/gpt-6-luna"), payload=payload,
                    created_by="scheduler") is None
    # No payload model at all (the skill pin chose codex) → nothing to refuse.
    assert _refusal(skill_cfg=_skill(model="codex/gpt-6-luna"), payload={},
                    created_by="scheduler") is None


def test_code_server_providers_reads_settings(monkeypatch):
    monkeypatch.setattr(settings, "router_code_server_providers", " Anthropic , codex ")
    assert session.code_server_providers() == frozenset({"anthropic", "codex"})
    monkeypatch.setattr(settings, "router_code_server_providers", "")
    assert session.code_server_providers() == frozenset()


# ── 2. Precedence + executor presence ─────────────────────────────────────


def test_resolve_model_choice_reports_the_source(monkeypatch):
    monkeypatch.setattr(settings, "router_providers_enabled", "anthropic,codex")
    monkeypatch.setattr(settings, "default_model", "claude-sonnet-4-6")
    ref, why = session.resolve_model_choice({"model": "codex/gpt-6-luna"}, _skill(model="claude-opus-5"))
    assert (ref, why) == (CODEX, "payload")
    ref, why = session.resolve_model_choice({}, _skill(model="codex/gpt-6-sol"))
    assert (ref, why) == (reg.ModelRef("codex", "gpt-6-sol"), "pin")
    ref, why = session.resolve_model_choice({"model": ""}, _skill())
    assert (ref, why) == (ANTH, "default")
    ref, why = session.resolve_model_choice(None, None)
    assert (ref, why) == (ANTH, "default")


def test_resolve_model_codex_resolves_when_enabled(monkeypatch):
    # T4 replaces T1's interim "no executor" refusal for codex: the executor
    # exists now, so an enabled codex id resolves to its ModelRef.
    monkeypatch.setattr(settings, "router_providers_enabled", "anthropic,codex")
    assert session._resolve_model({"model": "codex/gpt-6-luna"}, None) == CODEX


def test_resolve_model_still_refuses_a_provider_without_an_executor(monkeypatch):
    # The registry's `executor:` field must name a module this runner has.
    monkeypatch.setattr(settings, "router_providers_enabled", "anthropic,codex")
    monkeypatch.setattr(session, "_EXECUTORS", {})
    with pytest.raises(reg.ProviderRefused) as ei:
        session._resolve_model({"model": "codex/gpt-6-luna"}, None)
    assert "no executor" in ei.value.reason
    # Anthropic never depends on the executor table (it is the in-process SDK).
    assert session._resolve_model({}, None).provider == "anthropic"


def test_executor_table_is_keyed_by_the_registry_executor_name():
    assert reg.REGISTRY.provider("codex").executor in session._EXECUTORS
    assert session.executor_for("anthropic") is None
    mod = session.executor_for("codex")
    assert mod is not None and callable(mod.run) and callable(mod.interrupt)


def test_build_executor_prompt_prepends_the_system_prompt():
    prompt = session.build_executor_prompt("SYSTEM DIRECTIVE", "fix the flaky test")
    assert prompt.startswith("SYSTEM DIRECTIVE")
    assert prompt.rstrip().endswith("fix the flaky test")
    assert prompt.index("SYSTEM DIRECTIVE") < prompt.index("fix the flaky test")
    # The CLI's argv builder refuses a prompt that begins with '-'.
    assert not session.build_executor_prompt("", "-rf /").startswith("-")


# ── 3./4./5. run_session end to end with fakes ─────────────────────────────


class _FakeExecutor:
    """Stands in for `executors.codex_cli` behind `session._EXECUTORS`."""

    def __init__(self, result: ExecResult | None = None):
        self.calls: list[dict] = []
        self.interrupted: list[str] = []
        self.result = result or ExecResult(
            final_text="Did the work.\nTASK_COMPLETE: fixed the flaky test",
            usage={"input_tokens": 10, "output_tokens": 5},
            terminal_reason="ok", model_served="gpt-6-luna-2026-10",
            thread_id="thr_1", cli_version="0.162.0", exit_code=0, error=None)

    async def run(self, job, **kw):
        self.calls.append({"job": job, **kw})
        return self.result

    async def interrupt(self, job_id):
        self.interrupted.append(str(job_id))
        return True


class _FakeDB:
    """Captures the UPDATE run_session issues for the resolved_* stamp."""

    def __init__(self):
        self.statements = []

    def __call__(self):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def execute(self, stmt):
        self.statements.append(stmt)

    async def commit(self):
        pass

    @property
    def params(self) -> dict:
        """The resolved_* stamp run_session issues before the session (B3
        added a second, post-session column stamp — see `column_params`)."""
        assert self.statements, "no UPDATE captured"
        return dict(self.statements[0].compile().params)

    @property
    def column_params(self) -> dict:
        assert len(self.statements) >= 2, "no post-session column stamp captured"
        return dict(self.statements[-1].compile().params)


def _job(**kw) -> SimpleNamespace:
    base = dict(id=uuid.uuid4(), kind="demo", description="fix the flaky test in pickem",
                payload={"model": "codex/gpt-6-luna"}, task_id=None, parent_job_id=None,
                project_id=None, created_by="telegram:1")
    base.update(kw)
    return SimpleNamespace(**base)


@pytest.fixture
def harness(tmp_path, monkeypatch):
    """Everything `run_session` touches, faked; returns a mutable namespace
    the test can tune before calling `session.run_session`."""
    monkeypatch.setattr(settings, "server_root", tmp_path / "root")
    monkeypatch.setattr(settings, "router_providers_enabled", "anthropic,codex")
    monkeypatch.setattr(settings, "router_code_server_providers", "anthropic")
    monkeypatch.setattr(settings, "codex_sandbox_default", "workspace-write")
    monkeypatch.setattr(settings, "default_model", "claude-sonnet-4-6")
    (tmp_path / "root").mkdir()

    canonical = tmp_path / "canonical"
    canonical.mkdir()
    (canonical / ".git").mkdir()      # T5: a non-Anthropic lane needs a git canonical
    h = SimpleNamespace(
        skill=_skill(isolation="workspace"), skill_name="demo",
        deliv=None, canonical=canonical, slug="demo",
        executor=_FakeExecutor(), db=_FakeDB(),
        created=[], synced=[], cleaned=[], env_files=[], sdk_calls=[],
    )

    async def fake_resolve_skill(job):
        return h.skill_name, h.skill

    async def fake_resolve_project(job, skill_name=None):
        # A PROJECT canonical with a slug (T5 review round 1: a slug-less
        # job resolves to the server root, which D-A refuses by path).
        return h.canonical, h.deliv, False, h.slug

    def fake_create_workspace(job_id, canon, base_dir):
        ws_path = tmp_path / "ws" / job_id
        ws_path.mkdir(parents=True)
        ws = workspaces.Workspace(path=ws_path, canonical=canon, pushes_to_origin=False)
        h.created.append(ws)
        return ws

    def fake_sync(ws):
        h.synced.append(ws)
        return True, "fake sync"

    def fake_cleanup(ws, *, keep=False):
        h.cleaned.append((ws, keep))

    def fake_env_files(ws_path, canon, entries):
        h.env_files.append(list(entries))
        return list(entries)

    async def fake_run_in_process(job_id, prompt, options):
        h.sdk_calls.append((job_id, prompt, options))
        # B3: the 3-tuple — the typed capture rides beside the usage dict.
        return ("SDK did it.\nTASK_COMPLETE: via the SDK", {"input_tokens": 3, "output_tokens": 1},
                ResultCapture(usage={"input_tokens": 3, "output_tokens": 1}, num_turns=1,
                              duration_api_ms=500, total_cost_usd=0.001,
                              model_usage={"claude-sonnet-4-6": {}}))

    monkeypatch.setattr(session, "_resolve_skill", fake_resolve_skill)
    monkeypatch.setattr(session, "_resolve_project", fake_resolve_project)
    monkeypatch.setattr(session.workspaces, "create_workspace", fake_create_workspace)
    monkeypatch.setattr(session.workspaces, "sync_canonical", fake_sync)
    monkeypatch.setattr(session.workspaces, "cleanup_workspace", fake_cleanup)
    monkeypatch.setattr(session.workspaces, "provision_env_files", fake_env_files)
    # T5: the pre-push gate sees an EMPTY diff here (no reviewer, no commit),
    # so these T4 tests keep exercising dispatch alone; the gate itself is
    # covered in tests/test_pre_push_gate.py.
    monkeypatch.setattr(session.workspaces, "head_sha", lambda path: "b" * 40)
    monkeypatch.setattr(session.review, "diff_for_gate", lambda cwd, base_sha: "")
    monkeypatch.setattr(session, "_run_in_process", fake_run_in_process)
    monkeypatch.setattr(session, "async_session", h.db)
    monkeypatch.setattr(session, "_EXECUTORS", {"codex_cli": h.executor})
    return h


def _kinds(job_id) -> list[str]:
    return [e["kind"] for e in audit_log.read(str(job_id))]


def _event(job_id, kind) -> dict:
    found = [e for e in audit_log.read(str(job_id)) if e["kind"] == kind]
    assert found, f"no {kind} event"
    return found[-1]


async def test_run_session_dispatches_to_the_codex_executor(harness):
    h = harness
    h.deliv = SimpleNamespace(env_files=[".env"], topology="in-place")
    job = _job()

    result = await session.run_session(job)

    # The executor was called once, in the clone, with the pinned model and
    # the default sandbox; the prompt carries the directive, the job id, the
    # marker protocol and the description (plan §4h — never AGENTS.md).
    assert len(h.executor.calls) == 1
    call = h.executor.calls[0]
    assert call["job"] is job
    assert Path(call["cwd"]) == h.created[0].path
    assert call["model_id"] == "gpt-6-luna"
    assert call["sandbox"] == "workspace-write"
    assert call["timeout_s"] > 0
    assert "You are working inside the assistant server." in call["prompt"]
    assert f"**Job id**: `{job.id}`" in call["prompt"]
    assert "TASK_COMPLETE:" in call["prompt"]
    assert call["prompt"].rstrip().endswith("fix the flaky test in pickem")
    assert "Do the thing." in call["prompt"]              # skill body
    assert not (h.created[0].path / "AGENTS.md").exists()
    # The Anthropic SDK path never ran.
    assert h.sdk_calls == []

    # Audit: provider_selected → … → job_started.provider → job_completed{…}.
    kinds = _kinds(job.id)
    assert kinds.index("provider_selected") < kinds.index("workspace_created") < kinds.index("job_started")
    sel = _event(job.id, "provider_selected")
    assert (sel["provider"], sel["model"], sel["reason"]) == ("codex", "gpt-6-luna", "payload")
    started = _event(job.id, "job_started")
    assert started["provider"] == "codex" and started["model"] == "gpt-6-luna"
    assert started["isolation"] == "workspace"
    done = _event(job.id, "job_completed")
    assert (done["provider"], done["model_served"], done["terminal_reason"]) == \
        ("codex", "gpt-6-luna-2026-10", "ok")
    assert done["usage"] == {"input_tokens": 10, "output_tokens": 5}
    # Marker protocol ran on the executor's final text (plan §4i).
    assert _event(job.id, "task_complete")["summary"] == "fixed the flaky test"
    assert audit_log.summary_path(str(job.id)).read_text().startswith("Did the work.")

    # Result dict: the existing keys plus the provider fields.
    assert result["summary"].startswith("Did the work.")
    assert result["skill"] == "demo" and result["isolation"] == "workspace"
    assert result["provider"] == "codex"
    assert result["model"] == "gpt-6-luna"
    assert result["model_served"] == "gpt-6-luna-2026-10"
    assert result["terminal_reason"] == "ok"

    # DB stamp carries the provider beside the bare model id.
    p = h.db.params
    assert p["resolved_provider"] == "codex"
    assert p["resolved_model"] == "gpt-6-luna"
    assert p["resolved_skill"] == "demo"

    # Containment: no env_files for a non-Anthropic executor (plan §6). With
    # an empty diff the T5 gate skips: nothing to publish, no ff-sync, the
    # clone is removed like any clean success.
    assert h.env_files == []
    assert _event(job.id, "workspace_created")["env_files"] == []
    assert h.synced == []
    assert "workspace_synced" not in kinds
    assert _event(job.id, "merge_gate_skipped")["reason"] == "empty_diff"
    assert h.cleaned == [(h.created[0], False)]
    assert result["review_outcome"] is None


async def test_run_session_read_only_skill_gets_the_read_only_sandbox(harness):
    h = harness
    h.skill = _skill(isolation="workspace", privilege_class="read-only")
    await session.run_session(_job())
    assert h.executor.calls[0]["sandbox"] == "read-only"


async def test_run_session_skill_pin_selects_codex_without_a_payload(harness):
    h = harness
    h.skill = _skill(isolation="workspace", model="codex/gpt-6-sol")
    job = _job(payload={}, created_by="scheduler")      # a schedule row, no override
    await session.run_session(job)
    assert h.executor.calls[0]["model_id"] == "gpt-6-sol"
    sel = _event(job.id, "provider_selected")
    assert (sel["provider"], sel["reason"]) == ("codex", "pin")


async def test_run_session_executor_failure_is_executor_failed(harness):
    h = harness
    h.executor.result = ExecResult(
        final_text="", usage={}, terminal_reason="rate_limited", model_served=None,
        thread_id="thr_2", cli_version="0.162.0", exit_code=1,
        error="codex: usage limit reached, slow_down")
    job = _job()
    with pytest.raises(session.ExecutorFailed) as ei:
        await session.run_session(job)
    exc = ei.value
    assert isinstance(exc, RuntimeError)
    assert (exc.provider, exc.model_id, exc.terminal_reason) == ("codex", "gpt-6-luna", "rate_limited")
    assert exc.model_served is None
    assert "slow_down" in str(exc) and "rate_limited" in str(exc)
    kinds = _kinds(job.id)
    assert "job_started" in kinds and "job_completed" not in kinds
    assert h.synced == []
    assert h.cleaned == [(h.created[0], True)]          # failed clone kept, as today


@pytest.mark.parametrize("tweak, fragment", [
    (dict(skill=_skill(isolation="none")), "isolation"),
    (dict(skill=_skill(isolation="workspace", subagents=["code-review"])), "subagents"),
    (dict(skill=_skill(isolation="workspace", tags=["needs-dispatch-mcp"])), "needs-dispatch-mcp"),
    (dict(skill=_skill("server-patch", isolation="workspace"), skill_name="server-patch"), "code-server"),
    (dict(skill=_skill(isolation="workspace", model="claude-opus-5"), created_by="scheduler"), "override"),
])
async def test_run_session_refuses_before_any_clone_or_process(harness, tweak, fragment):
    h = harness
    created_by = tweak.pop("created_by", "telegram:1")
    for k, v in tweak.items():
        setattr(h, k, v)
    job = _job(created_by=created_by)
    with pytest.raises(reg.ProviderRefused) as ei:
        await session.run_session(job)
    assert fragment in ei.value.reason
    assert ei.value.provider == "codex" and ei.value.model_id == "gpt-6-luna"
    assert h.created == [] and h.executor.calls == [] and h.sdk_calls == []
    kinds = _kinds(job.id)
    assert "provider_selected" in kinds            # the pick was recorded …
    assert "workspace_created" not in kinds        # … but nothing was spun up
    assert "job_started" not in kinds
    assert h.db.statements == []                   # resolved_* never stamped


async def test_run_session_disabled_provider_refused_first(harness, monkeypatch):
    monkeypatch.setattr(settings, "router_providers_enabled", "anthropic")
    job = _job()
    with pytest.raises(reg.ProviderRefused) as ei:
        await session.run_session(job)
    assert "not enabled" in ei.value.reason
    assert _kinds(job.id) == []                    # refused before provider_selected


async def test_run_session_anthropic_path_is_unchanged(harness):
    h = harness
    h.skill = _skill(isolation="workspace", model="claude-opus-5")
    h.deliv = SimpleNamespace(env_files=[".env"], topology="in-place")
    job = _job(payload={"model": "sonnet"})

    result = await session.run_session(job)

    assert h.executor.calls == []
    assert len(h.sdk_calls) == 1
    job_id, prompt, options = h.sdk_calls[0]
    assert job_id == str(job.id) and prompt == job.description
    assert options.model == "claude-sonnet-4-6"
    assert str(h.created[0].path) == options.cwd
    assert options.hooks                               # workspace guard hooks still attached
    # Same system prompt the executor branch would get (one assembly).
    assert "You are working inside the assistant server." in options.system_prompt
    assert "Do the thing." in options.system_prompt
    # env_files provisioned, canonical synced, clone removed — as today.
    assert h.env_files == [[".env"]]
    assert h.synced == [h.created[0]]
    assert h.cleaned == [(h.created[0], False)]
    # Additive provider fields.
    sel = _event(job.id, "provider_selected")
    assert (sel["provider"], sel["model"], sel["reason"]) == ("anthropic", "claude-sonnet-4-6", "payload")
    assert _event(job.id, "job_started")["provider"] == "anthropic"
    done = _event(job.id, "job_completed")
    # B3: model_served is the captured value (ResultMessage.model_usage).
    assert (done["provider"], done["model_served"], done["terminal_reason"]) == \
        ("anthropic", "claude-sonnet-4-6", "ok")
    assert done["usage"] == {"input_tokens": 3, "output_tokens": 1}
    assert result["provider"] == "anthropic" and result["terminal_reason"] == "ok"
    assert result["model"] == "claude-sonnet-4-6" and result["model_served"] == "claude-sonnet-4-6"
    assert result["summary"].startswith("SDK did it.")
    assert h.db.params["resolved_provider"] == "anthropic"
    assert h.db.params["resolved_model"] == "claude-sonnet-4-6"


def test_build_options_system_prompt_equals_the_shared_assembly(tmp_path, monkeypatch):
    # `_build_options` builds through the same helper the executor branch
    # uses, so the two can never drift; and passing the pre-built prompt in
    # is byte-identical to letting `_build_options` build it.
    monkeypatch.setattr(settings, "server_root", tmp_path)
    monkeypatch.setattr(settings, "router_providers_enabled", "anthropic")
    skill = _skill(isolation="workspace", model="claude-opus-5", context_files=["README.md"])
    job = _job(payload={}, task_id=None)
    sp = session._build_system_prompt(job, tmp_path, skill, [], canonical_cwd=None)
    a = session._build_options(job, tmp_path, skill, [])
    b = session._build_options(job, tmp_path, skill, [], system_prompt=sp)
    assert a.system_prompt == b.system_prompt == sp
    assert "**Read these files first**" in sp and "README.md" in sp
    assert f"**Job id**: `{job.id}`" in sp
    assert "# Active skill" in sp


async def test_interrupt_falls_through_to_the_executor(monkeypatch):
    fake = _FakeExecutor()
    monkeypatch.setattr(session, "_EXECUTORS", {"codex_cli": fake})
    monkeypatch.setattr(session, "_running_sessions", {})
    assert await session.interrupt("job-1") is True
    assert fake.interrupted == ["job-1"]

    class _Nope:
        async def interrupt(self, job_id):
            return False
    monkeypatch.setattr(session, "_EXECUTORS", {"codex_cli": _Nope()})
    assert await session.interrupt("job-2") is False


# ── 6. Runner main: ExecutorFailed terminal, provider columns stamped ─────


def _handler_type_name(node: ast.ExceptHandler) -> str:
    t = node.type
    if isinstance(t, ast.Attribute):
        return t.attr
    if isinstance(t, ast.Name):
        return t.id
    return ""


def _process_job_handlers() -> list[ast.ExceptHandler]:
    tree = ast.parse((REPO / "src" / "runner" / "main.py").read_text())
    process_job = next(n for n in ast.walk(tree)
                       if isinstance(n, ast.AsyncFunctionDef) and n.name == "_process_job")
    for node in ast.walk(process_job):
        if isinstance(node, ast.Try) and any(
                _handler_type_name(h) == "ExecutorFailed" for h in node.handlers):
            return list(node.handlers)
    raise AssertionError("_process_job has no ExecutorFailed handler")


def test_main_executor_failed_is_terminal_and_never_escalated():
    names = [_handler_type_name(h) for h in _process_job_handlers()]
    assert names.index("ExecutorFailed") < names.index("Exception")
    handler = next(h for h in _process_job_handlers() if _handler_type_name(h) == "ExecutorFailed")
    src = ast.unparse(handler)
    assert "_finish_job" in src and "JobStatus.failed" in src
    assert "terminal_reason" in src and "model_served" in src
    assert "_maybe_escalate" not in src


def test_main_terminal_values_stamp_provider_columns_only_when_known():
    from src.runner import main as runner_main
    from src.models import JobStatus

    base = runner_main._terminal_values(JobStatus.completed, result={"summary": "s"}, error=None)
    assert base["status"] == "completed" and base["result"] == {"summary": "s"}
    assert "resolved_provider" not in base and "terminal_reason" not in base \
        and "model_served" not in base
    full = runner_main._terminal_values(
        JobStatus.failed, result=None, error="x", provider="codex",
        terminal_reason="rate_limited", model_served="gpt-6-luna-2026-10")
    assert full["resolved_provider"] == "codex"
    assert full["terminal_reason"] == "rate_limited"
    assert full["model_served"] == "gpt-6-luna-2026-10"


def test_main_completed_path_stamps_from_the_result():
    tree = ast.parse((REPO / "src" / "runner" / "main.py").read_text())
    process_job = next(n for n in ast.walk(tree)
                       if isinstance(n, ast.AsyncFunctionDef) and n.name == "_process_job")
    src = ast.unparse(process_job)
    assert "JobStatus.completed, result=result" in src
    assert 'result.get("terminal_reason")' in src or "result.get('terminal_reason')" in src
    assert 'result.get("model_served")' in src or "result.get('model_served')" in src
    assert 'result.get("provider")' in src or "result.get('provider')" in src


def test_main_provider_refused_stamps_the_provider():
    handler = next(
        h for h in ast.walk(ast.parse((REPO / "src" / "runner" / "main.py").read_text()))
        if isinstance(h, ast.ExceptHandler) and _handler_type_name(h) == "ProviderRefused")
    src = ast.unparse(handler)
    assert "provider=exc.provider" in src
    assert "provider_refused" in src


def test_audit_log_docstring_lists_the_new_kind():
    doc = (REPO / "src" / "audit_log.py").read_text()
    assert "provider_selected" in doc


# ── 7. Review round 1: no Anthropic escalation off a non-Anthropic lane ────
#
# (code-review T4, 2026-10-21, major) Main's `wait_for` deadline starts before
# skill resolution and the clone, so it always wins over the executor's own
# `timeout_s` when the two are equal; the resulting `asyncio.TimeoutError`
# (and any pre-process `CodexNotFound`/`ValueError`) fell into the generic
# branches of `_process_job`, which escalate onto the skill's Anthropic
# `on_failure` model — the vendor switch note (4) of T4 forbids.


def test_executor_timeout_is_strictly_below_the_session_ceiling():
    # The executor's own deadline sits under main's by a fixed margin so its
    # `timeout` terminal reason is reachable; never below the floor.
    for ceiling in (60, 600, 1800, session.SESSION_TIMEOUT_CAP_SECONDS):
        own = session.executor_timeout_s(ceiling)
        assert 0 < own < ceiling
        assert ceiling - own >= session.EXECUTOR_TIMEOUT_MARGIN_S or own == session.EXECUTOR_TIMEOUT_FLOOR_S
    assert session.executor_timeout_s(60) >= session.EXECUTOR_TIMEOUT_FLOOR_S


async def test_run_session_executor_gets_a_timeout_under_mains_ceiling(harness):
    h = harness
    job = _job(payload={"model": "codex/gpt-6-luna", "session_timeout_seconds": 900})
    await session.run_session(job)
    ceiling = session.resolve_session_timeout(job.payload, settings.session_timeout_seconds)
    assert ceiling == 900
    # T5 review round 1: the gate's allowance (reviewer ceiling + publish
    # margin) is carved out of the executor's budget on this lane.
    own = h.executor.calls[0]["timeout_s"]
    assert own == session.executor_timeout_s(900, reserve_s=session.gate_reserve_s()) < 900
    assert own + session.gate_reserve_s() + session.EXECUTOR_TIMEOUT_MARGIN_S <= 900


@pytest.mark.parametrize("exc", [
    CodexNotFound("no usable codex binary"),
    ValueError("sandbox 'danger-full-access' not allowed"),
])
async def test_run_session_pre_process_executor_errors_are_executor_failed(harness, exc):
    h = harness

    async def boom(job, **kw):
        h.executor.calls.append({"job": job, **kw})
        raise exc

    h.executor.run = boom
    job = _job()
    with pytest.raises(session.ExecutorFailed) as ei:
        await session.run_session(job)
    failed = ei.value
    assert (failed.provider, failed.model_id, failed.terminal_reason) == ("codex", "gpt-6-luna", "api_error")
    assert failed.model_served is None
    assert str(exc) in str(failed)
    assert "job_completed" not in _kinds(job.id)
    assert h.synced == [] and h.cleaned == [(h.created[0], True)]


def test_main_non_anthropic_lane_is_a_pure_read_of_the_stamp():
    from src.runner import main as runner_main
    assert runner_main._non_anthropic_lane(SimpleNamespace(resolved_provider=None)) is None
    assert runner_main._non_anthropic_lane(SimpleNamespace(resolved_provider="anthropic")) is None
    assert runner_main._non_anthropic_lane(SimpleNamespace()) is None
    assert runner_main._non_anthropic_lane(SimpleNamespace(resolved_provider="codex")) == "codex"


class _MainHarness:
    """`main._process_job` with every collaborator faked: the DB fetch returns
    a queued job, the session raises what the test says, and the terminal
    stamp / escalation / task DM are recorded instead of executed."""

    def __init__(self, job, provider_after_session: str | None):
        self.job = job
        self.provider_after_session = provider_after_session
        self.finished: list[dict] = []
        self.escalated: list = []
        self.notified: list = []

    # async_session() context manager
    def __call__(self):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, model, job_id):
        return self.job

    async def commit(self):
        pass


@pytest.fixture
def main_harness(tmp_path, monkeypatch):
    from src.runner import main as runner_main
    monkeypatch.setattr(settings, "server_root", tmp_path / "root")
    (tmp_path / "root").mkdir()

    def build(exc: BaseException, provider: str | None):
        job = _job(status="queued", started_at=None, resolved_skill="demo",
                   resolved_provider=None, error_message=None, payload={})
        h = _MainHarness(job, provider)

        async def fake_run_session(j):
            raise exc

        async def fake_preflight(j, log):
            return None

        async def fake_finish(job_id, status, **kw):
            h.finished.append({"job_id": job_id, "status": status, **kw})

        async def fake_refetch(job_id, fallback, log):
            fallback.resolved_provider = provider
            return fallback

        async def fake_escalate(j):
            h.escalated.append(j)

        async def fake_notify(task_id, kind, **fields):
            h.notified.append((task_id, kind, fields))

        monkeypatch.setattr(runner_main, "async_session", h)
        monkeypatch.setattr(runner_main, "_preflight_check", fake_preflight)
        monkeypatch.setattr(session, "run_session", fake_run_session)
        monkeypatch.setattr(runner_main, "_finish_job", fake_finish)
        monkeypatch.setattr(runner_main, "_refetch_job", fake_refetch)
        monkeypatch.setattr(runner_main, "_maybe_escalate", fake_escalate)
        monkeypatch.setattr(runner_main, "_notify_task", fake_notify)
        monkeypatch.setattr(runner_main, "_JOB_FETCH_DELAYS", (0.0,))
        return h

    return build


@pytest.mark.parametrize("exc, terminal_reason, category", [
    (asyncio.TimeoutError(), "timeout", "timeout"),
    # B3: the generic handler types every failure through
    # `terminal_reason_for_exception` (one reason per handler, both lanes);
    # a bare infrastructure RuntimeError is `error`, no longer the blanket
    # `api_error`.
    (RuntimeError("clone exploded"), "error", None),
])
async def test_main_non_anthropic_failures_are_terminal_never_escalated(
        main_harness, exc, terminal_reason, category):
    from src.models import JobStatus
    from src.runner import main as runner_main
    h = main_harness(exc, "codex")
    await runner_main._process_job(h.job.id)

    assert h.escalated == []                       # never re-run on Anthropic
    assert len(h.finished) == 1
    fin = h.finished[0]
    assert fin["status"] is JobStatus.failed
    assert fin["provider"] == "codex"
    assert fin["terminal_reason"] == terminal_reason
    kinds = _kinds(h.job.id)
    assert kinds.count("job_failed") == 1
    failed = _event(h.job.id, "job_failed")
    if category:
        assert failed["error_category"] == category   # existing shape kept (C14)
    note = _event(h.job.id, "note")
    assert "codex" in note["text"] and "escalat" in note["text"]


async def test_main_anthropic_timeout_still_escalates(main_harness):
    # Control: the Anthropic lane keeps the 2026-08-07 contract
    # (tests/test_timeout_escalation.py) — a timeout escalates.
    from src.runner import main as runner_main
    h = main_harness(asyncio.TimeoutError(), "anthropic")
    await runner_main._process_job(h.job.id)
    assert len(h.escalated) == 1
    # A2: the Anthropic timeout site now stamps the typed reason too; the
    # provider stays unstamped (the session wrote it, not main).
    assert "provider" not in h.finished[0] and h.finished[0]["terminal_reason"] == "timeout"
    assert "note" not in _kinds(h.job.id)


async def test_main_unstamped_provider_still_escalates(main_harness):
    # A job that died before the session stamped `resolved_provider` is
    # indistinguishable from an Anthropic one — the old behaviour holds.
    from src.runner import main as runner_main
    h = main_harness(RuntimeError("died early"), None)
    await runner_main._process_job(h.job.id)
    assert len(h.escalated) == 1
