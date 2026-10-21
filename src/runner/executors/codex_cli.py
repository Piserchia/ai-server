"""
Codex CLI executor — `codex exec --json` as the first non-Anthropic writer
(cross-vendor writer slice T3, 2026-10-21; plan §4c-§4f/§4i and §5 T3; old
spec §2.4 JSONL mapping, §2.6 containment table + EnvScrubber contract).

What this module does
---------------------
One `codex exec` process per job, in the job's per-job workspace clone
(`cwd`), under Codex's own Seatbelt (`--sandbox read-only|workspace-write`,
network off), with an environment scrubbed down to exactly
`{PATH, HOME, LANG, TMPDIR, CODEX_HOME}` so no server, vendor, broker or
Telegram secret can reach the child. The JSONL stream is mapped line by line
onto the audit log + the `jobs:stream:<id>` channel using the EXISTING audit
kinds (C14), so every downstream parser treats a Codex job like a Claude job:

    thread.started                      → executor_started{executor, thread_id,
                                                           model, cli_version, env_keys}
    item.started   command_execution    → tool_use{tool_name:"Bash", tool_use_id, input:{command}}
    item.completed command_execution    → tool_result{tool_use_id, is_error, result_preview,
                                                      exit_code, output}
    item.completed agent_message        → text{text}
    item.completed reasoning            → thinking{text}
    item.completed file_change          → tool_use{tool_name:"Edit", input:{path, kind}} + tool_result
    item.completed web_search           → tool_use{tool_name:"WebSearch", input:{query}} + tool_result
    turn.completed                      → turn_completed{usage}   (usage keys renamed to the SDK's)
    turn.failed / error                 → executor_error{terminal_reason, message}

New kinds added, none renamed or reshaped (`audit_log.py` docstring).

What it deliberately does NOT do
--------------------------------
- Never commits, pushes or holds git credentials (plan §4b: the runner
  commits after the T5 Anthropic review gate).
- Never writes `AGENTS.md` into the clone (§4h: it would be committed); the
  system prompt is prepended to the prompt string by the caller.
- Never reads a piped stdin (§4d: `codex exec` blocks on it) — `stdin=DEVNULL`.
- Never honours the owner's `~/.codex/config.toml` (§4e: `--ignore-user-config`
  plus explicit `-c` overrides: goals off, analytics off, OTEL metrics off,
  workspace-write network off).
- Never allows `--sandbox danger-full-access`.
- Never runs more than one stream per login (§4f: the session/queue keep
  codex concurrency at 1; this module has no pool).

Invocation (flags verified on the bundled 0.162.0-alpha.17.2 build):

    <codex_bin> exec --json --ephemeral --ignore-user-config --skip-git-repo-check
        --sandbox <mode> -C <clone> -m <model_id>
        -c features.goals=false -c analytics.enabled=false
        -c otel.metrics_exporter="none" -c sandbox_workspace_write.network_access=false
        -o <output_path> "<prompt>"

With `settings.codex_run_as_user` (env `CODEX_RUN_AS_USER`) set, the argv is
prefixed `sudo -n -u <user> --preserve-env=<allowlist> --` (D-C; the sudoers
line is owner work and unset by default). In that mode `codex_home` is
REQUIRED and becomes the stream home: `HOME=<codex_home>`,
`TMPDIR=<codex_home>/tmp`, `CODEX_HOME=<codex_home>` — the owner's HOME and
TMPDIR are never forwarded to the unprivileged user (old spec §2.4/§2.6).
What this does NOT yet deliver (review 2026-10-21): the per-job clone under
`volumes/workspaces/` is `drwx------` to the owner, so an unprivileged user
cannot open `-C <clone>` until a tracked-files materialisation step exists.
D-C therefore stays an owner-gated residual (plan §6) even with this prefix.

Testing: `run()` takes a `process_factory` so the whole path — argv, env,
stream parsing, `-o` precedence, timeout → SIGTERM → SIGKILL, interrupt — is
exercised on the fixtures under tests/fixtures/codex/ with no live process.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable

import structlog

from src import audit_log
from src.config import settings
from src.db import CHANNEL_JOB_STREAM, redis

logger = structlog.get_logger(__name__)

EXECUTOR_NAME = "codex_cli"

#: The only environment variables the child ever sees (old spec §2.6 EnvScrubber).
ALLOWED_ENV_KEYS: tuple[str, ...] = ("PATH", "HOME", "LANG", "TMPDIR", "CODEX_HOME")

#: Where the ChatGPT.app bundle ships the CLI (not on PATH; launchd's PATH is frozen).
BUNDLE_BIN = "/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex"

#: Seatbelt modes this executor will pass. `danger-full-access` is refused.
SANDBOX_MODES: frozenset[str] = frozenset({"read-only", "workspace-write"})

#: `-c key=value` overrides (plan §4e). Containment, not convenience: goals
#: off (no automatic continuation loop), analytics off, OTEL metrics off (the
#: default phones home to statsig), and workspace-write network off.
CONFIG_OVERRIDES: tuple[str, ...] = (
    "features.goals=false",
    "analytics.enabled=false",
    'otel.metrics_exporter="none"',
    "sandbox_workspace_write.network_access=false",
)

#: INV-8: SIGTERM, then SIGKILL this many seconds later.
KILL_GRACE_S = 1.5

#: Fallback PATH when the runner's own environment has none (launchd).
_DEFAULT_PATH = "/usr/bin:/bin:/usr/sbin:/sbin"

#: Longest JSONL line we accept from the stream (`aggregated_output` of a
#: chatty command can run to megabytes; the StreamReader default is 64 KiB).
_STREAM_LINE_LIMIT = 16 * 1024 * 1024

_PREVIEW_LIMIT = 500
_STDERR_KEEP = 4000
#: After stdout EOF: how long to wait for stderr, then for the exit status,
#: before treating the process as wedged and killing it.
_STDERR_DRAIN_S = 5.0
_EXIT_WAIT_S = 15.0

TERMINAL_REASONS: frozenset[str] = frozenset({
    "ok", "rate_limited", "auth_expired", "api_error", "timeout", "interrupted",
})


class CodexNotFound(FileNotFoundError):
    """No usable `codex` binary: not configured, not on PATH, not in the bundle."""


@dataclass
class ExecResult:
    """`model_served` is the id the STREAM reported (`thread.started` /
    `turn.completed` `model`), or None when the stream never said — it is
    never defaulted to the requested `model_id`, so `jobs.model_served` (T4)
    only ever carries an observed value (old spec §2.5)."""
    final_text: str
    usage: dict[str, int]
    terminal_reason: str
    model_served: str | None
    thread_id: str | None
    cli_version: str | None
    exit_code: int | None = None
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


OnEvent = Callable[[str, dict[str, Any]], Awaitable[None]]


# ── binary discovery (plan §4c) ──────────────────────────────────────────────


def discover_binary(configured: str = "", *, which=shutil.which,
                    exists=os.path.exists) -> str:
    """`settings.codex_bin` → `shutil.which("codex")` → the ChatGPT.app bundle.

    A configured path that does not exist is an error, never a fall-through:
    the owner pinned it, so silently running a different binary would be a
    containment surprise. Pure given `which`/`exists`.
    """
    configured = (configured or "").strip()
    if configured:
        if exists(configured):
            return configured
        raise CodexNotFound(f"settings.codex_bin={configured!r} does not exist")
    found = which("codex")
    if found:
        return found
    if exists(BUNDLE_BIN):
        return BUNDLE_BIN
    raise CodexNotFound(
        "no codex binary: set CODEX_BIN, put `codex` on PATH, or install the "
        f"ChatGPT app ({BUNDLE_BIN})")


# ── env scrub (old spec §2.6 EnvScrubber contract) ───────────────────────────


def scrubbed_env(environ: dict[str, str] | None = None, *, codex_home: str = "",
                 home: str | None = None, tmpdir: str | None = None) -> dict[str, str]:
    """Child environment: exactly the allowlist, nothing inherited beyond it.

    PATH and HOME get usable defaults when the runner has none (launchd);
    LANG and TMPDIR ride through only when present; CODEX_HOME is always set
    (`codex_home` argument > environ CODEX_HOME > `$HOME/.codex`, the existing
    login — plan §4f). `home`/`tmpdir` override what the environ carries —
    the run-as-user path passes the stream home for both so the owner's
    HOME/TMPDIR never reach the child. Pure given `environ`.
    """
    src = os.environ if environ is None else environ
    env: dict[str, str] = {}
    env["PATH"] = src.get("PATH") or _DEFAULT_PATH
    env["HOME"] = home or src.get("HOME") or str(Path.home())
    for key, override in (("LANG", None), ("TMPDIR", tmpdir)):
        val = override or src.get(key)
        if val:
            env[key] = val
    env["CODEX_HOME"] = (codex_home or "").strip() or src.get("CODEX_HOME") \
        or str(Path(env["HOME"]) / ".codex")
    assert set(env) <= set(ALLOWED_ENV_KEYS)
    return env


# ── argv builder (plan T3 "Invocation") ──────────────────────────────────────


def build_argv(*, codex_bin: str, cwd: Path | str, prompt: str, model_id: str,
               sandbox: str, output_path: Path | str, run_as_user: str = "") -> list[str]:
    """The exact `codex exec` command line. Pure.

    Raises `ValueError` on an unsupported sandbox mode (fail closed), an empty
    prompt, a prompt that begins with `-` (clap would parse it as a flag; no
    `--` separator is used because none was verified on the recorded build —
    T10 may verify one) or an empty model id. The prompt is the single
    trailing positional.
    """
    if sandbox not in SANDBOX_MODES:
        raise ValueError(f"sandbox {sandbox!r} not allowed; one of {sorted(SANDBOX_MODES)}")
    if not (prompt or "").strip():
        raise ValueError("empty prompt")
    if prompt.lstrip().startswith("-"):
        raise ValueError("prompt must not begin with '-' (would be parsed as a flag)")
    if not (model_id or "").strip():
        raise ValueError("empty model id")
    if not (codex_bin or "").strip():
        raise ValueError("empty codex binary path")
    argv: list[str] = []
    if run_as_user:
        argv += ["sudo", "-n", "-u", run_as_user,
                 "--preserve-env=" + ",".join(ALLOWED_ENV_KEYS), "--"]
    argv += [
        codex_bin, "exec", "--json", "--ephemeral", "--ignore-user-config",
        "--skip-git-repo-check", "--sandbox", sandbox,
        "-C", str(cwd), "-m", model_id,
    ]
    for override in CONFIG_OVERRIDES:
        argv += ["-c", override]
    argv += ["-o", str(output_path), prompt]
    return argv


# ── usage + error classification ─────────────────────────────────────────────

_USAGE_KEYS: tuple[tuple[str, str], ...] = (
    # (codex `turn.completed.usage` key, SDK usage key the ledger already reads)
    ("input_tokens", "input_tokens"),
    ("cached_input_tokens", "cache_read_input_tokens"),
    ("cache_write_input_tokens", "cache_creation_input_tokens"),
    ("output_tokens", "output_tokens"),
    ("reasoning_output_tokens", "reasoning_output_tokens"),
)


def map_usage(usage: dict[str, Any] | None) -> dict[str, int]:
    """`turn.completed.usage` → the SDK's key names (so `job_completed.usage`
    and the budget ledger read both providers identically). Pure; missing or
    non-integer counts become 0."""
    usage = usage or {}
    out: dict[str, int] = {}
    for src_key, dst_key in _USAGE_KEYS:
        val = usage.get(src_key, 0)
        out[dst_key] = int(val) if isinstance(val, (int, float)) and not isinstance(val, bool) else 0
    return out


# Word-bounded where a bare token would otherwise match inside unrelated text
# ("140123 input tokens" is not a 401; "plugin" is not a login): T6 parks the
# lane or prints `codex login` guidance on these classes, so false positives
# cost real behaviour.
_RATE_LIMIT_RE = re.compile(
    r"\b429\b|slow_down|usage[ _]limit|rate[ _]limit|too many requests")
_AUTH_RE = re.compile(
    r"\b401\b|\blog(?:ged)?[ _-]?in\b|refresh_token|unauthori[sz]ed|"
    r"not authenticated|authentication failed")


def classify_error(message: str) -> str:
    """Vendor error text → `terminal_reason ∈ {rate_limited, auth_expired,
    api_error}` (plan T3 event mapping). Pure; unknown → `api_error`."""
    m = (message or "").lower()
    if _RATE_LIMIT_RE.search(m):
        return "rate_limited"
    if _AUTH_RE.search(m):
        return "auth_expired"
    return "api_error"


def _error_text(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("message", "error", "detail", "code"):
            if isinstance(value.get(key), str) and value[key]:
                return value[key]
        return json.dumps(value, default=str)[:_STDERR_KEEP]
    return str(value or "")


def _preview(text: Any, limit: int = _PREVIEW_LIMIT) -> str:
    s = text if isinstance(text, str) else ("" if text is None else str(text))
    return s[:limit] + (f"... [{len(s) - limit} more]" if len(s) > limit else "")


# ── JSONL → audit-kind mapper (pure, stateful per run) ───────────────────────


class EventMapper:
    """Maps one `codex exec --json` stream onto audit `(kind, fields)` pairs.

    Stateful only for what the stream itself requires: which tool ids have
    had their `tool_use` emitted, the thread id, accumulated usage, the last
    `agent_message` (the fallback text of record) and the terminal reason
    once a `turn.failed`/`error` arrives. `map()` never raises on a shape it
    does not know — unknown event or item types are ignored.
    """

    def __init__(self, job_id: str, *, model_id: str, cli_version: str | None,
                 env_keys: list[str]):
        self.job_id = job_id
        self.model_id = model_id
        self.cli_version = cli_version
        self.env_keys = list(env_keys)
        self.thread_id: str | None = None
        self.model_served: str | None = None
        self.usage: dict[str, int] = map_usage({})
        self.saw_turn_completed = False
        self.terminal_reason: str | None = None
        self.error_message: str | None = None
        self.last_agent_message: str = ""
        self._seen_tool_ids: set[str] = set()

    def map(self, event: Any) -> list[tuple[str, dict[str, Any]]]:
        if not isinstance(event, dict):
            return []
        etype = event.get("type")
        if etype == "thread.started":
            self.thread_id = event.get("thread_id") or self.thread_id
            if isinstance(event.get("model"), str):
                self.model_served = event["model"]
            return [("executor_started", {
                "executor": EXECUTOR_NAME,
                "thread_id": self.thread_id,
                "model": self.model_id,
                "cli_version": self.cli_version,
                "env_keys": self.env_keys,
            })]
        if etype == "turn.completed":
            turn = map_usage(event.get("usage"))
            for k, v in turn.items():
                self.usage[k] = self.usage.get(k, 0) + v
            self.saw_turn_completed = True
            if isinstance(event.get("model"), str):
                self.model_served = event["model"]
            return [("turn_completed", {"usage": turn})]
        if etype in ("turn.failed", "error"):
            message = _error_text(event.get("error") if etype == "turn.failed"
                                  else event.get("message", event.get("error")))
            reason = classify_error(message)
            self.terminal_reason = reason
            self.error_message = message
            return [("executor_error", {"terminal_reason": reason, "message": message})]
        if etype in ("item.started", "item.completed"):
            item = event.get("item")
            if not isinstance(item, dict):
                return []
            return self._map_item(etype == "item.completed", item)
        return []

    # ── items ─────────────────────────────────────────────────────────────

    def _map_item(self, completed: bool, item: dict[str, Any]) -> list[tuple[str, dict]]:
        itype = item.get("type")
        item_id = str(item.get("id") or "")
        if itype == "command_execution":
            return self._map_command(completed, item_id, item)
        if not completed:
            return []
        if itype == "agent_message":
            text = item.get("text")
            if not isinstance(text, str):
                return []
            self.last_agent_message = text
            return [("text", {"text": text})]
        if itype == "reasoning":
            text = item.get("text")
            return [("thinking", {"text": text})] if isinstance(text, str) else []
        if itype == "file_change":
            return self._map_file_change(item_id, item)
        if itype == "web_search":
            query = item.get("query")
            return [
                ("tool_use", {"tool_name": "WebSearch", "tool_use_id": item_id,
                              "input": {"query": query}}),
                ("tool_result", {"tool_use_id": item_id, "is_error": False,
                                 "result_preview": _preview(item.get("results", ""))}),
            ]
        return []  # mcp_tool_call, plan_update, todo_list, …: nothing to audit yet

    def _map_command(self, completed: bool, item_id: str,
                     item: dict[str, Any]) -> list[tuple[str, dict]]:
        out: list[tuple[str, dict]] = []
        if item_id not in self._seen_tool_ids:
            self._seen_tool_ids.add(item_id)
            out.append(("tool_use", {"tool_name": "Bash", "tool_use_id": item_id,
                                     "input": {"command": item.get("command")}}))
        if completed:
            exit_code = item.get("exit_code")
            status = item.get("status")
            is_error = (exit_code not in (0, None)) or status in ("failed", "error")
            preview = _preview(item.get("aggregated_output", ""))
            out.append(("tool_result", {
                "tool_use_id": item_id,
                "is_error": bool(is_error),
                "exit_code": exit_code,
                "result_preview": preview,
                "output": preview,
            }))
        return out

    def _map_file_change(self, item_id: str, item: dict[str, Any]) -> list[tuple[str, dict]]:
        changes = item.get("changes")
        if not isinstance(changes, list):
            changes = [item] if item.get("path") else []
        out: list[tuple[str, dict]] = []
        for i, change in enumerate(changes):
            if not isinstance(change, dict):
                continue
            path, kind = change.get("path"), change.get("kind")
            tool_use_id = item_id if i == 0 else f"{item_id}:{i}"
            out.append(("tool_use", {"tool_name": "Edit", "tool_use_id": tool_use_id,
                                     "input": {"path": path, "kind": kind}}))
            out.append(("tool_result", {"tool_use_id": tool_use_id, "is_error": False,
                                        "result_preview": f"{kind} {path}"}))
        return out


# ── default sink: audit log + jobs:stream (mirrors session._handle_message) ──

_STREAM_FIELDS: dict[str, tuple[str, ...]] = {
    "text": ("text",),
    "tool_use": ("tool_name", "tool_use_id"),
    "tool_result": ("tool_use_id", "is_error", "exit_code"),
    "thinking": (),
}


def _stream_view(kind: str, fields: dict[str, Any]) -> dict[str, Any]:
    keep = _STREAM_FIELDS.get(kind)
    if keep is None:
        return {"kind": kind, **fields}
    return {"kind": kind, **{k: fields[k] for k in keep if k in fields}}


def default_sink(job_id: str) -> OnEvent:
    """Audit every event under the job and publish a compact view on
    `jobs:stream:<id>` — the same two sinks `session._handle_message` feeds,
    so the dashboard SSE and the Telegram stream see a Codex job live."""

    async def on_event(kind: str, fields: dict[str, Any]) -> None:
        audit_log.append(job_id, kind, **fields)
        try:
            await redis.publish(f"{CHANNEL_JOB_STREAM}:{job_id}",
                                json.dumps(_stream_view(kind, fields), default=str))
        except Exception as exc:  # noqa: BLE001 — streaming is best-effort, never silent
            logger.debug("stream publish failed", job_id=job_id[:8], error=str(exc))

    return on_event


# ── process plumbing ─────────────────────────────────────────────────────────

_create_subprocess = asyncio.create_subprocess_exec


async def _default_process_factory(argv: list[str], *, cwd: str, env: dict[str, str]):
    """The real thing: `stdin=DEVNULL` always (plan §4d — a piped stdin is
    read as extra instructions and blocks `exec` until EOF), stdout/stderr
    piped, a line limit that survives a multi-megabyte `aggregated_output`."""
    return await _create_subprocess(
        *argv, cwd=cwd, env=env,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        limit=_STREAM_LINE_LIMIT,
    )


ProcessFactory = Callable[..., Awaitable[Any]]

#: job_id → running process (for `interrupt`); job ids interrupted on purpose.
_running: dict[str, Any] = {}
_interrupted: set[str] = set()


async def _terminate(proc: Any, grace_s: float) -> None:
    """INV-8: SIGTERM, wait `grace_s`, SIGKILL. Idempotent on a dead process."""
    if proc.returncode is not None:
        return
    try:
        proc.terminate()
    except ProcessLookupError:
        return
    try:
        await asyncio.wait_for(asyncio.shield(proc.wait()), grace_s)
        return
    except asyncio.TimeoutError:
        pass
    try:
        proc.kill()
    except ProcessLookupError:
        return
    await proc.wait()


async def interrupt(job_id: str, *, grace_s: float = KILL_GRACE_S) -> bool:
    """Stop a running Codex job (cancel listener / INV-8). SIGTERM, then
    SIGKILL after `grace_s`. Returns False when no such process is running."""
    proc = _running.get(str(job_id))
    if proc is None:
        return False
    _interrupted.add(str(job_id))
    await _terminate(proc, grace_s)
    return True


async def _drain(stream: Any, buf: list[str], keep: int = _STDERR_KEEP) -> None:
    if stream is None:
        return
    while True:
        chunk = await stream.readline()
        if not chunk:
            return
        buf.append(chunk.decode("utf-8", "replace"))
        total = sum(len(s) for s in buf)
        while len(buf) > 1 and total > keep:
            total -= len(buf.pop(0))


async def _consume(proc: Any, mapper: EventMapper, on_event: OnEvent,
                   stderr_buf: list[str]) -> None:
    stderr_task = asyncio.create_task(_drain(proc.stderr, stderr_buf))
    try:
        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            text = line.decode("utf-8", "replace").strip()
            if not text.startswith("{"):
                continue  # comments, banners, blank lines
            try:
                event = json.loads(text)
            except json.JSONDecodeError:
                logger.debug("codex stream: unparseable line", job_id=mapper.job_id[:8])
                continue
            for kind, fields in mapper.map(event):
                await on_event(kind, fields)
        # stdout is closed: the process is exiting. Give stderr a bounded
        # moment to finish so a crash message reaches `ExecResult.error`.
        try:
            await asyncio.wait_for(asyncio.shield(stderr_task), _STDERR_DRAIN_S)
        except asyncio.TimeoutError:
            pass
    finally:
        if not stderr_task.done():
            stderr_task.cancel()
            try:
                await stderr_task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass


async def probe_cli_version(codex_bin: str, process_factory: ProcessFactory,
                            env: dict[str, str], *, cwd: str) -> str | None:
    """`codex --version` → first stdout line, or None. Best-effort: a probe
    failure never fails the job. Never through sudo."""
    proc: Any = None
    try:
        proc = await process_factory([codex_bin, "--version"], cwd=cwd, env=env)
        line = await asyncio.wait_for(proc.stdout.readline(), 15)
        await asyncio.wait_for(asyncio.shield(proc.wait()), 15)
        text = line.decode("utf-8", "replace").strip()
        return text or None
    except Exception as exc:  # noqa: BLE001
        logger.warning("codex --version probe failed", error=str(exc))
        return None
    finally:
        # A readline/wait timeout lands here too: never leave the probe behind.
        if proc is not None and proc.returncode is None:
            await _terminate(proc, 0.5)


def default_output_path(job_id: str) -> Path:
    """`-o` target: beside the job's audit log (`<job_id>.codex-last.md`),
    never inside the clone (it would be committed — plan §4h)."""
    return settings.audit_log_dir / f"{job_id}.codex-last.md"


# ── the executor ─────────────────────────────────────────────────────────────


async def run(job: Any, *, cwd: Path | str, prompt: str, model_id: str, sandbox: str,
              timeout_s: float, on_event: OnEvent | None = None,
              process_factory: ProcessFactory | None = None,
              codex_bin: str = "", codex_home: str = "", run_as_user: str | None = None,
              output_path: Path | str | None = None,
              environ: dict[str, str] | None = None,
              cli_version: str | None = None,
              kill_grace_s: float = KILL_GRACE_S) -> ExecResult:
    """Run one Codex job and return its `ExecResult`.

    `job` is a Job row or a job id. Everything else is explicit so the caller
    (T4's dispatch branch) decides the clone, the prompt (system directive +
    skill body prepended — §4h), the pinned model and the sandbox; the
    refusals that gate the lane (provider enabled, workspace tier, no
    subagents/MCP, `code-server` set) live in the session, before this call.

    Never raises on a vendor failure: `terminal_reason` says what happened
    (`ok | rate_limited | auth_expired | api_error | timeout | interrupted`).
    Raises `ValueError` on bad inputs (including `run_as_user` without a
    `codex_home` stream home) and `CodexNotFound` on no binary — both before
    any process starts. An infrastructure failure mid-stream (the sink
    raising — e.g. the audit log on a full disk — or a stream line over
    `_STREAM_LINE_LIMIT`) terminates the child first and then propagates.
    """
    job_id = str(getattr(job, "id", job))
    cwd_path = Path(cwd)
    if not cwd_path.is_dir():
        raise ValueError(f"cwd is not a directory: {cwd_path}")
    if sandbox not in SANDBOX_MODES:
        raise ValueError(f"sandbox {sandbox!r} not allowed; one of {sorted(SANDBOX_MODES)}")
    if not (prompt or "").strip():
        raise ValueError("empty prompt")
    if not timeout_s or timeout_s <= 0:
        raise ValueError("timeout_s must be positive")

    binary = discover_binary(codex_bin or settings.codex_bin)
    user = settings.codex_run_as_user if run_as_user is None else run_as_user
    stream_home = (codex_home or settings.codex_home or "").strip()
    if user:
        # D-C: the unprivileged user gets the stream home for HOME/TMPDIR/
        # CODEX_HOME — never the owner's (old spec §2.4; review 2026-10-21).
        if not stream_home:
            raise ValueError("codex_run_as_user requires codex_home (the stream home)")
        env = scrubbed_env(environ, codex_home=stream_home, home=stream_home,
                           tmpdir=str(Path(stream_home) / "tmp"))
    else:
        env = scrubbed_env(environ, codex_home=stream_home)
    out_path = Path(output_path) if output_path is not None else default_output_path(job_id)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    argv = build_argv(codex_bin=binary, cwd=cwd_path, prompt=prompt, model_id=model_id,
                      sandbox=sandbox, output_path=out_path, run_as_user=user or "")
    factory = process_factory or _default_process_factory
    sink = on_event or default_sink(job_id)

    if cli_version is None:
        cli_version = await probe_cli_version(binary, factory, env, cwd=str(cwd_path))

    mapper = EventMapper(job_id, model_id=model_id, cli_version=cli_version,
                         env_keys=sorted(env))
    stderr_buf: list[str] = []
    terminal_reason: str | None = None
    error: str | None = None
    _interrupted.discard(job_id)
    # Job ids are reused on requeue (reconcile, INV-12 front requeue, T6's
    # rate_limited LPUSH): a stale `-o` from an earlier attempt must never
    # become this attempt's text of record.
    out_path.unlink(missing_ok=True)

    proc = await factory(argv, cwd=str(cwd_path), env=env)
    _running[job_id] = proc
    try:
        try:
            await asyncio.wait_for(_consume(proc, mapper, sink, stderr_buf), timeout_s)
        except asyncio.TimeoutError:
            await _terminate(proc, kill_grace_s)
            terminal_reason = "timeout"
            error = f"codex exec exceeded {timeout_s:g}s"
        try:
            await asyncio.wait_for(asyncio.shield(proc.wait()), _EXIT_WAIT_S)
        except asyncio.TimeoutError:
            # stdout closed but the process lingers: never leave it behind.
            await _terminate(proc, kill_grace_s)
    except BaseException:
        # Cancellation (main._process_job's wait_for), a sink that raises
        # (audit log on a full disk), a stream line over the limit, anything
        # else: the child never outlives this call. Then propagate.
        await _terminate(proc, kill_grace_s)
        raise
    finally:
        _running.pop(job_id, None)

    exit_code = proc.returncode
    stderr_text = "".join(stderr_buf).strip()

    if terminal_reason is None:
        if job_id in _interrupted:
            terminal_reason = "interrupted"
            error = "interrupted"
        elif mapper.terminal_reason is not None:
            terminal_reason = mapper.terminal_reason
            error = mapper.error_message
        elif mapper.saw_turn_completed:
            terminal_reason = "ok"
        else:
            # Non-zero exit with no turn.completed → api_error (plan T3); and
            # a zero exit with no turn.completed is the silent-empty-success
            # trap (old spec §2.4) — no work of record, same class.
            terminal_reason = "api_error"
            error = (f"codex exec exited {exit_code} without turn.completed"
                     + (f": {stderr_text[-_STDERR_KEEP:]}" if stderr_text else ""))
    _interrupted.discard(job_id)

    if terminal_reason in ("timeout", "api_error") and mapper.terminal_reason is None:
        await sink("executor_error", {"terminal_reason": terminal_reason, "message": error})

    # Plan §4i: the `-o` file is the text of record — but only once a turn
    # completed (codex writes it at the end of the turn; anything else there
    # is not this attempt's work). Fallback: the last `agent_message`.
    final_text = (_read_output(out_path) if mapper.saw_turn_completed else "") \
        or mapper.last_agent_message.strip()

    return ExecResult(
        final_text=final_text,
        usage=dict(mapper.usage),
        terminal_reason=terminal_reason,
        model_served=mapper.model_served,
        thread_id=mapper.thread_id,
        cli_version=cli_version,
        exit_code=exit_code,
        error=error,
    )


def _read_output(path: Path) -> str:
    """The `-o` file is the text of record (plan §4i); empty/missing → ''."""
    try:
        if path.is_file():
            return path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError as exc:
        logger.warning("could not read codex output file", path=str(path), error=str(exc))
    return ""
