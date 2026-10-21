"""
Cross-vendor writer slice T5 — pre-push Anthropic review gate for
non-Anthropic lanes (`docs/superpowers/plans/2026-10-21-cross-vendor-writer-
slice.md` §5 T5; old spec §5.3 belt 3b, INV-21(c)).

Pure/fixture style: no network, no live SDK, no `codex` process. Real git
in temp repos for the diff and publish helpers (the pattern of
`tests/test_workspaces.py`); `run_code_review` is a spy in every
`run_session` test.

Covered:
1. `review.diff_for_gate(cwd, base_sha)` — committed + staged + unstaged +
   untracked; empty on a clean clone; raises (fail closed) on a non-repo
   or an unknown base.
2. `workspaces.publish_workspace(ws, …)` — the runner commits with the
   provenance trailers and pushes; a self-committed job gets a provenance
   commit; the canonical ff-syncs afterwards.
3. `run_session`: the gate runs iff provider ≠ anthropic; each outcome;
   timeout counts as `changes_requested`; empty diff → no gate, no commit,
   job completes; `sync_canonical` never called on a non-LGTM (spy); no
   settings switch can disable the gate.
4. `main._process_job`: `ReviewBlocked` is terminal (`error_category=
   review_blocked`, `review_outcome` stamped, failed card names the
   verdict, never escalated); `_maybe_review` skips the non-Anthropic lane
   with `reason=pre_push_gate` (the gate is the review of record).
"""

from __future__ import annotations

import ast
import asyncio
import subprocess
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

from src import audit_log
from src.config import settings
from src.registry import models as reg
from src.registry.skills import SkillConfig
from src.runner import review, session, workspaces
from src.runner.executors.codex_cli import ExecResult
from src.runner.review import ReviewOutcome

REPO = Path(__file__).resolve().parents[1]


# ── git helpers (temp repos) ───────────────────────────────────────────────


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=str(cwd), capture_output=True, text=True, check=False,
    )


@pytest.fixture
def canonical_repo(tmp_path: Path) -> Path:
    remote = tmp_path / "remote.git"
    remote.mkdir()
    _git(["init", "--bare", "--initial-branch=main"], remote)
    canonical = tmp_path / "canonical"
    _git(["clone", str(remote), str(canonical)], tmp_path)
    (canonical / "README.md").write_text("v1\n")
    (canonical / "keep.py").write_text("x = 1\n")
    _git(["add", "-A"], canonical)
    _git(["commit", "-m", "v1"], canonical)
    _git(["push", "origin", "main"], canonical)
    return canonical


@pytest.fixture
def clone(canonical_repo: Path, tmp_path: Path) -> workspaces.Workspace:
    return workspaces.create_workspace("job00000001", canonical_repo, tmp_path / "ws")


# ── 1. diff_for_gate ──────────────────────────────────────────────────────


class TestDiffForGate:
    def test_clean_clone_is_empty(self, clone):
        base = workspaces.head_sha(clone.path)
        assert base and len(base) == 40
        assert review.diff_for_gate(clone.path, base) == ""

    def test_covers_committed_staged_unstaged_and_untracked(self, clone):
        base = workspaces.head_sha(clone.path)
        # committed by the job itself
        (clone.path / "keep.py").write_text("x = 2\n")
        _git(["commit", "-am", "job commit"], clone.path)
        # staged
        (clone.path / "staged.py").write_text("s = 1\n")
        _git(["add", "staged.py"], clone.path)
        # unstaged edit of a tracked file
        (clone.path / "README.md").write_text("v2\n")
        # untracked
        (clone.path / "new.txt").write_text("hello\n")
        diff = review.diff_for_gate(clone.path, base)
        for marker in ("-x = 1", "+x = 2", "+s = 1", "-v1", "+v2", "+hello"):
            assert marker in diff, marker
        assert "new.txt" in diff and "staged.py" in diff

    def test_gitignored_files_are_not_in_the_diff(self, clone):
        base = workspaces.head_sha(clone.path)
        (clone.path / ".gitignore").write_text("*.secret\n")
        (clone.path / "k.secret").write_text("TOKEN\n")
        diff = review.diff_for_gate(clone.path, base)
        assert "TOKEN" not in diff and ".gitignore" in diff

    def test_non_repo_raises_fail_closed(self, tmp_path):
        with pytest.raises(RuntimeError):
            review.diff_for_gate(tmp_path, "0" * 40)

    def test_unknown_base_raises(self, clone):
        with pytest.raises(RuntimeError):
            review.diff_for_gate(clone.path, None)
        with pytest.raises(RuntimeError):
            review.diff_for_gate(clone.path, "deadbeef" * 5)


def test_count_findings_is_a_list_item_heuristic():
    assert review.count_findings("") == 0
    assert review.count_findings("LGTM\n\nReview: fine") == 0
    text = ("CHANGES\n\nReview: two things\n- missing error handler in x.py:12\n"
            "* unused import\n1. no test for the empty case\n  2) also this\n"
            "not a bullet - inline dash")
    assert review.count_findings(text) == 4


def test_reviewer_constants_match_run_code_review():
    # The trailer names the reviewer; it must be the model run_code_review
    # actually pins (never the reviewed skill's choice).
    src = (REPO / "src" / "runner" / "review.py").read_text()
    assert review.REVIEWER_PROVIDER == "anthropic"
    assert review.REVIEWER_MODEL.startswith("claude-")
    assert "model=REVIEWER_MODEL" in src
    assert review.GATE_TIMEOUT_SECONDS == 600


# ── 2. publish_workspace ───────────────────────────────────────────────────


def test_provenance_trailers_format():
    job_id = uuid.uuid4()
    lines = workspaces.provenance_trailers(
        provider="codex", model_id="gpt-6-luna", job_id=job_id,
        reviewer="anthropic/claude-opus-4-7")
    assert lines == [
        "Executor: codex/gpt-6-luna",
        f"Job: {job_id}",
        "Reviewed-By: anthropic/claude-opus-4-7",
    ]


class TestPublishWorkspace:
    def _log_body(self, path: Path) -> str:
        return _git(["log", "-1", "--format=%B"], path).stdout

    def test_runner_commits_with_trailers_pushes_and_canonical_syncs(self, clone, canonical_repo):
        base = workspaces.head_sha(clone.path)
        (clone.path / "keep.py").write_text("x = 2\n")
        (clone.path / "new.txt").write_text("hello\n")
        trailers = workspaces.provenance_trailers(
            provider="codex", model_id="gpt-6-luna", job_id="abc", reviewer="anthropic/m")
        ok, detail, sha = workspaces.publish_workspace(
            clone, base_sha=base, message="demo: fix the flaky test", trailers=trailers)
        assert ok, detail
        assert sha and sha != base and sha == workspaces.head_sha(clone.path)
        body = self._log_body(clone.path)
        assert body.startswith("demo: fix the flaky test")
        assert "\n\nExecutor: codex/gpt-6-luna\nJob: abc\nReviewed-By: anthropic/m" in body
        # Untracked files were staged by the runner, the clone is clean after.
        assert _git(["status", "--porcelain"], clone.path).stdout == ""
        # Pushed: the remote has it, and the canonical ff-syncs as today.
        remote_head = _git(["rev-parse", "main"], canonical_repo.parent / "remote.git").stdout.strip()
        assert remote_head == sha
        synced, msg = workspaces.sync_canonical(clone)
        assert synced, msg
        assert workspaces.head_sha(canonical_repo) == sha
        assert (canonical_repo / "new.txt").read_text() == "hello\n"

    def test_self_committed_job_gets_a_provenance_commit(self, clone):
        base = workspaces.head_sha(clone.path)
        (clone.path / "keep.py").write_text("x = 3\n")
        _git(["commit", "-am", "codex did this itself"], clone.path)
        own = workspaces.head_sha(clone.path)
        ok, detail, sha = workspaces.publish_workspace(
            clone, base_sha=base, message="demo: task", trailers=["Job: j1"])
        assert ok, detail
        assert sha != own                      # never amended …
        assert "Job: j1" in self._log_body(clone.path)
        parents = _git(["log", "--format=%H", f"{base}..HEAD"], clone.path).stdout.split()
        assert parents == [sha, own]           # … a provenance commit on top

    def test_nothing_to_publish_is_reported_not_committed(self, clone):
        base = workspaces.head_sha(clone.path)
        ok, detail, sha = workspaces.publish_workspace(
            clone, base_sha=base, message="m", trailers=["Job: j"])
        assert ok is False and "nothing" in detail and sha is None
        assert workspaces.head_sha(clone.path) == base

    def test_push_rejection_is_reported_not_forced(self, clone, canonical_repo):
        # The remote moved on (another writer): one push attempt, no rebase,
        # no force — the reviewed commit stays in the kept clone.
        (canonical_repo / "README.md").write_text("someone else\n")
        _git(["commit", "-am", "moved"], canonical_repo)
        _git(["push", "origin", "main"], canonical_repo)
        base = workspaces.head_sha(clone.path)
        (clone.path / "keep.py").write_text("x = 9\n")
        ok, detail, sha = workspaces.publish_workspace(
            clone, base_sha=base, message="m", trailers=["Job: j"])
        assert ok is False and "push" in detail.lower()
        assert sha and workspaces.head_sha(clone.path) == sha   # commit kept locally
        remote_head = _git(["rev-parse", "main"], canonical_repo.parent / "remote.git").stdout.strip()
        assert remote_head != sha

    def test_no_remote_canonical_publishes_locally_and_syncs_from_workspace(self, tmp_path):
        canonical = tmp_path / "local-only"
        canonical.mkdir()
        _git(["init", "--initial-branch=main"], canonical)
        (canonical / "a.txt").write_text("1\n")
        _git(["add", "-A"], canonical)
        _git(["commit", "-m", "v1"], canonical)
        ws = workspaces.create_workspace("job00000002", canonical, tmp_path / "ws")
        assert ws.pushes_to_origin is False
        base = workspaces.head_sha(ws.path)
        (ws.path / "a.txt").write_text("2\n")
        ok, detail, sha = workspaces.publish_workspace(
            ws, base_sha=base, message="m", trailers=["Job: j"])
        assert ok, detail
        synced, msg = workspaces.sync_canonical(ws)
        assert synced, msg
        assert workspaces.head_sha(canonical) == sha


# ── 3. run_session with the gate ──────────────────────────────────────────


CODEX = reg.ModelRef("codex", "gpt-6-luna")


def _skill(name: str = "demo", **kw) -> SkillConfig:
    kw.setdefault("body", "Do the thing.")
    kw.setdefault("isolation", "workspace")
    return SkillConfig(name=name, **kw)


class _FakeExecutor:
    def __init__(self):
        self.calls: list[dict] = []
        self.result = ExecResult(
            final_text="Did the work.\nTASK_COMPLETE: fixed it",
            usage={"input_tokens": 10, "output_tokens": 5},
            terminal_reason="ok", model_served="gpt-6-luna-2026-10",
            thread_id="thr_1", cli_version="0.162.0", exit_code=0, error=None)

    async def run(self, job, **kw):
        self.calls.append({"job": job, **kw})
        return self.result

    async def interrupt(self, job_id):
        return True


class _FakeDB:
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


def _job(**kw) -> SimpleNamespace:
    base = dict(id=uuid.uuid4(), kind="demo", description="fix the flaky test in pickem",
                payload={"model": "codex/gpt-6-luna"}, task_id=None, parent_job_id=None,
                project_id=None, created_by="telegram:1")
    base.update(kw)
    return SimpleNamespace(**base)


@pytest.fixture
def harness(tmp_path, monkeypatch):
    """`run_session` with every collaborator faked. The gate's own pieces —
    `diff_for_gate`, `run_code_review`, `publish_workspace` — are spies the
    test tunes: `h.diff` (the diff the gate sees), `h.outcome` (what the
    reviewer returns, or an exception to raise), `h.publish_ok`."""
    monkeypatch.setattr(settings, "server_root", tmp_path / "root")
    monkeypatch.setattr(settings, "router_providers_enabled", "anthropic,codex")
    monkeypatch.setattr(settings, "router_code_server_providers", "anthropic")
    monkeypatch.setattr(settings, "codex_sandbox_default", "workspace-write")
    monkeypatch.setattr(settings, "default_model", "claude-sonnet-4-6")
    (tmp_path / "root").mkdir()

    canonical = tmp_path / "canonical"
    canonical.mkdir()
    (canonical / ".git").mkdir()          # looks like a git checkout to the lane check
    h = SimpleNamespace(
        skill=_skill(), skill_name="demo", deliv=None, canonical=canonical, slug="demo",
        executor=_FakeExecutor(), db=_FakeDB(),
        created=[], synced=[], cleaned=[], sdk_calls=[],
        diff="--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n-1\n+2\n",
        outcome=ReviewOutcome.lgtm, review_calls=[], publish_calls=[],
        publish_ok=True, review_text="LGTM\n\nReview: fine",
        base_sha="b" * 40,
    )

    async def fake_resolve_skill(job):
        return h.skill_name, h.skill

    async def fake_resolve_project(job, skill_name=None):
        # A PROJECT canonical with a slug: the D-A canonical-path rule
        # (review round 1) refuses slug-less / server-root canonicals.
        return h.canonical, h.deliv, False, h.slug

    def fake_create_workspace(job_id, canon, base_dir):
        ws_path = tmp_path / "ws" / job_id
        ws_path.mkdir(parents=True)
        ws = workspaces.Workspace(path=ws_path, canonical=canon, pushes_to_origin=True)
        h.created.append(ws)
        return ws

    def fake_head_sha(path):
        return h.base_sha

    def fake_sync(ws):
        h.synced.append(ws)
        return True, "fake sync"

    def fake_cleanup(ws, *, keep=False):
        h.cleaned.append((ws, keep))

    async def fake_run_in_process(job_id, prompt, options):
        h.sdk_calls.append((job_id, prompt, options))
        return "SDK did it.\nTASK_COMPLETE: via the SDK", {"input_tokens": 3}

    def fake_diff(cwd, base_sha):
        h.diff_calls = getattr(h, "diff_calls", []) + [(cwd, base_sha)]
        return h.diff

    async def fake_review(parent_job_id, diff, cwd):
        h.review_calls.append((parent_job_id, diff, cwd))
        if isinstance(h.outcome, BaseException):
            raise h.outcome
        if h.outcome == "hang":
            await asyncio.sleep(3600)
        audit_log.append(parent_job_id, "code_review_done",
                         outcome=h.outcome.value, review_text=h.review_text)
        return h.outcome

    def fake_publish(ws, *, base_sha, message, trailers):
        h.publish_calls.append(dict(ws=ws, base_sha=base_sha, message=message, trailers=trailers))
        if h.publish_ok:
            return True, "committed and pushed", "c" * 40
        return False, "push rejected (non-fast-forward)", "c" * 40

    monkeypatch.setattr(session, "_resolve_skill", fake_resolve_skill)
    monkeypatch.setattr(session, "_resolve_project", fake_resolve_project)
    monkeypatch.setattr(session.workspaces, "create_workspace", fake_create_workspace)
    monkeypatch.setattr(session.workspaces, "head_sha", fake_head_sha)
    monkeypatch.setattr(session.workspaces, "sync_canonical", fake_sync)
    monkeypatch.setattr(session.workspaces, "cleanup_workspace", fake_cleanup)
    monkeypatch.setattr(session.workspaces, "publish_workspace", fake_publish)
    monkeypatch.setattr(session.review, "diff_for_gate", fake_diff)
    monkeypatch.setattr(session.review, "run_code_review", fake_review)
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


async def test_gate_runs_only_for_non_anthropic_lanes(harness):
    h = harness
    h.skill = _skill(model="claude-opus-5")
    job = _job(payload={"model": "sonnet"})
    result = await session.run_session(job)
    assert h.sdk_calls and not h.executor.calls
    assert h.review_calls == [] and h.publish_calls == []
    assert h.synced == [h.created[0]] and h.cleaned == [(h.created[0], False)]
    assert "merge_gate_verdict" not in _kinds(job.id)
    assert result["review_outcome"] is None             # uniform shape, like model_served
    assert _event(job.id, "workspace_created")["base_sha"] is None   # no base recorded


async def test_lgtm_commits_with_trailers_then_syncs(harness):
    h = harness
    job = _job()
    result = await session.run_session(job)

    # The gate saw the clone's diff against the pre-job base.
    assert h.review_calls == [(str(job.id), h.diff, h.created[0].path)]
    assert h.diff_calls == [(h.created[0].path, h.base_sha)]
    # The runner committed (trailers of record) and the canonical synced.
    assert len(h.publish_calls) == 1
    pub = h.publish_calls[0]
    assert pub["ws"] is h.created[0] and pub["base_sha"] == h.base_sha
    assert pub["message"].startswith("demo: fix the flaky test in pickem")
    assert pub["trailers"] == [
        "Executor: codex/gpt-6-luna",
        f"Job: {job.id}",
        f"Reviewed-By: anthropic/{review.REVIEWER_MODEL}",
    ]
    assert h.synced == [h.created[0]]
    assert h.cleaned == [(h.created[0], False)]          # clone removed like an Anthropic success

    kinds = _kinds(job.id)
    assert kinds.index("merge_gate_verdict") < kinds.index("workspace_published") \
        < kinds.index("job_completed") < kinds.index("workspace_synced")
    verdict = _event(job.id, "merge_gate_verdict")
    assert verdict["belt"] == "pre_push"
    assert verdict["reviewer_provider"] == "anthropic"
    assert verdict["reviewer_model"] == review.REVIEWER_MODEL
    assert verdict["verdict"] == ReviewOutcome.lgtm.value
    assert verdict["findings_n"] == 0
    assert verdict["timed_out"] is False
    assert verdict["diff_chars"] == len(h.diff)
    published = _event(job.id, "workspace_published")
    assert published["ok"] is True and published["commit"] == "c" * 40
    assert result["review_outcome"] == ReviewOutcome.lgtm.value
    assert result["terminal_reason"] == "ok" and result["provider"] == "codex"
    assert "note" not in kinds                           # the T4 "kept for T5" note is gone
    assert _event(job.id, "workspace_created")["base_sha"] == h.base_sha


@pytest.mark.parametrize("outcome", [
    ReviewOutcome.changes_requested, ReviewOutcome.blocker, ReviewOutcome.error,
])
async def test_non_lgtm_blocks_keeps_the_clone_and_never_syncs(harness, outcome):
    h = harness
    h.outcome = outcome
    h.review_text = f"{outcome.value}\n\nReview:\n- thing one\n- thing two"
    job = _job()
    with pytest.raises(session.ReviewBlocked) as ei:
        await session.run_session(job)
    exc = ei.value
    assert isinstance(exc, RuntimeError)
    assert (exc.provider, exc.model_id, exc.verdict) == ("codex", "gpt-6-luna", outcome.value)
    assert exc.findings_n == 2
    assert outcome.value in str(exc)
    assert h.publish_calls == []
    assert h.synced == []                                 # sync_canonical never called
    assert h.cleaned == [(h.created[0], True)]            # clone kept for the owner
    kinds = _kinds(job.id)
    assert "job_completed" not in kinds and "workspace_published" not in kinds
    verdict = _event(job.id, "merge_gate_verdict")
    assert verdict["verdict"] == outcome.value and verdict["findings_n"] == 2
    assert verdict["timed_out"] is False


async def test_reviewer_timeout_counts_as_changes_requested(harness, monkeypatch):
    h = harness
    h.outcome = "hang"
    monkeypatch.setattr(session.review, "GATE_TIMEOUT_SECONDS", 0.01)
    job = _job()
    with pytest.raises(session.ReviewBlocked) as ei:
        await session.run_session(job)
    assert ei.value.verdict == ReviewOutcome.changes_requested.value
    verdict = _event(job.id, "merge_gate_verdict")
    assert verdict["verdict"] == ReviewOutcome.changes_requested.value
    assert verdict["timed_out"] is True
    assert h.publish_calls == [] and h.synced == []
    assert h.cleaned == [(h.created[0], True)]


async def test_reviewer_exception_is_fail_closed(harness):
    # run_code_review catches its own errors and returns `error`; anything
    # that still escapes must not read as a pass.
    h = harness
    h.outcome = RuntimeError("sdk exploded")
    job = _job()
    with pytest.raises(RuntimeError):
        await session.run_session(job)
    assert h.publish_calls == [] and h.synced == []
    assert h.cleaned == [(h.created[0], True)]
    assert "job_completed" not in _kinds(job.id)


async def test_empty_diff_skips_the_gate_and_completes(harness):
    h = harness
    h.diff = ""
    job = _job()
    result = await session.run_session(job)
    assert h.review_calls == [] and h.publish_calls == []
    assert h.synced == []                                 # nothing to sync
    assert h.cleaned == [(h.created[0], False)]           # nothing to keep either
    kinds = _kinds(job.id)
    assert "merge_gate_verdict" not in kinds and "job_completed" in kinds
    skipped = _event(job.id, "merge_gate_skipped")
    assert skipped["belt"] == "pre_push" and skipped["reason"] == "empty_diff"
    assert result["review_outcome"] is None
    assert result["summary"].startswith("Did the work.")


async def test_publish_failure_after_lgtm_fails_the_job_and_keeps_the_clone(harness):
    h = harness
    h.publish_ok = False
    job = _job()
    # Typed (review round 1): main's ExecutorFailed handler stamps
    # `terminal_reason=publish_failed`, so the ledger can tell "approved but
    # the push was rejected" from a vendor `api_error`.
    with pytest.raises(session.ExecutorFailed) as ei:
        await session.run_session(job)
    assert ei.value.terminal_reason == "publish_failed"
    assert (ei.value.provider, ei.value.model_id) == ("codex", "gpt-6-luna")
    assert "publish" in str(ei.value).lower() and "push rejected" in str(ei.value)
    assert not isinstance(ei.value, session.ReviewBlocked)
    assert h.synced == [] and h.cleaned == [(h.created[0], True)]
    published = _event(job.id, "workspace_published")
    assert published["ok"] is False and "push rejected" in published["detail"]
    kinds = _kinds(job.id)
    assert _event(job.id, "merge_gate_verdict")["verdict"] == ReviewOutcome.lgtm.value
    assert "job_completed" not in kinds


async def test_diff_failure_is_fail_closed(harness, monkeypatch):
    # A git error while computing the diff must not look like "empty diff".
    h = harness

    def boom(cwd, base_sha):
        raise RuntimeError("git diff failed")
    monkeypatch.setattr(session.review, "diff_for_gate", boom)
    job = _job()
    with pytest.raises(RuntimeError):
        await session.run_session(job)
    assert h.review_calls == [] and h.publish_calls == [] and h.synced == []
    assert h.cleaned == [(h.created[0], True)]
    assert "job_completed" not in _kinds(job.id)


async def test_non_git_canonical_is_refused_before_the_clone(harness):
    h = harness
    (h.canonical / ".git").rmdir()
    job = _job()
    with pytest.raises(reg.ProviderRefused) as ei:
        await session.run_session(job)
    assert "git" in ei.value.reason
    assert h.created == [] and h.executor.calls == []


async def test_executor_failure_never_reaches_the_gate(harness):
    h = harness
    h.executor.result = ExecResult(
        final_text="", usage={}, terminal_reason="api_error", model_served=None,
        thread_id="t", cli_version="0", exit_code=1, error="boom")
    job = _job()
    with pytest.raises(session.ExecutorFailed):
        await session.run_session(job)
    assert h.review_calls == [] and h.publish_calls == [] and h.synced == []
    assert "merge_gate_verdict" not in _kinds(job.id)


def test_gate_is_a_rule_not_a_switch():
    # Round-1 critical #1: no env var / setting can disable the gate. The
    # gate function reads nothing from `settings`, `run_session` calls it on
    # the provider alone, and no setting even names a gate.
    tree = ast.parse((REPO / "src" / "runner" / "session.py").read_text())
    gate = next(n for n in ast.walk(tree)
                if isinstance(n, ast.AsyncFunctionDef) and n.name == "_pre_push_gate")
    settings_reads = [
        n for n in ast.walk(gate)
        if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)
        and n.value.id == "settings"]
    assert settings_reads == []
    run_session = next(n for n in ast.walk(tree)
                       if isinstance(n, ast.AsyncFunctionDef) and n.name == "run_session")
    assert "_pre_push_gate(" in ast.unparse(run_session)
    fields = type(settings).model_fields
    assert not [k for k in fields if "gate" in k.lower() or "review" in k.lower()]


# ── 4. main: ReviewBlocked terminal; belt 2 skipped on the lane ───────────


class _MainHarness:
    def __init__(self, job, provider_after_session):
        self.job = job
        self.provider_after_session = provider_after_session
        self.finished: list[dict] = []
        self.escalated: list = []
        self.notified: list = []

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

    def build(exc: BaseException, provider: str | None, *, task_id=None):
        job = _job(status="queued", started_at=None, resolved_skill="demo",
                   resolved_provider=None, error_message=None, payload={}, task_id=task_id)
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


async def test_main_review_blocked_is_terminal_and_names_the_verdict(main_harness):
    from src.models import JobStatus
    from src.runner import main as runner_main
    exc = session.ReviewBlocked("codex", "gpt-6-luna", verdict="blocker", findings_n=3)
    h = main_harness(exc, "codex", task_id=uuid.uuid4())
    await runner_main._process_job(h.job.id)

    assert h.escalated == []
    assert len(h.finished) == 1
    fin = h.finished[0]
    assert fin["status"] is JobStatus.failed
    assert fin["provider"] == "codex"
    assert fin["terminal_reason"] == "review_blocked"
    assert fin["review_outcome"] == "blocker"
    assert "blocker" in fin["error"]
    # The done DM names the verdict (not a bare "failed").
    assert "blocker" in fin["done_payload"]["summary"]
    failed = _event(h.job.id, "job_failed")
    assert failed["error_category"] == "review_blocked"
    # The task's failed card names the verdict too.
    assert len(h.notified) == 1
    task_id, kind, fields = h.notified[0]
    assert kind == "failed" and "blocker" in fields["text"] and "3" in fields["text"]


def test_main_review_blocked_handler_precedes_the_generic_ones():
    tree = ast.parse((REPO / "src" / "runner" / "main.py").read_text())
    process_job = next(n for n in ast.walk(tree)
                       if isinstance(n, ast.AsyncFunctionDef) and n.name == "_process_job")
    handlers = None
    for node in ast.walk(process_job):
        if isinstance(node, ast.Try):
            names = [getattr(h.type, "attr", getattr(h.type, "id", "")) for h in node.handlers]
            if "ReviewBlocked" in names:
                handlers = (names, node.handlers)
                break
    assert handlers, "_process_job has no ReviewBlocked handler"
    names, nodes = handlers
    assert names.index("ReviewBlocked") < names.index("Exception")
    src = ast.unparse(nodes[names.index("ReviewBlocked")])
    assert "_maybe_escalate" not in src
    assert "review_blocked" in src and "review_outcome" in src


def test_main_terminal_values_stamp_review_outcome_only_when_known():
    from src.models import JobStatus
    from src.runner import main as runner_main
    base = runner_main._terminal_values(JobStatus.completed, result={"summary": "s"}, error=None)
    assert "review_outcome" not in base
    full = runner_main._terminal_values(
        JobStatus.failed, result=None, error="x", provider="codex",
        terminal_reason="review_blocked", review_outcome="changes_requested")
    assert full["review_outcome"] == "changes_requested"
    assert full["terminal_reason"] == "review_blocked"


def test_main_completed_path_stamps_review_outcome_from_the_result():
    tree = ast.parse((REPO / "src" / "runner" / "main.py").read_text())
    process_job = next(n for n in ast.walk(tree)
                       if isinstance(n, ast.AsyncFunctionDef) and n.name == "_process_job")
    src = ast.unparse(process_job)
    assert "result.get('review_outcome')" in src or 'result.get("review_outcome")' in src


async def test_maybe_review_skips_the_non_anthropic_lane_as_already_reviewed(monkeypatch, tmp_path):
    from src.runner import main as runner_main
    monkeypatch.setattr(settings, "server_root", tmp_path / "root")
    (tmp_path / "root").mkdir()
    calls: list = []

    async def fake_review(*a, **kw):
        calls.append((a, kw))
        return ReviewOutcome.lgtm

    async def fake_resolve_cwd(job, skill):
        raise AssertionError("cwd must not be resolved — the lane is skipped first")

    monkeypatch.setattr(runner_main, "run_code_review", fake_review)
    monkeypatch.setattr(runner_main, "load_skill",
                        lambda name: _skill(name, post_review={"trigger": "always"}))
    monkeypatch.setattr(runner_main.session_mod, "_resolve_cwd", fake_resolve_cwd)
    job = _job(resolved_skill="demo", resolved_provider="codex", started_at=None)
    await runner_main._maybe_review(job, {"review_outcome": "LGTM"})
    assert calls == []
    skipped = _event(job.id, "post_review_skipped")
    assert skipped["reason"] == "pre_push_gate" and skipped["verdict"] == "LGTM"


async def test_maybe_review_still_runs_for_anthropic(monkeypatch, tmp_path):
    # Control: the Anthropic path reaches the cwd/stale-head logic as before.
    from src.runner import main as runner_main
    monkeypatch.setattr(settings, "server_root", tmp_path / "root")
    (tmp_path / "root").mkdir()
    reached: list = []

    async def fake_resolve_cwd(job, skill):
        reached.append(skill)
        return tmp_path                          # not a repo → no_diff skip

    monkeypatch.setattr(runner_main, "load_skill",
                        lambda name: _skill(name, post_review={"trigger": "always"}))
    monkeypatch.setattr(runner_main.session_mod, "_resolve_cwd", fake_resolve_cwd)
    job = _job(resolved_skill="demo", resolved_provider="anthropic", started_at=None)
    await runner_main._maybe_review(job, {})
    assert reached == ["demo"]
    assert _event(job.id, "post_review_skipped")["reason"] == "no_diff"


def test_audit_log_docstring_lists_the_new_kinds():
    doc = (REPO / "src" / "audit_log.py").read_text()
    for kind in ("merge_gate_verdict", "merge_gate_skipped", "workspace_published"):
        assert kind in doc, kind


# ── 5. Review round 1 (2026-10-21) ────────────────────────────────────────
# (a) the reviewer runs in SDK isolation mode (no settings/hooks/CLAUDE.md
#     from the reviewed clone); (b) a hardcoded path deny list refuses the
#     diff BEFORE a reviewer is spent; (c) D-A by canonical PATH — a
#     slug-less / server-root canonical is refused unless the provider is in
#     ROUTER_CODE_SERVER_PROVIDERS; (d) the gate's allowance is carved out of
#     the executor's budget; (e) empty description; (f) typed publish failure.


class TestGatePathDenials:
    DIFF = (
        "diff --git a/src/x.py b/src/x.py\n--- a/src/x.py\n+++ b/src/x.py\n@@ -1 +1 @@\n-1\n+2\n"
        "diff --git a/.claude/settings.json b/.claude/settings.json\n"
        "--- /dev/null\n+++ b/.claude/settings.json\n@@ -0,0 +1 @@\n+{\"hooks\": {}}\n"
        "diff --git a/docs/a.md b/docs/AGENTS.md\nsimilarity index 100%\n"
        "rename from docs/a.md\nrename to docs/AGENTS.md\n"
        "diff --git a//dev/null b/new.txt\n--- /dev/null\n+++ b/new.txt\n@@ -0,0 +1 @@\n+hello\n"
    )

    def test_paths_are_collected_from_every_header_form(self):
        paths = review.gate_diff_paths(self.DIFF)
        assert paths == ["src/x.py", ".claude/settings.json", "docs/a.md", "docs/AGENTS.md", "new.txt"]

    @pytest.mark.parametrize("path", [
        ".claude/settings.json", ".claude/settings.local.json", ".claude", "./.claude/x",
        ".codex/config.toml", ".git/hooks/pre-commit", ".githooks/pre-push",
        ".github/workflows/ci.yml", ".gitmodules", ".gitattributes", ".gitconfig",
        ".mcp.json", "AGENTS.md", "docs/AGENTS.md", "CLAUDE.md", "projects/x/CLAUDE.md",
    ])
    def test_denied(self, path):
        assert review.gate_path_denied(path), path

    @pytest.mark.parametrize("path", [
        "src/x.py", ".gitignore", "docs/.claude-notes.md", "research/claude.md",
        "agents.md", "src/.github.py", "x/.gitmodules", "README.md", "",
    ])
    def test_allowed(self, path):
        assert not review.gate_path_denied(path), path

    def test_denials_are_deny_first_and_a_rename_counts_both_sides(self):
        assert review.gate_path_denials(self.DIFF) == [".claude/settings.json", "docs/AGENTS.md"]
        assert review.gate_path_denials("--- a/src/x.py\n+++ b/src/x.py\n") == []
        assert review.gate_path_denials("") == []

    def test_deny_list_is_hardcoded_in_review(self):
        for name in (".claude", ".codex", ".git", ".githooks", ".github"):
            assert name in review.GATE_DENIED_DIRS
        assert "AGENTS.md" in review.GATE_DENIED_BASENAMES


async def test_denied_path_in_diff_is_refused_before_any_reviewer_runs(harness):
    h = harness
    h.diff = ("--- a/src/x.py\n+++ b/src/x.py\n@@ -1 +1 @@\n-1\n+2\n"
              "--- /dev/null\n+++ b/.claude/settings.json\n@@ -0,0 +1 @@\n+{\"hooks\": {}}\n")
    job = _job()
    with pytest.raises(session.ReviewBlocked) as ei:
        await session.run_session(job)
    exc = ei.value
    assert exc.denied_paths == [".claude/settings.json"]
    assert exc.verdict == ReviewOutcome.blocker.value
    assert ".claude/settings.json" in str(exc)
    # Fail closed WITHOUT spending a reviewer session; nothing published.
    assert h.review_calls == [] and h.publish_calls == [] and h.synced == []
    assert h.cleaned == [(h.created[0], True)]
    kinds = _kinds(job.id)
    assert "merge_gate_verdict" not in kinds and "code_review_done" not in kinds
    assert "job_completed" not in kinds and "workspace_published" not in kinds
    refused = _event(job.id, "merge_gate_refused")
    assert refused["belt"] == "pre_push" and refused["reason"] == "denied_path"
    assert refused["paths"] == [".claude/settings.json"]


async def test_run_code_review_runs_in_sdk_isolation_mode(monkeypatch, tmp_path):
    # The ClaudeAgentOptions handed to `query` must carry
    # `setting_sources=[]`: with `None` the SDK loads the reviewed
    # checkout's .claude/settings*.json (hooks run as the owner) and
    # CLAUDE.md — exactly what a Codex clone can plant.
    monkeypatch.setattr(settings, "server_root", tmp_path / "root")
    (tmp_path / "root").mkdir()
    captured: list = []

    async def fake_query(*, prompt, options):
        captured.append((prompt, options))
        if False:   # pragma: no cover — an async generator that yields nothing
            yield None

    monkeypatch.setattr(review, "query", fake_query)
    outcome = await review.run_code_review("job-iso", "--- a/x\n+++ b/x\n", tmp_path)
    assert outcome is ReviewOutcome.changes_requested      # no output → conservative
    assert len(captured) == 1
    opts = captured[0][1]
    assert opts.setting_sources == []
    assert opts.permission_mode == "plan" and opts.allowed_tools == ["Read", "Glob", "Grep"]
    assert opts.cwd == str(tmp_path)
    src = (REPO / "src" / "runner" / "review.py").read_text()
    assert "setting_sources=[]" in src


async def test_main_review_blocked_card_names_denied_paths(main_harness):
    from src.models import JobStatus
    from src.runner import main as runner_main
    exc = session.ReviewBlocked("codex", "gpt-6-luna", verdict="blocker", findings_n=1,
                                denied_paths=[".claude/settings.json"])
    h = main_harness(exc, "codex", task_id=uuid.uuid4())
    await runner_main._process_job(h.job.id)
    assert h.escalated == []
    fin = h.finished[0]
    assert fin["status"] is JobStatus.failed and fin["terminal_reason"] == "review_blocked"
    assert fin["review_outcome"] == "blocker"
    assert ".claude/settings.json" in fin["done_payload"]["summary"]
    assert "denied" in h.notified[0][2]["text"]


# (c) D-A by canonical path.


def _canon(path, *, slug="p", provider="codex", csp=frozenset({"anthropic"}), root, projects=None):
    return session.canonical_refusal(
        path, slug=slug, provider=provider, code_server_providers=csp,
        server_root=root, projects_dir=projects or (root / "projects"))


def test_canonical_refusal_rules(tmp_path):
    root = tmp_path / "root"
    (root / "projects" / "p").mkdir(parents=True)
    (root / "skills").mkdir()
    dev = tmp_path / "repos" / "atlas"
    dev.mkdir(parents=True)
    # Anthropic is never refused; a code-server-listed provider is never refused.
    assert _canon(root, slug=None, provider="anthropic", root=root) is None
    assert _canon(root, slug=None, csp=frozenset({"anthropic", "codex"}), root=root) is None
    # Slug-less → server root → refused, naming D-A.
    why = _canon(root, slug=None, root=root)
    assert why and "D-A" in why and "slug" in why
    # A slug whose canonical still resolves to the server root (missing dir).
    why = _canon(root, slug="ghost", root=root)
    assert why and "server root" in why and "D-A" in why
    # Inside the root but not a project directory.
    why = _canon(root / "skills", root=root)
    assert why and "not a project" in why
    # A project directory, and a dev-repo clone elsewhere on disk, pass.
    assert _canon(root / "projects" / "p", root=root) is None
    assert _canon(dev, slug="atlas", root=root) is None
    # Case-folded providers from settings are honoured.
    assert _canon(root, slug=None, csp=session.code_server_providers() | {"codex"}, root=root) is None


async def test_slugless_codex_job_is_refused_before_the_clone(harness, monkeypatch):
    # `_resolve_project` returns the server root for a slug-less job: with
    # T5's publish path that would push a Codex diff to THIS repo's main.
    h = harness
    h.slug = None
    h.canonical = settings.server_root
    (settings.server_root / ".git").mkdir()        # git-ness is NOT the question
    job = _job()
    with pytest.raises(reg.ProviderRefused) as ei:
        await session.run_session(job)
    assert "D-A" in ei.value.reason and "ROUTER_CODE_SERVER_PROVIDERS" in ei.value.reason
    assert ei.value.provider == "codex"
    assert h.created == [] and h.executor.calls == []
    assert h.review_calls == [] and h.publish_calls == []
    assert "workspace_created" not in _kinds(job.id)

    # The owner's flip (D-A on) lets the same job through.
    monkeypatch.setattr(settings, "router_code_server_providers", "anthropic,codex")
    job2 = _job()
    result = await session.run_session(job2)
    assert result["provider"] == "codex" and len(h.created) == 1
    assert len(h.executor.calls) == 1 and len(h.publish_calls) == 1


async def test_project_canonical_outside_projects_dir_but_inside_root_is_refused(harness):
    h = harness
    h.slug = "demo"
    h.canonical = settings.server_root / "skills"
    h.canonical.mkdir(parents=True)
    (h.canonical / ".git").mkdir()
    with pytest.raises(reg.ProviderRefused) as ei:
        await session.run_session(_job())
    assert "not a project" in ei.value.reason
    assert h.created == []


async def test_anthropic_slugless_job_is_untouched_by_the_canonical_rule(harness):
    h = harness
    h.slug = None
    h.canonical = settings.server_root
    h.skill = _skill(model="claude-opus-5")
    job = _job(payload={"model": "sonnet"})
    result = await session.run_session(job)
    assert h.sdk_calls and result["provider"] == "anthropic"


def test_canonical_rule_sits_before_create_workspace():
    tree = ast.parse((REPO / "src" / "runner" / "session.py").read_text())
    run_session = next(n for n in ast.walk(tree)
                       if isinstance(n, ast.AsyncFunctionDef) and n.name == "run_session")
    src = ast.unparse(run_session)
    assert src.index("canonical_refusal(") < src.index("create_workspace(")


# (d) the gate's allowance is carved out of the executor's budget.


def test_executor_budget_reserves_the_gate_allowance():
    reserve = session.gate_reserve_s()
    assert reserve == review.GATE_TIMEOUT_SECONDS + session.GATE_PUBLISH_MARGIN_S == 660.0
    own = session.executor_timeout_s(1800, reserve_s=reserve)
    assert own == 1800 - session.EXECUTOR_TIMEOUT_MARGIN_S - reserve == 1110.0
    # Executor + gate + margin always fit under the ceiling (or hit the floor).
    for ceiling in (60, 600, 1800, session.SESSION_TIMEOUT_CAP_SECONDS):
        own = session.executor_timeout_s(ceiling, reserve_s=reserve)
        assert own >= session.EXECUTOR_TIMEOUT_FLOOR_S
        assert own == session.EXECUTOR_TIMEOUT_FLOOR_S or \
            own + reserve + session.EXECUTOR_TIMEOUT_MARGIN_S <= ceiling
    # Default reserve is zero — the T4 arithmetic is unchanged for callers.
    assert session.executor_timeout_s(1800) == 1770.0


async def test_gate_completes_inside_mains_ceiling_with_patched_constants(harness, monkeypatch):
    # Shrunk clocks: ceiling 2.0 s; executor budget = 2.0 − 0.2 − (0.6 + 0.2)
    # = 1.0 s, which the executor uses up entirely; the reviewer then takes
    # 0.5 s; publish is instant. The whole session fits under a `wait_for`
    # with main's ceiling — before the fix the executor got 1.8 s and the
    # review was cancelled by the outer deadline.
    h = harness
    monkeypatch.setattr(session, "resolve_session_timeout", lambda payload, default, cap=0: 2.0)
    monkeypatch.setattr(session, "EXECUTOR_TIMEOUT_MARGIN_S", 0.2)
    monkeypatch.setattr(session, "EXECUTOR_TIMEOUT_FLOOR_S", 0.1)
    monkeypatch.setattr(session, "GATE_PUBLISH_MARGIN_S", 0.2)
    monkeypatch.setattr(review, "GATE_TIMEOUT_SECONDS", 0.6)
    assert session.executor_timeout_s(2.0, reserve_s=session.gate_reserve_s()) == pytest.approx(1.0)

    async def slow_run(job, **kw):
        h.executor.calls.append({"job": job, **kw})
        await asyncio.sleep(kw["timeout_s"])
        return h.executor.result
    h.executor.run = slow_run

    async def slow_review(parent_job_id, diff, cwd):
        h.review_calls.append((parent_job_id, diff, cwd))
        await asyncio.sleep(0.5)
        audit_log.append(parent_job_id, "code_review_done", outcome="LGTM", review_text="LGTM")
        return ReviewOutcome.lgtm
    monkeypatch.setattr(session.review, "run_code_review", slow_review)

    job = _job()
    result = await asyncio.wait_for(session.run_session(job), timeout=2.0)
    assert h.executor.calls[0]["timeout_s"] == pytest.approx(1.0)
    assert result["review_outcome"] == ReviewOutcome.lgtm.value
    assert len(h.publish_calls) == 1 and h.synced == [h.created[0]]
    assert _event(job.id, "merge_gate_verdict")["timed_out"] is False


# (e) empty description → the job kind is the subject.


@pytest.mark.parametrize("description", ["", "   \n  "])
async def test_empty_description_uses_the_kind_as_commit_subject(harness, description):
    h = harness
    job = _job(description=description)
    result = await session.run_session(job)
    assert result["review_outcome"] == ReviewOutcome.lgtm.value
    assert h.publish_calls[0]["message"] == "demo: demo"


# (f) a push rejected after LGTM is a typed failure.


def test_audit_log_docstring_lists_publish_failed_and_merge_gate_refused():
    doc = (REPO / "src" / "audit_log.py").read_text()
    assert "publish_failed" in doc and "merge_gate_refused" in doc
