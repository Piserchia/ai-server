"""
The project deploy autopilot in `scripts/healthcheck-all.sh` (2026-11-21):
`check_project_deploys` and its helpers, driven end to end against real git
repos in `tmp_path` with fake `psql` / `redis-cli` / `curl` on PATH. No DB,
Redis, Telegram or network is touched.

Fixture shape: `origin.git` (bare) ← `projects/<slug>` (the runtime clone,
manifest tracked in the project repo, like atlas) and a `work` clone that
"merges PRs" by pushing to origin. The fakes record every call in
`calls.log`; `FAKE_INFLIGHT` sets what the in-flight count query answers.

Needs `yq` (Go or Python flavour — the script uses `yq -r`, valid in both).

Run: PIPENV_DONT_LOAD_ENV=1 SERVER_ROOT="$PWD" pipenv run pytest tests/test_project_autopilot.py -q -p no:cacheprovider
"""

from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "healthcheck-all.sh"

pytestmark = pytest.mark.skipif(shutil.which("yq") is None or shutil.which("git") is None,
                                reason="needs yq and git on PATH")

FNS = ("resolve_venv_py", "notify_send", "deploy_in_flight", "env_value", "alert_owner",
       "project_deploy_target", "range_is_docs_only", "project_deploy_followup",
       "check_project_deploys")

JOB_ID = "11111111-2222-3333-4444-555555555555"

ATLAS_LIKE = """slug: {slug}
type: service
port: 8791
healthcheck: /
delivery:
  topology: {topology}
  dev_repo: "~/Documents/repos/{slug}"
  runtime_clone: pull-only
  branch: {branch}
  deployable: {deployable}
  deploy:
    skill: {skill}
    autonomy: {autonomy}
    gates:
      - kind: test
        cmd: "true"
    services:
      - {slug}
"""


def _fn(name: str) -> str:
    src = SCRIPT.read_text()
    m = re.search(rf"^{re.escape(name)}\(\) \{{.*?^\}}", src, re.DOTALL | re.MULTILINE)
    assert m, f"no top-level bash function {name}()"
    return m.group(0)


def _exe(path: Path, body: str) -> None:
    path.write_text("#!/bin/bash\n" + body)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _git(cwd: Path, *args: str) -> str:
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid"}
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, env=env, check=False)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


class Env:
    """A fake server checkout with one or more projects."""

    def __init__(self, tmp: Path):
        self.tmp = tmp
        self.root = tmp / "srv"
        (self.root / "projects").mkdir(parents=True)
        (self.root / "volumes" / "state").mkdir(parents=True)
        (self.root / "volumes" / "logs").mkdir(parents=True)
        for skill in ("atlas-redeploy", "project-redeploy"):
            (self.root / "skills" / skill).mkdir(parents=True)
            (self.root / "skills" / skill / "SKILL.md").write_text("---\nname: x\n---\n")
        (self.root / ".env").write_text("TELEGRAM_BOT_TOKEN=tok\nTELEGRAM_ALLOWED_CHAT_IDS=42,7\n")
        self.bin = tmp / "bin"
        self.bin.mkdir()
        self.calls = tmp / "calls.log"
        _exe(self.bin / "psql", f"""
echo "psql $*" | tr '\\n' ' ' >> '{self.calls}'; echo >> '{self.calls}'
case "$*" in
  *"SELECT count(*)"*) echo "${{FAKE_INFLIGHT:-0}}" ;;
  *"INSERT INTO jobs"*) echo "{JOB_ID}" ;;
  *"SELECT status"*) echo "${{FAKE_STATUS:-failed}}" ;;
esac
""")
        _exe(self.bin / "redis-cli", f"echo \"redis $*\" >> '{self.calls}'\nexit ${{FAKE_REDIS_RC:-0}}\n")
        _exe(self.bin / "curl", f"echo \"curl $*\" >> '{self.calls}'\nexit 0\n")
        self.work: dict[str, Path] = {}

    def add_project(self, slug: str, *, topology="dev-repo", branch="master", deployable="true",
                    skill="atlas-redeploy", autonomy="gated-auto") -> Path:
        origin = self.tmp / f"{slug}-origin.git"
        _git(self.tmp, "init", "-q", "--bare", "-b", branch, str(origin))
        work = self.tmp / f"{slug}-work"
        _git(self.tmp, "clone", "-q", str(origin), str(work))
        _git(work, "checkout", "-q", "-b", branch)
        (work / "manifest.yml").write_text(ATLAS_LIKE.format(
            slug=slug, topology=topology, branch=branch, deployable=deployable,
            skill=skill, autonomy=autonomy))
        (work / "app.py").write_text("v = 1\n")
        _git(work, "add", "-A")
        _git(work, "commit", "-q", "-m", "init")
        _git(work, "push", "-q", "origin", branch)
        runtime = self.root / "projects" / slug
        _git(self.tmp, "clone", "-q", "-b", branch, str(origin), str(runtime))
        self.work[slug] = work
        return runtime

    def commit(self, slug: str, path: str, text: str, *, push=True) -> str:
        work = self.work[slug]
        (work / path).parent.mkdir(parents=True, exist_ok=True)
        (work / path).write_text(text)
        _git(work, "add", "-A")
        _git(work, "commit", "-q", "-m", f"change {path}")
        if push:
            _git(work, "push", "-q", "origin", "HEAD")
        return _git(work, "rev-parse", "HEAD")

    def head(self, slug: str) -> str:
        return _git(self.root / "projects" / slug, "rev-parse", "HEAD")

    def marker(self, slug: str, sha: str) -> None:
        (self.root / "volumes" / "state" / f"deployed-sha-{slug}").write_text(sha + "\n")

    def state(self, slug: str) -> str:
        p = self.root / "volumes" / "state" / f"autodeploy-{slug}"
        return p.read_text().strip() if p.exists() else ""

    def run(self, call: str = "check_project_deploys", **env: str) -> subprocess.CompletedProcess:
        script = "\n".join(_fn(n) for n in FNS) + "\n" + call + "\n"
        full = {**os.environ,
                "PATH": f"{self.bin}:{os.environ['PATH']}",
                "PROJECT_DIR": str(self.root), "LOG": str(self.root / "volumes/logs/hc.log"),
                "PROJ_STATE_DIR": str(self.root / "volumes" / "state"),
                "DEPLOY_QUIET_SECONDS": "0", "VENV_PY": "", "HOME": str(self.tmp),
                **env}
        r = subprocess.run(["bash", "-c", script], capture_output=True, text=True, env=full, check=False)
        assert r.returncode == 0, r.stderr
        return r

    def log(self) -> str:
        p = self.root / "volumes/logs/hc.log"
        return p.read_text() if p.exists() else ""

    def call_log(self) -> str:
        return self.calls.read_text() if self.calls.exists() else ""

    def inserts(self) -> list[str]:
        return [ln for ln in self.call_log().splitlines() if "INSERT INTO jobs" in ln]


@pytest.fixture
def env(tmp_path):
    return Env(tmp_path)


# ── dispatch ────────────────────────────────────────────────────────────────


def test_new_code_commit_dispatches_the_manifest_executor_once(env):
    env.add_project("atlas")
    env.marker("atlas", env.head("atlas"))
    tip = env.commit("atlas", "app.py", "v = 2\n")
    env.run()
    calls = env.call_log()
    ins = env.inserts()
    assert len(ins) == 1
    assert "'atlas_redeploy'" in ins[0]
    assert '{"project_slug": "atlas"}' in ins[0]
    assert "'deploy-autopilot'" in ins[0]
    assert f"redis lpush jobs:queue {JOB_ID}" in calls
    assert env.state("atlas") == f"{tip} {JOB_ID} 0"
    # the runtime clone is never pulled by the watcher — only fetched
    assert env.head("atlas") != tip
    # a second tick with the same tip dispatches nothing new
    env.run(FAKE_INFLIGHT="1")
    env.run()
    assert len(env.inserts()) == 1


def test_default_skill_is_project_redeploy(env):
    env.add_project("pickem", branch="main", skill='""')
    env.marker("pickem", env.head("pickem"))
    env.commit("pickem", "app.py", "v = 2\n")
    env.run()
    assert "'project_redeploy'" in env.inserts()[0]


def test_markdown_only_range_does_not_wake_a_deploy(env):
    env.add_project("atlas")
    env.marker("atlas", env.head("atlas"))
    env.commit("atlas", "alpha-lab/evaluation/LEDGER.md", "entry\n")
    env.run()
    assert env.inserts() == []
    # opt-in switch deploys docs too
    (env.root / ".env").write_text((env.root / ".env").read_text() + "DEPLOY_AUTOPILOT_INCLUDE_DOCS=1\n")
    env.run()
    assert len(env.inserts()) == 1


def test_docs_after_a_failed_attempt_do_not_retry_the_broken_range(env):
    env.add_project("atlas")
    env.marker("atlas", env.head("atlas"))
    env.commit("atlas", "app.py", "v = 2\n")
    env.run()                                    # attempt 1 (assume it went red)
    env.commit("atlas", "CHANGELOG.md", "x\n")   # ledger commit lands on top
    env.run()
    assert len(env.inserts()) == 1               # md-only since the last attempt
    env.commit("atlas", "app.py", "v = 3\n")     # a real fix lands
    env.run()
    assert len(env.inserts()) == 2


def test_in_flight_deploy_blocks_dispatch(env):
    env.add_project("atlas")
    env.marker("atlas", env.head("atlas"))
    env.commit("atlas", "app.py", "v = 2\n")
    env.run(FAKE_INFLIGHT="1")
    assert env.inserts() == []
    env.run(FAKE_INFLIGHT="garbage")             # unknown = stand down
    assert env.inserts() == []


def test_quiet_window_waits_for_a_settled_tip(env):
    env.add_project("atlas")
    env.marker("atlas", env.head("atlas"))
    env.commit("atlas", "app.py", "v = 2\n")
    env.run(DEPLOY_QUIET_SECONDS="600")
    assert env.inserts() == []


def test_already_deployed_marker_dispatches_nothing(env):
    env.add_project("atlas")
    tip = env.commit("atlas", "app.py", "v = 2\n")
    env.marker("atlas", tip)
    env.run()
    assert env.inserts() == []


def test_no_marker_and_clone_at_tip_dispatches_nothing(env):
    env.add_project("atlas")
    env.run()
    assert env.inserts() == []


@pytest.mark.parametrize("kw", [
    {"autonomy": "human-approval"},
    {"autonomy": "manual-only"},
    {"topology": "in-place"},
    {"deployable": "false"},
    {"skill": "no-such-skill"},
])
def test_ineligible_contracts_are_left_alone(env, kw):
    env.add_project("proj", **kw)
    env.marker("proj", env.head("proj"))
    env.commit("proj", "app.py", "v = 2\n")
    env.run()
    assert env.inserts() == []


def test_switches(env):
    env.add_project("atlas")
    env.marker("atlas", env.head("atlas"))
    env.commit("atlas", "app.py", "v = 2\n")
    base = (env.root / ".env").read_text()
    for line in ("DEPLOY_AUTOPILOT=0", "DEPLOY_AUTOPILOT_PROJECTS=false",
                 "DEPLOY_AUTOPILOT_SKIP=pickem,atlas"):
        (env.root / ".env").write_text(base + line + "\n")
        env.run()
        assert env.inserts() == [], line


def test_quarantined_dirs_are_ignored(env):
    rt = env.add_project("atlas")
    rt.rename(rt.parent / "atlas.stale-clone-20260731.quarantined")
    env.run()
    assert env.inserts() == []


def test_one_dispatch_per_tick(env):
    for slug in ("atlas", "pickem"):
        env.add_project(slug)
        env.marker(slug, env.head(slug))
        env.commit(slug, "app.py", "v = 2\n")
    env.run()
    assert len(env.inserts()) == 1


def test_lpush_failure_cancels_the_row_and_records_no_attempt(env):
    env.add_project("atlas")
    env.marker("atlas", env.head("atlas"))
    env.commit("atlas", "app.py", "v = 2\n")
    env.run(FAKE_REDIS_RC="1")
    assert "status='cancelled'" in env.call_log()
    assert env.state("atlas") == ""


def test_divergence_alerts_once_and_dispatches_nothing(env):
    rt = env.add_project("atlas")
    env.marker("atlas", env.head("atlas"))
    (rt / "local.txt").write_text("runtime-born\n")
    _git(rt, "add", "-A")
    _git(rt, "commit", "-q", "-m", "runtime-born commit")
    env.commit("atlas", "app.py", "v = 2\n")
    env.run()
    env.run()
    env.commit("atlas", "app.py", "v = 3\n")   # a new tip does not re-alert
    env.run()
    assert env.inserts() == []
    assert env.call_log().count("api.telegram.org") == 1
    assert "diverged" in env.log()
    # reconciled (clone reset onto origin by a human) → deploys resume
    _git(rt, "fetch", "-q", "origin")
    _git(rt, "reset", "-q", "--hard", "HEAD~1")
    env.run()
    assert len(env.inserts()) == 1
    assert not (env.root / "volumes/state/autodeploy-atlas.diverged").exists()


# ── follow-up ───────────────────────────────────────────────────────────────


def test_followup_green_logs_and_closes_without_alert(env):
    env.add_project("atlas")
    env.marker("atlas", env.head("atlas"))
    tip = env.commit("atlas", "app.py", "v = 2\n")
    env.run()
    env.marker("atlas", tip)                     # the executor shipped it
    env.run()
    assert env.state("atlas") == f"{tip} {JOB_ID} 1"
    assert "api.telegram.org" not in env.call_log()
    assert f"AUTOPILOT atlas deployed {tip[:8]}" in env.log()


def test_followup_red_alerts_once_naming_the_job(env):
    env.add_project("atlas")
    env.marker("atlas", env.head("atlas"))
    tip = env.commit("atlas", "app.py", "v = 2\n")
    env.run()
    env.run(FAKE_INFLIGHT="1")                   # still running: no verdict yet
    assert "api.telegram.org" not in env.call_log()
    env.run()                                    # done, marker never moved
    env.run()
    calls = env.call_log()
    assert calls.count("api.telegram.org") == 1
    assert JOB_ID[:8] in calls and "failed" in calls
    assert env.state("atlas") == f"{tip} {JOB_ID} 1"
    assert len(env.inserts()) == 1               # no retry of the same tip


def test_project_deploy_target_reads_atlas_manifest_shape(env):
    rt = env.add_project("atlas")
    r = env.run(f"project_deploy_target '{rt}/manifest.yml'")
    assert r.stdout.strip() == "atlas_redeploy master"


def test_deploy_in_flight_counts_every_redeploy_kind():
    fn = _fn("deploy_in_flight")
    for needle in ("'server-deploy'", "'deploy_director'", "%\\_redeploy", "%-redeploy",
                   "resolved_skill LIKE"):
        assert needle in fn
