"""
T3 — The Codex executor (cross-vendor writer slice, 2026-10-21; plan §5 T3,
old spec §2.4 JSONL mapping + §2.6 EnvScrubber contract).

`src/runner/executors/codex_cli.py` runs one `codex exec --json` process per
job under Codex's own Seatbelt, with a scrubbed environment, and maps the
JSONL event stream onto the EXISTING audit kinds (`tool_use`, `tool_result`,
`text`, `thinking` — C14: same strings `review._summarize_tool_usage`,
learning's Write/Edit gate and `retrospective.parse_read_events` parse) plus
three new ones (`executor_started`, `turn_completed`, `executor_error`).

Pure/fixture style: no network, no live SDK, no live `codex` process. A
process factory is injected; the fixtures under tests/fixtures/codex/ are the
recorded truth (`ok`, `command_and_file` recorded 2026-10-21 on
0.162.0-alpha.17.2; `file_change_and_failure` hand-authored, labelled so).

Run: pipenv run pytest tests/test_codex_executor.py -v
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import pytest

from src.config import settings
from src.runner.executors import codex_cli

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "codex"
VERSION_LINE = "codex-cli 0.162.0-alpha.17.2"
JOB_ID = "0123abcd-0000-4000-8000-000000000001"
MODEL = "gpt-6-luna"

# Every name the old spec §2.6 contract and plan T3 say must never reach the
# child, plus the runner's own operational keys.
DENIED_ENV = {
    "ANTHROPIC_API_KEY": "x", "ANTHROPIC_AUTH_TOKEN": "x", "ANTHROPIC_BASE_URL": "x",
    "ANTHROPIC_MAX_SESSIONS": "x", "CLAUDE_CODE_OAUTH_TOKEN": "x",
    "TELEGRAM_BOT_TOKEN": "x", "TELEGRAM_ALLOWED_CHAT_IDS": "x",
    "DATABASE_URL": "x", "POSTGRES_DSN": "x",
    "POSTGRES_PASSWORD": "x", "REDIS_URL": "x",
    "WEB_AUTH_TOKEN": "x", "ALPACA_API_KEY": "x", "ALPACA_SECRET_KEY": "x",
    "TRADIER_SANDBOX_TOKEN": "x", "FINNHUB_TOKEN": "x", "OPENAI_API_KEY": "x",
    "CODEX_API_KEY": "x", "GEMINI_API_KEY": "x", "OPENROUTER_API_KEY": "x",
    "SERVER_ROOT": "x", "ROUTER_PROVIDERS_ENABLED": "x",
}


# ── helpers: fixtures and a fake process ─────────────────────────────────────


def fixture_bytes(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def fixture_events(name: str) -> list[dict]:
    out = []
    for line in (FIXTURES / name).read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s and not s.startswith("#"):
            out.append(json.loads(s))
    return out


class FakeProc:
    """Shape of what `asyncio.create_subprocess_exec` returns, in memory."""

    def __init__(self, stdout: bytes, returncode: int = 0, *, hang: bool = False,
                 dies_on_term: bool = True, stderr: bytes = b""):
        self.stdout = asyncio.StreamReader()
        self.stdout.feed_data(stdout)
        self.stderr = asyncio.StreamReader()
        self.stderr.feed_data(stderr)
        self.stderr.feed_eof()
        self.returncode: int | None = None
        self.calls: list[str] = []
        self.dies_on_term = dies_on_term
        self._done = asyncio.Event()
        self._final_rc = returncode
        if not hang:
            self._finish(returncode)

    def _finish(self, rc: int) -> None:
        if self.returncode is not None:
            return
        self.returncode = rc
        self.stdout.feed_eof()
        self._done.set()

    async def wait(self) -> int:
        await self._done.wait()
        return self.returncode  # type: ignore[return-value]

    def terminate(self) -> None:
        self.calls.append("terminate")
        if self.dies_on_term:
            self._finish(-15)

    def kill(self) -> None:
        self.calls.append("kill")
        self._finish(-9)


def make_factory(stdout: bytes, returncode: int = 0, *, version: str | None = VERSION_LINE,
                 write_output: str | None = None, hang: bool = False,
                 dies_on_term: bool = True, stderr: bytes = b""):
    """A process factory that answers `--version` and one `exec`. Records
    every call so tests can assert argv / cwd / env, and optionally writes
    the `-o` file the way the real CLI does."""
    calls: dict = {"exec": [], "version": []}

    async def factory(argv: list[str], *, cwd: str, env: dict[str, str]):
        if argv[-1] == "--version":
            calls["version"].append({"argv": argv, "cwd": cwd, "env": env})
            if version is None:
                return FakeProc(b"", 1)
            return FakeProc(version.encode() + b"\n")
        calls["exec"].append({"argv": argv, "cwd": cwd, "env": env})
        if write_output is not None:
            Path(argv[argv.index("-o") + 1]).write_text(write_output, encoding="utf-8")
        proc = FakeProc(stdout, returncode, hang=hang, dies_on_term=dies_on_term,
                        stderr=stderr)
        calls["proc"] = proc
        return proc

    return factory, calls


class Sink:
    def __init__(self):
        self.events: list[tuple[str, dict]] = []

    async def __call__(self, kind: str, fields: dict) -> None:
        self.events.append((kind, fields))

    @property
    def kinds(self) -> list[str]:
        return [k for k, _ in self.events]


@pytest.fixture
def clone(tmp_path: Path) -> Path:
    d = tmp_path / "clone"
    d.mkdir()
    return d


@pytest.fixture
def out_path(tmp_path: Path) -> Path:
    return tmp_path / "out" / "codex-last.md"


@pytest.fixture
def codex_bin(tmp_path: Path) -> str:
    """A configured binary must exist (fail closed); the factory never runs it."""
    b = tmp_path / "bin" / "codex"
    b.parent.mkdir()
    b.write_text("#!/bin/sh\nexit 1\n")
    return str(b)


@pytest.fixture
def base_env() -> dict[str, str]:
    return {"PATH": "/usr/bin:/bin", "HOME": "/Users/owner", "LANG": "en_US.UTF-8",
            "TMPDIR": "/tmp/x", **DENIED_ENV}


async def run_fixture(name: str, clone: Path, out_path: Path, env: dict[str, str],
                      codex_bin: str, **kw):
    factory, calls = make_factory(fixture_bytes(name), **{
        k: kw.pop(k) for k in list(kw) if k in ("returncode", "write_output", "stderr",
                                                 "hang", "dies_on_term", "version")})
    sink = Sink()
    result = await codex_cli.run(
        JOB_ID, cwd=clone, prompt="do the thing", model_id=MODEL,
        sandbox="workspace-write", timeout_s=kw.pop("timeout_s", 30),
        on_event=sink, process_factory=factory, codex_bin=codex_bin,
        output_path=out_path, environ=env, **kw)
    return result, sink, calls


# ── argv builder ─────────────────────────────────────────────────────────────


def test_build_argv_every_flag(clone: Path, out_path: Path):
    argv = codex_cli.build_argv(
        codex_bin="/opt/codex", cwd=clone, prompt="PROMPT", model_id=MODEL,
        sandbox="workspace-write", output_path=out_path)
    assert argv == [
        "/opt/codex", "exec", "--json", "--ephemeral", "--ignore-user-config",
        "--skip-git-repo-check", "--sandbox", "workspace-write",
        "-C", str(clone), "-m", MODEL,
        "-c", "features.goals=false",
        "-c", "analytics.enabled=false",
        "-c", 'otel.metrics_exporter="none"',
        "-c", "sandbox_workspace_write.network_access=false",
        "-o", str(out_path),
        "PROMPT",
    ]
    # The prompt is the single trailing positional — never split, never a flag.
    assert argv[-1] == "PROMPT"


@pytest.mark.parametrize("mode", ["read-only", "workspace-write"])
def test_build_argv_sandbox_modes(clone: Path, out_path: Path, mode: str):
    argv = codex_cli.build_argv(codex_bin="/opt/codex", cwd=clone, prompt="p",
                                model_id=MODEL, sandbox=mode, output_path=out_path)
    assert argv[argv.index("--sandbox") + 1] == mode


@pytest.mark.parametrize("mode", ["danger-full-access", "", "full", "workspace_write"])
def test_build_argv_refuses_unknown_or_unsafe_sandbox(clone: Path, out_path: Path, mode: str):
    with pytest.raises(ValueError):
        codex_cli.build_argv(codex_bin="/opt/codex", cwd=clone, prompt="p",
                             model_id=MODEL, sandbox=mode, output_path=out_path)


def test_build_argv_run_as_user_prefix(clone: Path, out_path: Path):
    argv = codex_cli.build_argv(codex_bin="/opt/codex", cwd=clone, prompt="p",
                                model_id=MODEL, sandbox="read-only",
                                output_path=out_path, run_as_user="_aicodex")
    assert argv[:4] == ["sudo", "-n", "-u", "_aicodex"]
    sep = argv.index("--")
    assert argv[sep + 1] == "/opt/codex" and argv[sep + 2] == "exec"
    # sudoers env_reset strips everything else; the allowlist rides through.
    assert "--preserve-env=PATH,HOME,LANG,TMPDIR,CODEX_HOME" in argv[:sep]
    plain = codex_cli.build_argv(codex_bin="/opt/codex", cwd=clone, prompt="p",
                                 model_id=MODEL, sandbox="read-only",
                                 output_path=out_path)
    assert plain[0] == "/opt/codex" and "sudo" not in plain


def test_build_argv_rejects_empty_prompt_or_model(clone: Path, out_path: Path):
    with pytest.raises(ValueError):
        codex_cli.build_argv(codex_bin="/opt/codex", cwd=clone, prompt="  ",
                             model_id=MODEL, sandbox="read-only", output_path=out_path)
    # No `--` separator is passed (unverified on the recorded build), so a
    # prompt that would parse as a flag is refused instead (review 2026-10-21).
    for bad in ("-m gpt-6", "--sandbox danger-full-access", "  --help"):
        with pytest.raises(ValueError):
            codex_cli.build_argv(codex_bin="/opt/codex", cwd=clone, prompt=bad,
                                 model_id=MODEL, sandbox="read-only", output_path=out_path)
    ok = codex_cli.build_argv(codex_bin="/opt/codex", cwd=clone, prompt="fix the -m flag",
                              model_id=MODEL, sandbox="read-only", output_path=out_path)
    assert ok[-1] == "fix the -m flag"
    with pytest.raises(ValueError):
        codex_cli.build_argv(codex_bin="/opt/codex", cwd=clone, prompt="p",
                             model_id="", sandbox="read-only", output_path=out_path)


# ── env scrub ────────────────────────────────────────────────────────────────


def test_scrubbed_env_is_exactly_the_allowlist(base_env: dict[str, str]):
    env = codex_cli.scrubbed_env(base_env, codex_home="/Users/owner/.codex")
    assert set(env) == {"PATH", "HOME", "LANG", "TMPDIR", "CODEX_HOME"}
    assert set(env) <= set(codex_cli.ALLOWED_ENV_KEYS)
    for name in DENIED_ENV:
        assert name not in env
    assert not any(k.startswith(("ANTHROPIC_", "TELEGRAM_", "POSTGRES_", "ALPACA_",
                                 "TRADIER_", "FINNHUB_")) for k in env)
    assert env["PATH"] == "/usr/bin:/bin"
    assert env["HOME"] == "/Users/owner"
    assert env["CODEX_HOME"] == "/Users/owner/.codex"


def test_scrubbed_env_codex_home_precedence(base_env: dict[str, str]):
    # explicit argument > CODEX_HOME in the environ > ~/.codex under HOME
    assert codex_cli.scrubbed_env(base_env, codex_home="/srv/stream-0")["CODEX_HOME"] \
        == "/srv/stream-0"
    assert codex_cli.scrubbed_env({**base_env, "CODEX_HOME": "/env/home"})["CODEX_HOME"] \
        == "/env/home"
    assert codex_cli.scrubbed_env(base_env)["CODEX_HOME"] == "/Users/owner/.codex"


def test_scrubbed_env_home_and_tmpdir_overrides(base_env: dict[str, str]):
    env = codex_cli.scrubbed_env(base_env, codex_home="/srv/stream-0",
                                 home="/srv/stream-0", tmpdir="/srv/stream-0/tmp")
    assert env["HOME"] == "/srv/stream-0" and env["TMPDIR"] == "/srv/stream-0/tmp"
    assert env["CODEX_HOME"] == "/srv/stream-0"
    assert set(env) == {"PATH", "HOME", "LANG", "TMPDIR", "CODEX_HOME"}
    # without overrides the environ's values ride through unchanged
    plain = codex_cli.scrubbed_env(base_env)
    assert plain["HOME"] == "/Users/owner" and plain["TMPDIR"] == "/tmp/x"


def test_scrubbed_env_optional_keys_only_when_present():
    env = codex_cli.scrubbed_env({"HOME": "/Users/owner"})
    assert "LANG" not in env and "TMPDIR" not in env
    assert env["PATH"]  # launchd gives no PATH; a usable default is supplied
    assert env["HOME"] == "/Users/owner"
    assert "CODEX_HOME" in env


def test_scrubbed_env_never_reads_os_environ_secrets(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "leak")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "leak")
    env = codex_cli.scrubbed_env()  # default: os.environ
    assert "ANTHROPIC_API_KEY" not in env and "TELEGRAM_BOT_TOKEN" not in env
    assert set(env) <= set(codex_cli.ALLOWED_ENV_KEYS)


# ── binary discovery ─────────────────────────────────────────────────────────


def test_discover_binary_order(tmp_path: Path):
    configured = tmp_path / "codex"
    configured.write_text("#!/bin/sh\n")
    which_hits = {"codex": "/usr/local/bin/codex"}
    # 1. settings.codex_bin wins when it exists
    assert codex_cli.discover_binary(str(configured), which=which_hits.get,
                                     exists=lambda p: True) == str(configured)
    # 2. then PATH
    assert codex_cli.discover_binary("", which=which_hits.get,
                                     exists=lambda p: False) == "/usr/local/bin/codex"
    # 3. then the ChatGPT.app bundle
    assert codex_cli.discover_binary("", which=lambda n: None,
                                     exists=lambda p: p == codex_cli.BUNDLE_BIN) \
        == codex_cli.BUNDLE_BIN
    assert codex_cli.BUNDLE_BIN == \
        "/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex"
    # 4. nothing → fail closed
    with pytest.raises(codex_cli.CodexNotFound):
        codex_cli.discover_binary("", which=lambda n: None, exists=lambda p: False)
    # a configured path that does not exist is an error, not a fall-through
    with pytest.raises(codex_cli.CodexNotFound):
        codex_cli.discover_binary(str(tmp_path / "missing"), which=which_hits.get,
                                  exists=os.path.exists)


# ── event mapping (pure) ─────────────────────────────────────────────────────


def mapped(name: str) -> tuple[codex_cli.EventMapper, list[tuple[str, dict]]]:
    m = codex_cli.EventMapper(JOB_ID, model_id=MODEL, cli_version=VERSION_LINE,
                              env_keys=["CODEX_HOME", "HOME", "PATH"])
    out: list[tuple[str, dict]] = []
    for ev in fixture_events(name):
        out.extend(m.map(ev))
    return m, out


def test_map_ok_fixture_golden_kinds():
    m, out = mapped("ok.jsonl")
    assert [k for k, _ in out] == ["executor_started", "text", "turn_completed"]
    started = out[0][1]
    assert started == {"executor": "codex_cli",
                       "thread_id": "01a16019-ede8-73e0-aec7-444f3d42c81f",
                       "model": MODEL, "cli_version": VERSION_LINE,
                       "env_keys": ["CODEX_HOME", "HOME", "PATH"]}
    assert out[1][1] == {"text": "ok"}
    assert m.thread_id == "01a16019-ede8-73e0-aec7-444f3d42c81f"
    assert m.saw_turn_completed and m.terminal_reason is None
    assert m.last_agent_message == "ok"
    assert m.usage == {"input_tokens": 15407, "cache_read_input_tokens": 0,
                       "cache_creation_input_tokens": 0, "output_tokens": 5,
                       "reasoning_output_tokens": 0}


def test_map_command_and_file_fixture_golden_kinds_and_shapes():
    m, out = mapped("command_and_file.jsonl")
    assert [k for k, _ in out] == [
        "executor_started", "text",
        "tool_use", "tool_result",
        "tool_use", "tool_result",
        "text", "turn_completed",
    ]
    tu1 = out[2][1]
    assert tu1 == {"tool_name": "Bash", "tool_use_id": "item_1",
                   "input": {"command": "/bin/zsh -lc 'ls -la'"}}
    tr1 = out[3][1]
    assert tr1["tool_use_id"] == "item_1" and tr1["exit_code"] == 0
    assert tr1["is_error"] is False
    assert tr1["result_preview"].startswith("total 48\n")
    assert tr1["output"] == tr1["result_preview"]
    assert len(tr1["result_preview"]) <= 500 + 40  # 500 chars + the "... [n more]" tail
    tu2 = out[4][1]
    assert tu2["tool_name"] == "Bash" and tu2["tool_use_id"] == "item_2"
    assert "hello from codex" in tu2["input"]["command"]
    assert out[5][1] == {"tool_use_id": "item_2", "is_error": False, "exit_code": 0,
                         "result_preview": "", "output": ""}
    assert out[6][1]["text"].endswith("TASK_COMPLETE: wrote hello.txt")
    assert out[7][1] == {"usage": {
        "input_tokens": 47324, "cache_read_input_tokens": 31104,
        "cache_creation_input_tokens": 0, "output_tokens": 477,
        "reasoning_output_tokens": 0}}
    assert m.last_agent_message.endswith("TASK_COMPLETE: wrote hello.txt")


def test_map_file_change_and_failure_fixture():
    m, out = mapped("file_change_and_failure.jsonl")
    assert [k for k, _ in out] == [
        "executor_started", "thinking",
        "tool_use", "tool_result",              # web_search
        "tool_use", "tool_result",              # file_change: update
        "tool_use", "tool_result",              # file_change: add
        "text", "executor_error",
    ]
    assert out[1][1] == {"text": "Look up the asyncio subprocess API first, then edit "
                                 "the module and add a test."}
    ws = out[2][1]
    assert ws["tool_name"] == "WebSearch" and ws["tool_use_id"] == "item_1"
    assert ws["input"] == {"query": "python asyncio create_subprocess_exec stdin DEVNULL"}
    assert out[3][1]["tool_use_id"] == "item_1" and out[3][1]["is_error"] is False
    e1, e2 = out[4][1], out[6][1]
    assert e1 == {"tool_name": "Edit", "tool_use_id": "item_2",
                  "input": {"path": "src/example.py", "kind": "update"}}
    assert e2 == {"tool_name": "Edit", "tool_use_id": "item_2:1",
                  "input": {"path": "tests/test_example.py", "kind": "add"}}
    assert out[5][1]["tool_use_id"] == "item_2" and out[7][1]["tool_use_id"] == "item_2:1"
    assert out[5][1]["is_error"] is False
    err = out[9][1]
    assert err["terminal_reason"] == "rate_limited"
    assert "slow_down" in err["message"]
    assert m.terminal_reason == "rate_limited" and not m.saw_turn_completed


def test_map_tool_use_tool_result_shapes_are_the_existing_contract():
    """C14: downstream parsers read `tool_name`, `tool_use_id`, `input`
    (tool_use) and `tool_use_id`, `is_error`, `result_preview` (tool_result)."""
    _, out = mapped("command_and_file.jsonl")
    for kind, fields in out:
        if kind == "tool_use":
            assert {"tool_name", "tool_use_id", "input"} <= set(fields)
        if kind == "tool_result":
            assert {"tool_use_id", "is_error", "result_preview"} <= set(fields)


def test_map_command_completed_without_started_still_pairs():
    m = codex_cli.EventMapper(JOB_ID, model_id=MODEL, cli_version=None, env_keys=[])
    out = m.map({"type": "item.completed", "item": {
        "id": "item_9", "type": "command_execution", "command": "false",
        "aggregated_output": "", "exit_code": 1, "status": "failed"}})
    assert [k for k, _ in out] == ["tool_use", "tool_result"]
    assert out[1][1]["is_error"] is True and out[1][1]["exit_code"] == 1


def test_map_ignores_unknown_and_non_event_shapes():
    m = codex_cli.EventMapper(JOB_ID, model_id=MODEL, cli_version=None, env_keys=[])
    assert m.map({"type": "turn.started"}) == []
    assert m.map({"type": "item.started", "item": {"id": "x", "type": "agent_message"}}) == []
    assert m.map({"type": "item.completed", "item": {"id": "x", "type": "plan_update"}}) == []
    assert m.map({"type": "something.new"}) == []
    assert m.map({"nope": 1}) == []
    assert m.map("not a dict") == []  # type: ignore[arg-type]


def test_map_error_event_and_usage_accumulates_across_turns():
    m = codex_cli.EventMapper(JOB_ID, model_id=MODEL, cli_version=None, env_keys=[])
    m.map({"type": "turn.completed", "usage": {"input_tokens": 10, "output_tokens": 1}})
    m.map({"type": "turn.completed", "usage": {"input_tokens": 5, "cached_input_tokens": 2,
                                               "output_tokens": 2}})
    assert m.usage["input_tokens"] == 15 and m.usage["output_tokens"] == 3
    assert m.usage["cache_read_input_tokens"] == 2
    out = m.map({"type": "error", "message": "401 Unauthorized: please run codex login"})
    assert out == [("executor_error", {"terminal_reason": "auth_expired",
                                       "message": "401 Unauthorized: please run codex login"})]
    assert m.terminal_reason == "auth_expired"


def test_map_model_served_only_when_the_stream_reports_it():
    m = codex_cli.EventMapper(JOB_ID, model_id=MODEL, cli_version=None, env_keys=[])
    m.map({"type": "thread.started", "thread_id": "t"})
    assert m.model_served is None
    m.map({"type": "turn.completed", "usage": {}, "model": "gpt-6-luna-2026-10"})
    assert m.model_served == "gpt-6-luna-2026-10"


def test_map_usage():
    assert codex_cli.map_usage({
        "input_tokens": 1, "cached_input_tokens": 2, "cache_write_input_tokens": 3,
        "output_tokens": 4, "reasoning_output_tokens": 5}) == {
        "input_tokens": 1, "cache_read_input_tokens": 2, "cache_creation_input_tokens": 3,
        "output_tokens": 4, "reasoning_output_tokens": 5}
    assert codex_cli.map_usage({}) == {
        "input_tokens": 0, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0,
        "output_tokens": 0, "reasoning_output_tokens": 0}
    assert codex_cli.map_usage(None) == codex_cli.map_usage({})


@pytest.mark.parametrize("message,expected", [
    ("429 slow_down: You have hit your usage limit.", "rate_limited"),
    ("Error: slow_down", "rate_limited"),
    ("You've hit your usage limit. Try again later.", "rate_limited"),
    ("usage_limited", "rate_limited"),
    ("rate limit reached", "rate_limited"),
    ("HTTP 401 Unauthorized", "auth_expired"),
    ("Not logged in. Run `codex login` first.", "auth_expired"),
    ("refresh_token_reused", "auth_expired"),
    ("503 server_is_overloaded", "api_error"),
    ("model gpt-6-nope not found", "api_error"),
    ("", "api_error"),
    # word boundaries: bare tokens inside unrelated text must not classify
    ("140123 input tokens exceeded the context window", "api_error"),
    ("request id 4290-1 failed", "api_error"),
    ("plugin registry unavailable", "api_error"),
    ("catalogin failed", "api_error"),
    ("stream closed after 4015 ms", "api_error"),
])
def test_classify_error(message: str, expected: str):
    assert codex_cli.classify_error(message) == expected


# ── run(): end to end on fixtures, process factory injected ──────────────────


async def test_run_ok_fixture_end_to_end(clone: Path, out_path: Path, base_env, codex_bin):
    result, sink, calls = await run_fixture("ok.jsonl", clone, out_path, base_env, codex_bin)
    assert isinstance(result, codex_cli.ExecResult)
    assert result.terminal_reason == "ok"
    assert result.final_text == "ok"
    assert result.thread_id == "01a16019-ede8-73e0-aec7-444f3d42c81f"
    assert result.cli_version == VERSION_LINE
    # neither recorded fixture carries a `model` field: unobserved → None,
    # never the requested id (T4 stamps jobs.model_served from this alone)
    assert result.model_served is None
    assert result.usage["input_tokens"] == 15407 and result.usage["output_tokens"] == 5
    assert result.exit_code == 0 and result.error is None
    assert sink.kinds == ["executor_started", "text", "turn_completed"]
    assert sink.events[0][1]["env_keys"] == ["CODEX_HOME", "HOME", "LANG", "PATH", "TMPDIR"]

    # exactly one exec, run in the clone, with the scrubbed env
    assert len(calls["exec"]) == 1
    call = calls["exec"][0]
    assert call["cwd"] == str(clone)
    assert call["argv"][0] == codex_bin and call["argv"][1] == "exec"
    assert call["argv"][argv_index(call["argv"], "-C") + 1] == str(clone)
    assert call["argv"][argv_index(call["argv"], "-o") + 1] == str(out_path)
    assert set(call["env"]) == {"PATH", "HOME", "LANG", "TMPDIR", "CODEX_HOME"}
    for name in DENIED_ENV:
        assert name not in call["env"]
    # the version probe ran once, with the same scrubbed env
    assert len(calls["version"]) == 1
    assert calls["version"][0]["argv"] == [codex_bin, "--version"]
    assert set(calls["version"][0]["env"]) <= set(codex_cli.ALLOWED_ENV_KEYS)
    assert result.as_dict()["terminal_reason"] == "ok"


def argv_index(argv: list[str], flag: str) -> int:
    return argv.index(flag)


async def test_run_output_file_takes_precedence_over_last_message(clone, out_path, base_env, codex_bin):
    last_md = (FIXTURES / "command_and_file.last.md").read_text(encoding="utf-8")
    result, sink, calls = await run_fixture("command_and_file.jsonl", clone, out_path,
                                            base_env, codex_bin, write_output=last_md)
    assert result.final_text == last_md.strip()
    assert result.final_text.endswith("TASK_COMPLETE: wrote hello.txt")
    assert result.terminal_reason == "ok"
    assert sink.kinds.count("tool_use") == 2 and sink.kinds.count("tool_result") == 2
    assert result.usage == {"input_tokens": 47324, "cache_read_input_tokens": 31104,
                            "cache_creation_input_tokens": 0, "output_tokens": 477,
                            "reasoning_output_tokens": 0}


async def test_run_falls_back_to_last_agent_message_without_output_file(clone, out_path,
                                                                        base_env, codex_bin):
    result, _, _ = await run_fixture("command_and_file.jsonl", clone, out_path, base_env, codex_bin)
    assert not out_path.exists()
    assert result.final_text.endswith("TASK_COMPLETE: wrote hello.txt")
    assert result.final_text.startswith("`ls -la` output:")


async def test_run_empty_output_file_falls_back(clone, out_path, base_env, codex_bin):
    result, _, _ = await run_fixture("ok.jsonl", clone, out_path, base_env, codex_bin,
                                     write_output="   \n")
    assert result.final_text == "ok"


async def test_run_stale_output_file_from_earlier_attempt_is_ignored(clone, out_path,
                                                                     base_env, codex_bin):
    """Job ids are reused on requeue: a `-o` left by a previous attempt must
    not become this attempt's text of record (review 2026-10-21)."""
    out_path.parent.mkdir(parents=True)
    out_path.write_text("TASK_COMPLETE: stale\n", encoding="utf-8")
    result, _, _ = await run_fixture("file_change_and_failure.jsonl", clone, out_path,
                                     base_env, codex_bin, returncode=1)
    assert result.terminal_reason == "rate_limited"
    assert "stale" not in result.final_text
    assert result.final_text.startswith("Edited src/example.py")
    assert not out_path.exists()  # unlinked before the spawn


async def test_run_output_file_ignored_without_turn_completed(clone, out_path, base_env,
                                                              codex_bin):
    """Even a file written during THIS attempt is not the text of record
    unless a turn completed — codex writes `-o` at the end of a turn."""
    result, _, _ = await run_fixture("file_change_and_failure.jsonl", clone, out_path,
                                     base_env, codex_bin, returncode=1,
                                     write_output="TASK_COMPLETE: not really\n")
    assert result.terminal_reason == "rate_limited"
    assert result.final_text.startswith("Edited src/example.py")


async def test_run_sink_exception_terminates_the_child(clone, out_path, base_env, codex_bin):
    """`audit_log.append` can raise (full disk, permissions): the child must
    not be orphaned and `_running` must be clean afterwards."""

    class RaisingSink(Sink):
        async def __call__(self, kind, fields):
            await super().__call__(kind, fields)
            if len(self.events) == 2:
                raise OSError(28, "No space left on device")

    factory, calls = make_factory(fixture_bytes("command_and_file.jsonl"), hang=True,
                                  dies_on_term=False)
    sink = RaisingSink()
    with pytest.raises(OSError):
        await codex_cli.run(JOB_ID, cwd=clone, prompt="p", model_id=MODEL,
                            sandbox="workspace-write", timeout_s=30, on_event=sink,
                            process_factory=factory, codex_bin=codex_bin,
                            output_path=out_path, environ=base_env, kill_grace_s=0.05)
    assert calls["proc"].calls == ["terminate", "kill"]
    assert calls["proc"].returncode is not None
    assert JOB_ID not in codex_cli._running
    assert len(sink.events) == 2


async def test_run_turn_failed_sets_terminal_reason(clone, out_path, base_env, codex_bin):
    result, sink, _ = await run_fixture("file_change_and_failure.jsonl", clone, out_path,
                                        base_env, codex_bin, returncode=1)
    assert result.terminal_reason == "rate_limited"
    assert "slow_down" in (result.error or "")
    assert result.thread_id == "00000000-0000-7000-8000-00000000c0de"
    assert sink.kinds[-1] == "executor_error"
    # the partial text is still the text of record (fallback: last agent_message)
    assert result.final_text.startswith("Edited src/example.py")


async def test_run_nonzero_exit_without_turn_completed_is_api_error(clone, out_path,
                                                                    base_env, codex_bin):
    stdout = b'{"type":"thread.started","thread_id":"t-1"}\n{"type":"turn.started"}\n'
    factory, calls = make_factory(stdout, returncode=2, stderr=b"codex: boom\n")
    sink = Sink()
    result = await codex_cli.run(JOB_ID, cwd=clone, prompt="p", model_id=MODEL,
                                 sandbox="read-only", timeout_s=5, on_event=sink,
                                 process_factory=factory, codex_bin=codex_bin,
                                 output_path=out_path, environ=base_env)
    assert result.terminal_reason == "api_error"
    assert result.exit_code == 2
    assert "boom" in (result.error or "")
    assert sink.kinds == ["executor_started", "executor_error"]
    assert sink.events[-1][1]["terminal_reason"] == "api_error"


async def test_run_zero_exit_without_turn_completed_is_api_error(clone, out_path, base_env, codex_bin):
    """The silent-empty-success trap (old spec §2.4): no `turn.completed`
    means no work of record, whatever the exit code says."""
    stdout = b'{"type":"thread.started","thread_id":"t-1"}\n'
    factory, _ = make_factory(stdout, returncode=0)
    result = await codex_cli.run(JOB_ID, cwd=clone, prompt="p", model_id=MODEL,
                                 sandbox="read-only", timeout_s=5, on_event=Sink(),
                                 process_factory=factory, codex_bin=codex_bin,
                                 output_path=out_path, environ=base_env)
    assert result.terminal_reason == "api_error"
    assert "turn.completed" in (result.error or "")


async def test_run_skips_comment_and_garbage_lines(clone, out_path, base_env, codex_bin):
    stdout = (b"# header\n"
              b"not json at all\n"
              b'{"type":"thread.started","thread_id":"t-2"}\n'
              b"{broken json\n"
              b'{"type":"item.completed","item":{"id":"i","type":"agent_message","text":"hi"}}\n'
              b'{"type":"turn.completed","usage":{"input_tokens":1,"output_tokens":1}}\n')
    factory, _ = make_factory(stdout)
    sink = Sink()
    result = await codex_cli.run(JOB_ID, cwd=clone, prompt="p", model_id=MODEL,
                                 sandbox="read-only", timeout_s=5, on_event=sink,
                                 process_factory=factory, codex_bin=codex_bin,
                                 output_path=out_path, environ=base_env)
    assert result.terminal_reason == "ok" and result.final_text == "hi"
    assert sink.kinds == ["executor_started", "text", "turn_completed"]


async def test_run_timeout_sends_sigterm_then_sigkill(clone, out_path, base_env, codex_bin):
    assert codex_cli.KILL_GRACE_S == 1.5  # INV-8: SIGTERM, then SIGKILL after 1.5 s
    factory, calls = make_factory(
        b'{"type":"thread.started","thread_id":"t-3"}\n', hang=True, dies_on_term=False)
    sink = Sink()
    result = await codex_cli.run(JOB_ID, cwd=clone, prompt="p", model_id=MODEL,
                                 sandbox="read-only", timeout_s=0.05, on_event=sink,
                                 process_factory=factory, codex_bin=codex_bin,
                                 output_path=out_path, environ=base_env,
                                 kill_grace_s=0.05)
    proc = calls["proc"]
    assert proc.calls == ["terminate", "kill"]
    assert result.terminal_reason == "timeout"
    assert result.exit_code == -9
    assert sink.kinds[-1] == "executor_error"
    assert sink.events[-1][1]["terminal_reason"] == "timeout"
    assert JOB_ID not in codex_cli._running


async def test_run_timeout_sigterm_suffices_when_process_dies(clone, out_path, base_env, codex_bin):
    factory, calls = make_factory(b'{"type":"thread.started","thread_id":"t-4"}\n',
                                  hang=True, dies_on_term=True)
    result = await codex_cli.run(JOB_ID, cwd=clone, prompt="p", model_id=MODEL,
                                 sandbox="read-only", timeout_s=0.05, on_event=Sink(),
                                 process_factory=factory, codex_bin=codex_bin,
                                 output_path=out_path, environ=base_env,
                                 kill_grace_s=0.5)
    assert calls["proc"].calls == ["terminate"]
    assert result.terminal_reason == "timeout"


async def test_interrupt_running_job(clone, out_path, base_env, codex_bin):
    factory, calls = make_factory(b'{"type":"thread.started","thread_id":"t-5"}\n',
                                  hang=True, dies_on_term=False)
    task = asyncio.create_task(codex_cli.run(
        JOB_ID, cwd=clone, prompt="p", model_id=MODEL, sandbox="read-only",
        timeout_s=30, on_event=Sink(), process_factory=factory, codex_bin=codex_bin,
        output_path=out_path, environ=base_env))
    for _ in range(200):
        if JOB_ID in codex_cli._running:
            break
        await asyncio.sleep(0.005)
    assert JOB_ID in codex_cli._running
    assert await codex_cli.interrupt(JOB_ID, grace_s=0.05) is True
    result = await asyncio.wait_for(task, 5)
    assert calls["proc"].calls == ["terminate", "kill"]
    assert result.terminal_reason == "interrupted"
    assert JOB_ID not in codex_cli._running
    assert await codex_cli.interrupt(JOB_ID) is False
    assert await codex_cli.interrupt("never-ran") is False


async def test_run_cancellation_kills_the_process(clone, out_path, base_env, codex_bin):
    """`main._process_job`'s `wait_for` cancels the session task on the job
    timeout; the child must not outlive it."""
    factory, calls = make_factory(b'{"type":"thread.started","thread_id":"t-6"}\n',
                                  hang=True, dies_on_term=False)
    task = asyncio.create_task(codex_cli.run(
        JOB_ID, cwd=clone, prompt="p", model_id=MODEL, sandbox="read-only",
        timeout_s=30, on_event=Sink(), process_factory=factory, codex_bin=codex_bin,
        output_path=out_path, environ=base_env, kill_grace_s=0.05))
    for _ in range(200):
        if JOB_ID in codex_cli._running:
            break
        await asyncio.sleep(0.005)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert calls["proc"].calls == ["terminate", "kill"]
    assert calls["proc"].returncode is not None
    assert JOB_ID not in codex_cli._running


async def test_run_refuses_bad_inputs_before_any_process(tmp_path, out_path, base_env, codex_bin):
    factory, calls = make_factory(fixture_bytes("ok.jsonl"))
    common = dict(prompt="p", model_id=MODEL, timeout_s=5, on_event=Sink(),
                  process_factory=factory, codex_bin=codex_bin,
                  output_path=out_path, environ=base_env)
    with pytest.raises(ValueError):
        await codex_cli.run(JOB_ID, cwd=tmp_path / "missing", sandbox="read-only", **common)
    clone = tmp_path / "c"
    clone.mkdir()
    with pytest.raises(ValueError):
        await codex_cli.run(JOB_ID, cwd=clone, sandbox="danger-full-access", **common)
    with pytest.raises(ValueError):
        await codex_cli.run(JOB_ID, cwd=clone, sandbox="read-only",
                            **{**common, "prompt": ""})
    with pytest.raises(ValueError):
        await codex_cli.run(JOB_ID, cwd=clone, sandbox="read-only",
                            **{**common, "timeout_s": 0})
    assert calls["exec"] == [] and calls["version"] == []


async def test_run_missing_binary_fails_closed(clone, out_path, base_env, monkeypatch):
    factory, calls = make_factory(fixture_bytes("ok.jsonl"))
    monkeypatch.setattr(codex_cli, "discover_binary",
                        lambda *a, **k: (_ for _ in ()).throw(codex_cli.CodexNotFound("x")))
    with pytest.raises(codex_cli.CodexNotFound):
        await codex_cli.run(JOB_ID, cwd=clone, prompt="p", model_id=MODEL,
                            sandbox="read-only", timeout_s=5, on_event=Sink(),
                            process_factory=factory, output_path=out_path,
                            environ=base_env)
    assert calls["exec"] == []


async def test_run_reads_settings_for_bin_home_and_run_as_user(clone, out_path, base_env,
                                                               tmp_path, monkeypatch):
    bin_path = tmp_path / "codex"
    bin_path.write_text("#!/bin/sh\n")
    monkeypatch.setattr(settings, "codex_bin", str(bin_path))
    monkeypatch.setattr(settings, "codex_home", str(tmp_path / "stream-0"))
    monkeypatch.setattr(settings, "codex_run_as_user", "_aicodex")
    factory, calls = make_factory(fixture_bytes("ok.jsonl"))
    result = await codex_cli.run(JOB_ID, cwd=clone, prompt="p", model_id=MODEL,
                                 sandbox="workspace-write", timeout_s=5, on_event=Sink(),
                                 process_factory=factory, output_path=out_path,
                                 environ=base_env)
    assert result.terminal_reason == "ok"
    argv = calls["exec"][0]["argv"]
    assert argv[:4] == ["sudo", "-n", "-u", "_aicodex"]
    assert argv[argv.index("--") + 1] == str(bin_path)
    assert calls["exec"][0]["env"]["CODEX_HOME"] == str(tmp_path / "stream-0")
    # the version probe never goes through sudo
    assert calls["version"][0]["argv"] == [str(bin_path), "--version"]


async def test_run_as_user_never_forwards_owner_home_or_tmpdir(clone, out_path, base_env,
                                                               tmp_path, codex_bin):
    """D-C: under `sudo -u <user> --preserve-env=...` the child must get the
    stream home, not the owner's HOME (login) or TMPDIR (0700 /var/folders)."""
    stream = tmp_path / "stream-0"
    factory, calls = make_factory(fixture_bytes("ok.jsonl"))
    result = await codex_cli.run(JOB_ID, cwd=clone, prompt="p", model_id=MODEL,
                                 sandbox="workspace-write", timeout_s=5, on_event=Sink(),
                                 process_factory=factory, codex_bin=codex_bin,
                                 output_path=out_path, environ=base_env,
                                 run_as_user="_aicodex", codex_home=str(stream))
    assert result.terminal_reason == "ok"
    env = calls["exec"][0]["env"]
    assert env["HOME"] == str(stream)
    assert env["TMPDIR"] == str(stream / "tmp")
    assert env["CODEX_HOME"] == str(stream)
    assert env["HOME"] != base_env["HOME"] and env["TMPDIR"] != base_env["TMPDIR"]
    assert set(env) == {"PATH", "HOME", "LANG", "TMPDIR", "CODEX_HOME"}
    assert calls["exec"][0]["argv"][:4] == ["sudo", "-n", "-u", "_aicodex"]


async def test_run_as_user_requires_a_stream_home(clone, out_path, base_env, codex_bin,
                                                  monkeypatch):
    monkeypatch.setattr(settings, "codex_home", "")
    factory, calls = make_factory(fixture_bytes("ok.jsonl"))
    with pytest.raises(ValueError):
        await codex_cli.run(JOB_ID, cwd=clone, prompt="p", model_id=MODEL,
                            sandbox="workspace-write", timeout_s=5, on_event=Sink(),
                            process_factory=factory, codex_bin=codex_bin,
                            output_path=out_path, environ=base_env,
                            run_as_user="_aicodex", codex_home="")
    assert calls["exec"] == [] and calls["version"] == []


async def test_run_version_probe_failure_is_not_fatal(clone, out_path, base_env, codex_bin):
    result, sink, _ = await run_fixture("ok.jsonl", clone, out_path, base_env, codex_bin, version=None)
    assert result.terminal_reason == "ok" and result.cli_version is None
    assert sink.events[0][1]["cli_version"] is None


async def test_probe_cli_version_terminates_a_hung_probe(clone, monkeypatch):
    monkeypatch.setattr(codex_cli.asyncio, "wait_for", _fast_wait_for)
    proc = FakeProc(b"", hang=True, dies_on_term=True)

    async def factory(argv, *, cwd, env):
        return proc

    assert await codex_cli.probe_cli_version("/opt/codex", factory, {}, cwd=str(clone)) is None
    assert proc.calls == ["terminate"] and proc.returncode is not None


async def _fast_wait_for(aw, timeout):
    """`asyncio.wait_for` with the 15 s probe timeouts shrunk to 50 ms."""
    return await _real_wait_for(aw, min(timeout, 0.05))


_real_wait_for = asyncio.wait_for


def test_settings_default_sandbox_and_run_as_user():
    assert settings.codex_sandbox_default == "workspace-write"
    assert isinstance(settings.codex_run_as_user, str)


# ── the real process factory and the default audit/stream sink ───────────────


async def test_default_process_factory_uses_devnull_stdin_and_pipes(monkeypatch, clone):
    captured: dict = {}

    async def fake_create(*argv, **kwargs):
        captured["argv"] = list(argv)
        captured.update(kwargs)
        return FakeProc(b"")

    monkeypatch.setattr(codex_cli, "_create_subprocess", fake_create)
    proc = await codex_cli._default_process_factory(["/opt/codex", "exec"], cwd=str(clone),
                                                    env={"PATH": "/usr/bin"})
    assert isinstance(proc, FakeProc)
    assert captured["argv"] == ["/opt/codex", "exec"]
    assert captured["stdin"] is asyncio.subprocess.DEVNULL  # 4d: a piped stdin blocks exec
    assert captured["stdout"] is asyncio.subprocess.PIPE
    assert captured["stderr"] is asyncio.subprocess.PIPE
    assert captured["cwd"] == str(clone)
    assert captured["env"] == {"PATH": "/usr/bin"}
    assert captured["limit"] >= 1024 * 1024  # long aggregated_output lines must not overrun


async def test_default_sink_audits_and_streams(monkeypatch):
    audited: list[tuple] = []
    published: list[tuple[str, str]] = []

    def fake_append(job_id, kind, **fields):
        audited.append((str(job_id), kind, fields))

    class FakeRedis:
        async def publish(self, channel, body):
            published.append((channel, body))

    monkeypatch.setattr(codex_cli.audit_log, "append", fake_append)
    monkeypatch.setattr(codex_cli, "redis", FakeRedis())
    sink = codex_cli.default_sink(JOB_ID)
    await sink("text", {"text": "hello"})
    await sink("tool_use", {"tool_name": "Bash", "tool_use_id": "item_1",
                            "input": {"command": "ls"}})
    await sink("tool_result", {"tool_use_id": "item_1", "is_error": False, "exit_code": 0,
                               "result_preview": "x" * 500, "output": "x" * 500})
    await sink("thinking", {"text": "secret-ish reasoning"})
    await sink("executor_started", {"executor": "codex_cli", "thread_id": "t"})

    assert [(k, f) for _, k, f in audited] == [
        ("text", {"text": "hello"}),
        ("tool_use", {"tool_name": "Bash", "tool_use_id": "item_1", "input": {"command": "ls"}}),
        ("tool_result", {"tool_use_id": "item_1", "is_error": False, "exit_code": 0,
                         "result_preview": "x" * 500, "output": "x" * 500}),
        ("thinking", {"text": "secret-ish reasoning"}),
        ("executor_started", {"executor": "codex_cli", "thread_id": "t"}),
    ]
    assert all(c == f"jobs:stream:{JOB_ID}" for c, _ in published)
    bodies = [json.loads(b) for _, b in published]
    assert bodies[0] == {"kind": "text", "text": "hello"}
    assert bodies[1] == {"kind": "tool_use", "tool_name": "Bash", "tool_use_id": "item_1"}
    assert bodies[2] == {"kind": "tool_result", "tool_use_id": "item_1", "is_error": False,
                         "exit_code": 0}
    assert bodies[3] == {"kind": "thinking"}
    assert bodies[4] == {"kind": "executor_started", "executor": "codex_cli", "thread_id": "t"}


async def test_default_sink_stream_failure_is_swallowed(monkeypatch):
    monkeypatch.setattr(codex_cli.audit_log, "append", lambda *a, **k: None)

    class Broken:
        async def publish(self, *a):
            raise ConnectionError("redis down")

    monkeypatch.setattr(codex_cli, "redis", Broken())
    await codex_cli.default_sink(JOB_ID)("text", {"text": "still audited"})


# ── no network, no subprocess, no SDK — the test module itself ───────────────


def test_this_module_never_spawns_a_real_process():
    src = Path(__file__).read_text(encoding="utf-8")
    banned = ("import " + "subprocess", "claude_agent" + "_sdk", "shutil." + "which(")
    for needle in banned:
        assert needle not in src, needle
