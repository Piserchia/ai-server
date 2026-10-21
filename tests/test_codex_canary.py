"""
T10 canary entry points of the Codex executor (cross-vendor writer slice,
2026-10-21; plan §5 T10): `python -m src.runner.executors.codex_cli
--canary <clone>` and `--gate-dry-run <clone>`.

Pure/fixture style: the process factory is injected and replays the
recorded `command_and_file.jsonl` stream while writing to the clone exactly
what that run wrote on disk; the reviewer is a stub. No network, no live
SDK, no live `codex`. The live run itself is `scripts/codex-canary.sh`,
which is the ONE place that spawns the real binary, and its measurements
go into the plan's §8 table — never into this suite.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src import audit_log
from src.config import settings
from src.runner.executors import codex_cli
from tests.test_codex_executor import (
    DENIED_ENV, JOB_ID, MODEL, VERSION_LINE, FakeProc, fixture_bytes,
)

SENTINEL = codex_cli.CANARY_SENTINEL


# ── a process factory that behaves like the recorded canary run ──────────────


def canary_factory(*, stdout_fixture: str = "command_and_file.jsonl",
                   env_keys: tuple[str, ...] = ("PATH", "HOME", "LANG", "TMPDIR",
                                                "CODEX_HOME", "PWD", "SHLVL"),
                   write_canary: bool = True, write_env: bool = True,
                   write_output: str | None = "did the thing\n\nTASK_COMPLETE: canary",
                   escape: bool = False, extra_files: tuple[str, ...] = (),
                   returncode: int = 0):
    """Replays `stdout_fixture` and performs the side effects the real CLI
    would: the canary file, the env-names file, the `-o` file, optionally
    an escape file (a Seatbelt failure) and extra files."""
    calls: dict = {"exec": [], "version": []}

    async def factory(argv: list[str], *, cwd: str, env: dict[str, str]):
        if argv[-1] == "--version":
            calls["version"].append(argv)
            return FakeProc(VERSION_LINE.encode() + b"\n")
        calls["exec"].append({"argv": argv, "cwd": cwd, "env": env})
        clone = Path(argv[argv.index("-C") + 1])
        if write_canary:
            (clone / codex_cli.CANARY_FILE).write_text(codex_cli.CANARY_LINE + "\n")
        if write_env:
            (clone / codex_cli.CANARY_ENV_FILE).write_text("\n".join(sorted(env_keys)) + "\n")
        for name in extra_files:
            (clone / name).write_text("stray\n")
        if escape:
            prompt = argv[-1]
            escape_path = codex_cli.escape_path_from_prompt(prompt)
            Path(escape_path).write_text("escaped\n")
        if write_output is not None:
            Path(argv[argv.index("-o") + 1]).write_text(write_output, encoding="utf-8")
        proc = FakeProc(fixture_bytes(stdout_fixture), returncode)
        calls["proc"] = proc
        return proc

    return factory, calls


@pytest.fixture
def root(tmp_path: Path, monkeypatch) -> Path:
    """Every write the canary makes lands under tmp_path: `settings.server_root`
    (audit log + the `-o` file) and HOME (the escape probe)."""
    r = tmp_path / "fake-server-root"
    monkeypatch.setattr(settings, "server_root", r)
    monkeypatch.setattr(settings, "codex_bin", "")
    monkeypatch.setattr(settings, "codex_home", "")
    monkeypatch.setattr(settings, "codex_run_as_user", "")
    return r


@pytest.fixture
def clone(tmp_path: Path) -> Path:
    d = tmp_path / "clone"
    d.mkdir()
    (d / "README.md").write_text("seed\n")
    (d / ".git").mkdir()
    return d


@pytest.fixture
def codex_bin(tmp_path: Path) -> str:
    b = tmp_path / "bin" / "codex"
    b.parent.mkdir()
    b.write_text("#!/bin/sh\nexit 1\n")
    return str(b)


@pytest.fixture
def escape_path(tmp_path: Path) -> Path:
    return tmp_path / "home" / "codex-canary-escape.txt"


@pytest.fixture
def environ() -> dict[str, str]:
    return {"PATH": "/usr/bin:/bin", "HOME": "/Users/owner", "LANG": "C",
            "TMPDIR": "/tmp/x", **DENIED_ENV}


async def run_canary(clone: Path, codex_bin: str, escape_path: Path, environ: dict,
                     **factory_kw):
    factory, calls = canary_factory(**factory_kw)
    report = await codex_cli.run_canary(
        clone, model_id=MODEL, sandbox="workspace-write", timeout_s=30,
        job_id=JOB_ID, process_factory=factory, codex_bin=codex_bin,
        escape_path=escape_path, environ=environ)
    return report, calls


# ── prompt ───────────────────────────────────────────────────────────────────


def test_canary_prompt_names_every_probe_and_the_marker():
    prompt = codex_cli.build_canary_prompt(escape_path="/Users/owner/escape.txt")
    assert not prompt.lstrip().startswith("-")  # build_argv would refuse it
    assert codex_cli.CANARY_ENV_FILE in prompt
    assert codex_cli.CANARY_FILE in prompt
    assert codex_cli.CANARY_LINE in prompt
    assert "/Users/owner/escape.txt" in prompt
    assert prompt.rstrip().endswith(codex_cli.CANARY_MARKER)
    # names only — the env file must never carry values into the clone / diff
    assert "cut -d= -f1" in prompt
    assert codex_cli.escape_path_from_prompt(prompt) == "/Users/owner/escape.txt"


def test_canary_environ_plants_sentinels_for_every_denied_name(environ):
    env = codex_cli.canary_environ(environ)
    assert env["PATH"] == environ["PATH"]
    for name in codex_cli.CANARY_SENTINEL_NAMES:
        assert env[name] == SENTINEL
    # and the scrub still removes every one of them
    scrubbed = codex_cli.scrubbed_env(env)
    assert not any(codex_cli.is_denied_env_name(k) for k in scrubbed)


@pytest.mark.parametrize("name,denied", [
    ("ANTHROPIC_API_KEY", True), ("ANTHROPIC_BASE_URL", True),
    ("CLAUDE_CODE_OAUTH_TOKEN", True), ("TELEGRAM_BOT_TOKEN", True),
    ("TELEGRAM_ALLOWED_CHAT_IDS", True), ("DATABASE_URL", True),
    ("POSTGRES_DSN", True), ("POSTGRES_PASSWORD", True), ("REDIS_URL", True),
    ("WEB_AUTH_TOKEN", True), ("ALPACA_API_KEY", True), ("TRADIER_SANDBOX_TOKEN", True),
    ("FINNHUB_TOKEN", True), ("OPENAI_API_KEY", True),
    ("PATH", False), ("HOME", False), ("CODEX_HOME", False), ("CODEX_SANDBOX", False),
    ("PWD", False), ("SHLVL", False), ("LANG", False),
])
def test_is_denied_env_name(name: str, denied: bool):
    assert codex_cli.is_denied_env_name(name) is denied


# ── the golden run ───────────────────────────────────────────────────────────


async def test_canary_golden_run_passes_every_check(root, clone, codex_bin, escape_path,
                                                    environ):
    report, calls = await run_canary(clone, codex_bin, escape_path, environ)
    assert report["ok"] is True, json.dumps(report["checks"], indent=1)
    failed = [k for k, v in report["checks"].items() if not v["ok"]]
    assert failed == []
    assert set(report["checks"]) == set(codex_cli.CANARY_CHECKS)
    # measurements the §8 table needs
    assert report["wall_seconds"] >= 0
    assert report["usage"]["input_tokens"] == 47324
    assert report["usage"]["output_tokens"] == 477
    assert report["terminal_reason"] == "ok"
    assert report["rate_limited"] is False
    assert report["auth_expired"] is False
    assert report["ran"] is True
    assert report["exit_code"] == 0
    assert report["cli_version"] == VERSION_LINE
    assert report["model_served"] is None  # the recorded stream carries no model
    assert report["kinds"][0] == "executor_started"
    assert report["kinds"][-1] == "turn_completed"
    assert "TASK_COMPLETE" in report["final_text_tail"]
    assert report["job_id"] == JOB_ID


async def test_canary_uses_the_slice_argv_env_and_out_of_clone_output(root, clone, codex_bin,
                                                                      escape_path, environ):
    report, calls = await run_canary(clone, codex_bin, escape_path, environ)
    call = calls["exec"][0]
    argv = call["argv"]
    assert argv[:2] == [codex_bin, "exec"]
    for flag in ("--json", "--ephemeral", "--ignore-user-config", "--skip-git-repo-check"):
        assert flag in argv
    assert argv[argv.index("--sandbox") + 1] == "workspace-write"
    assert argv[argv.index("-C") + 1] == str(clone)
    assert argv[argv.index("-m") + 1] == MODEL
    assert argv[-1].rstrip().endswith(codex_cli.CANARY_MARKER)
    # env: exactly the allowlist, sentinels gone
    assert set(call["env"]) <= set(codex_cli.ALLOWED_ENV_KEYS)
    assert SENTINEL not in json.dumps(call["env"])
    # `-o` is the real default location: audit_log_dir, outside the clone
    out = Path(argv[argv.index("-o") + 1])
    assert out == settings.audit_log_dir / f"{JOB_ID}.codex-last.md"
    assert not out.resolve().is_relative_to(clone.resolve())
    assert report["output_path"] == str(out)
    assert report["checks"]["output_file"]["ok"] is True


async def test_canary_audits_every_event_under_the_job(root, clone, codex_bin, escape_path,
                                                       environ):
    report, _ = await run_canary(clone, codex_bin, escape_path, environ)
    entries = audit_log.read(JOB_ID)
    assert [e["kind"] for e in entries] == report["kinds"]
    assert entries[0]["executor"] == "codex_cli"
    # the audit log lives under the (fake) server root, never in the clone
    assert settings.audit_log_dir.resolve().is_relative_to(root.resolve())
    assert not list(clone.rglob("*.jsonl"))


# ── each check fails for the right reason ────────────────────────────────────


async def test_canary_detects_a_leaked_env_name(root, clone, codex_bin, escape_path, environ):
    report, _ = await run_canary(clone, codex_bin, escape_path, environ,
                                 env_keys=("PATH", "HOME", "ANTHROPIC_API_KEY",
                                           "TELEGRAM_BOT_TOKEN"))
    assert report["ok"] is False
    check = report["checks"]["env_scrub"]
    assert check["ok"] is False
    assert "ANTHROPIC_API_KEY" in check["detail"] and "TELEGRAM_BOT_TOKEN" in check["detail"]
    assert report["secrets_visible"] is True
    # names, never values, in the report
    assert check["env_names"] == ["ANTHROPIC_API_KEY", "HOME", "PATH", "TELEGRAM_BOT_TOKEN"]


async def test_canary_detects_a_missing_env_file(root, clone, codex_bin, escape_path, environ):
    report, _ = await run_canary(clone, codex_bin, escape_path, environ, write_env=False)
    assert report["checks"]["env_scrub"]["ok"] is False
    assert "missing" in report["checks"]["env_scrub"]["detail"]
    assert report["secrets_visible"] is None  # unknown, not "no"


async def test_canary_detects_a_sentinel_echoed_into_the_stream(root, clone, codex_bin,
                                                                escape_path, environ, tmp_path):
    # Build a stream whose agent message echoes the sentinel value.
    src = fixture_bytes("command_and_file.jsonl").decode()
    leaked = src.replace("I’ll run `ls -la`", f"leak {SENTINEL} here")
    assert SENTINEL in leaked
    fx = tmp_path / "leak.jsonl"
    fx.write_text(leaked)
    factory, _ = canary_factory()

    async def leaking_factory(argv, *, cwd, env):
        proc = await factory(argv, cwd=cwd, env=env)
        if argv[-1] != "--version":
            proc = FakeProc(fx.read_bytes(), 0)
        return proc

    report = await codex_cli.run_canary(
        clone, model_id=MODEL, sandbox="workspace-write", timeout_s=30, job_id=JOB_ID,
        process_factory=leaking_factory, codex_bin=codex_bin, escape_path=escape_path,
        environ=environ)
    assert report["checks"]["env_scrub"]["ok"] is False
    assert "sentinel" in report["checks"]["env_scrub"]["detail"]


async def test_canary_detects_an_escape_outside_the_clone_and_removes_it(root, clone, codex_bin,
                                                                         escape_path, environ):
    escape_path.parent.mkdir(parents=True)
    report, _ = await run_canary(clone, codex_bin, escape_path, environ, escape=True)
    assert report["ok"] is False
    assert report["checks"]["nothing_outside"]["ok"] is False
    assert not escape_path.exists()  # cleaned up after being recorded
    assert "agent_reported_blocked=False" in report["checks"]["nothing_outside"]["detail"]


async def test_canary_detects_stray_files_in_the_clone(root, clone, codex_bin, escape_path,
                                                       environ):
    report, _ = await run_canary(clone, codex_bin, escape_path, environ,
                                 extra_files=("notes.txt",))
    assert report["checks"]["only_expected_files"]["ok"] is False
    assert "notes.txt" in report["checks"]["only_expected_files"]["detail"]


async def test_canary_detects_a_missing_canary_file(root, clone, codex_bin, escape_path, environ):
    report, _ = await run_canary(clone, codex_bin, escape_path, environ, write_canary=False)
    assert report["checks"]["file_in_clone"]["ok"] is False


async def test_canary_detects_a_missing_marker(root, clone, codex_bin, escape_path, environ):
    report, _ = await run_canary(clone, codex_bin, escape_path, environ,
                                 write_output="done, no marker")
    assert report["checks"]["task_complete_marker"]["ok"] is False


async def test_canary_detects_a_missing_output_file(root, clone, codex_bin, escape_path, environ):
    # No `-o` file: final text falls back to the last agent_message (which in
    # the fixture carries the marker), but the output_file check must fail.
    report, _ = await run_canary(clone, codex_bin, escape_path, environ, write_output=None)
    assert report["checks"]["output_file"]["ok"] is False
    assert report["checks"]["task_complete_marker"]["ok"] is True


async def test_canary_detects_an_out_of_order_stream(root, clone, codex_bin, escape_path,
                                                     environ):
    report, _ = await run_canary(clone, codex_bin, escape_path, environ,
                                 stdout_fixture="ok.jsonl")  # no tool_use at all
    assert report["checks"]["kind_sequence"]["ok"] is False


async def test_canary_rate_limited_is_recorded_not_retried(root, clone, codex_bin, escape_path,
                                                           environ):
    report, calls = await run_canary(clone, codex_bin, escape_path, environ,
                                     stdout_fixture="file_change_and_failure.jsonl",
                                     write_canary=False, write_env=False, write_output=None)
    assert report["ran"] is False
    assert report["rate_limited"] is True
    assert report["terminal_reason"] == "rate_limited"
    assert report["ok"] is False
    assert len(calls["exec"]) == 1  # exactly one attempt


def test_recorded_sandbox_denied_stream_carries_no_command_item():
    """T10 live finding (0.162.0-alpha.17.2): a Seatbelt-denied command runs
    (the agent quotes `Operation not permitted`) but the `--json` stream has
    no `command_execution` item for it, so the audit log shows no
    `tool_use`. The canary records the agent's own report beside the
    stream view instead of pretending the stream is complete."""
    from tests.test_codex_executor import fixture_events
    mapper = codex_cli.EventMapper(JOB_ID, model_id=MODEL, cli_version=VERSION_LINE,
                                   env_keys=[])
    kinds = [k for ev in fixture_events("sandbox_denied.jsonl") for k, _ in mapper.map(ev)]
    assert kinds == ["executor_started", "text", "text", "turn_completed"]
    assert "tool_use" not in kinds
    assert "Operation not permitted" in mapper.last_agent_message
    assert codex_cli._BLOCKED_RE.search(mapper.last_agent_message)


def test_kind_sequence_rule():
    ok = ["executor_started", "text", "tool_use", "tool_result", "tool_use", "tool_result",
          "text", "turn_completed"]
    assert codex_cli.check_kind_sequence(ok)[0] is True
    assert codex_cli.check_kind_sequence(["executor_started", "text", "turn_completed"])[0] is False
    assert codex_cli.check_kind_sequence(
        ["executor_started", "tool_use", "tool_result", "turn_completed", "text"])[0] is False
    assert codex_cli.check_kind_sequence(
        ["text", "executor_started", "tool_use", "tool_result", "text", "turn_completed"])[0] is False
    assert codex_cli.check_kind_sequence(
        ["executor_started", "tool_use", "tool_result", "text", "turn_completed",
         "executor_error"])[0] is False


# ── gate dry-run ─────────────────────────────────────────────────────────────


async def test_gate_dry_run_reviews_the_clone_diff_and_never_syncs(root, clone, monkeypatch):
    from src.runner import review

    seen: dict = {}

    def fake_diff(cwd, base_sha):
        seen["diff_args"] = (Path(cwd), base_sha)
        return "--- /dev/null\n+++ b/codex-canary.txt\n@@ -0,0 +1 @@\n+hello\n"

    async def fake_review(parent_job_id, diff, cwd):
        seen["review_args"] = (parent_job_id, diff, Path(cwd))
        audit_log.append(parent_job_id, "code_review_done", outcome="LGTM",
                         review_text="- fine\n- also fine\n")
        return review.ReviewOutcome.lgtm

    monkeypatch.setattr(review, "diff_for_gate", fake_diff)
    monkeypatch.setattr(review, "run_code_review", fake_review)
    for forbidden in ("sync_canonical", "publish_workspace"):
        monkeypatch.setattr("src.runner.workspaces." + forbidden,
                            lambda *a, **k: pytest.fail(forbidden + " must not run"),
                            raising=False)

    report = await codex_cli.gate_dry_run(clone, base_sha="abc123", job_id=JOB_ID)
    assert seen["diff_args"] == (clone, "abc123")
    assert seen["review_args"][0] == JOB_ID and seen["review_args"][2] == clone
    assert report["verdict"] == "LGTM"
    assert report["diff_chars"] > 0
    assert report["denied_paths"] == []
    assert report["findings_n"] == 2
    assert "fine" in report["review_text"]
    assert report["reviewer"] == f"{review.REVIEWER_PROVIDER}/{review.REVIEWER_MODEL}"
    assert report["synced"] is False


async def test_gate_dry_run_empty_diff_skips_the_reviewer(root, clone, monkeypatch):
    from src.runner import review
    monkeypatch.setattr(review, "diff_for_gate", lambda cwd, base_sha: "")

    async def never(*a, **k):
        pytest.fail("reviewer must not run on an empty diff")

    monkeypatch.setattr(review, "run_code_review", never)
    report = await codex_cli.gate_dry_run(clone, base_sha="abc123", job_id=JOB_ID)
    assert report["verdict"] == "empty_diff"
    assert report["diff_chars"] == 0


async def test_gate_dry_run_refuses_denied_paths_before_the_reviewer(root, clone, monkeypatch):
    from src.runner import review
    monkeypatch.setattr(review, "diff_for_gate", lambda cwd, base_sha:
                        "--- /dev/null\n+++ b/.claude/settings.json\n@@ -0,0 +1 @@\n+{}\n")

    async def never(*a, **k):
        pytest.fail("reviewer must not run on a denied diff")

    monkeypatch.setattr(review, "run_code_review", never)
    report = await codex_cli.gate_dry_run(clone, base_sha="abc123", job_id=JOB_ID)
    assert report["verdict"] == "refused"
    assert report["denied_paths"] == [".claude/settings.json"]


async def test_gate_dry_run_timeout_counts_as_changes_requested(root, clone, monkeypatch):
    import asyncio
    from src.runner import review
    monkeypatch.setattr(review, "diff_for_gate", lambda cwd, base_sha: "+x\n")

    async def slow(*a, **k):
        await asyncio.sleep(10)

    monkeypatch.setattr(review, "run_code_review", slow)
    report = await codex_cli.gate_dry_run(clone, base_sha="abc123", job_id=JOB_ID,
                                          timeout_s=0.01)
    assert report["verdict"] == review.ReviewOutcome.changes_requested.value
    assert "timeout" in report["detail"]


# ── main(): argv, report file, exit codes ────────────────────────────────────


def test_main_canary_writes_the_report_and_exits_zero(root, clone, codex_bin, escape_path,
                                                      environ, tmp_path):
    factory, _ = canary_factory()
    report_path = tmp_path / "canary-report.json"
    rc = codex_cli.main(
        ["--canary", str(clone), "--model", MODEL, "--timeout", "30", "--job-id", JOB_ID,
         "--escape-path", str(escape_path), "--report", str(report_path),
         "--codex-bin", codex_bin],
        process_factory=factory, environ=environ)
    assert rc == 0
    report = json.loads(report_path.read_text())
    assert report["ok"] is True and report["ran"] is True


def test_main_canary_exit_codes(root, clone, codex_bin, escape_path, environ, tmp_path):
    # 1 = ran but a check failed
    factory, _ = canary_factory(write_canary=False)
    rc = codex_cli.main(["--canary", str(clone), "--job-id", JOB_ID,
                         "--escape-path", str(escape_path), "--codex-bin", codex_bin,
                         "--report", str(tmp_path / "r1.json")],
                        process_factory=factory, environ=environ)
    assert rc == 1
    # 2 = did not run (rate-limited / auth lapsed)
    factory, _ = canary_factory(stdout_fixture="file_change_and_failure.jsonl",
                                write_canary=False, write_env=False, write_output=None)
    rc = codex_cli.main(["--canary", str(clone), "--job-id", JOB_ID,
                         "--escape-path", str(escape_path), "--codex-bin", codex_bin,
                         "--report", str(tmp_path / "r2.json")],
                        process_factory=factory, environ=environ)
    assert rc == 2
    assert json.loads((tmp_path / "r2.json").read_text())["rate_limited"] is True


def test_main_refuses_a_clone_under_the_server_root_or_volumes(root, codex_bin, tmp_path,
                                                                monkeypatch):
    inside = root / "volumes" / "workspaces" / "x"
    inside.mkdir(parents=True)
    rc = codex_cli.main(["--canary", str(inside), "--codex-bin", codex_bin])
    assert rc == 3
    vol = tmp_path / "elsewhere" / "volumes" / "clone"
    vol.mkdir(parents=True)
    rc = codex_cli.main(["--canary", str(vol), "--codex-bin", codex_bin])
    assert rc == 3
    # and never with the audit log pointed at the production tree (the dev
    # .env does exactly that): the canary writes an audit log + the -o file
    ok = tmp_path / "ok-clone"
    ok.mkdir()
    monkeypatch.setattr(settings, "server_root", codex_cli.PROD_ROOT)
    rc = codex_cli.main(["--canary", str(ok), "--codex-bin", codex_bin])
    assert rc == 3


def test_main_gate_dry_run_writes_the_verdict(root, clone, monkeypatch, tmp_path):
    from src.runner import review
    monkeypatch.setattr(review, "diff_for_gate", lambda cwd, base_sha: "+x\n")

    async def fake_review(parent_job_id, diff, cwd):
        return review.ReviewOutcome.changes_requested

    monkeypatch.setattr(review, "run_code_review", fake_review)
    report_path = tmp_path / "gate.json"
    rc = codex_cli.main(["--gate-dry-run", str(clone), "--base-sha", "abc", "--job-id", JOB_ID,
                         "--report", str(report_path)])
    assert rc == 0  # the dry-run reports; it does not fail on a non-LGTM
    assert json.loads(report_path.read_text())["verdict"] == "changes_requested"


def test_main_requires_exactly_one_mode():
    assert codex_cli.main([]) == 64
    assert codex_cli.main(["--canary", "/a", "--gate-dry-run", "/b"]) == 64


def test_this_module_never_spawns_a_real_process():
    src = Path(__file__).read_text(encoding="utf-8")
    banned = ("import " + "subprocess", "claude_agent" + "_sdk", "shutil." + "which(",
              "create_subprocess" + "_exec")
    for needle in banned:
        assert needle not in src, needle
