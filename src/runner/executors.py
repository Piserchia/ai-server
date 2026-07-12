"""
Session executors (P1). One interface, two backends:

- InProcessExecutor: the Claude Agent SDK session in this process — the
  original execution path, unchanged in behavior.
- ContainerExecutor: `claude -p` headless inside a container (docker CLI —
  works with colima, Docker Desktop, or OrbStack). Used by high-risk tiers
  (`isolation: container`) so a session cannot touch the live server.

Both backends emit the SAME audit-log events (text / tool_use / tool_result /
thinking) and the same Redis stream messages, so everything downstream
(review, write-back, learning, dashboards) is executor-agnostic. That parity
is the contract — see tests/test_executors.py.

Auth: containers get CLAUDE_CODE_OAUTH_TOKEN (from `claude setup-token`,
subscription auth) and NEVER ANTHROPIC_API_KEY (INV-3 applies inside
containers too). If the token or the runtime is missing, the runner
downgrades `container` → `workspace` (see workspaces.resolve_isolation) and
logs why.

Known limitation: the CLI lane passes --model but not effort (no stable CLI
flag); effort tuning applies on the in-process lane. Container-tier skills
(server-patch) trade that for isolation.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src import audit_log
from src.config import settings
from src.runner import quota

logger = logging.getLogger(__name__)

# Registry of running container names for /cancel (mirrors _running_sessions).
_running_containers: dict[str, str] = {}


@dataclass
class ExecutionResult:
    final_summary: str
    usage: dict[str, Any] = field(default_factory=dict)


# ── Container runtime availability ──────────────────────────────────────────

_runtime_probe: tuple[float, bool] | None = None  # (checked_at, available)
_PROBE_TTL_SECONDS = 300


def container_runtime_available() -> bool:
    """True if the configured container runtime is usable AND an OAuth token
    is present. Cached for 5 minutes. Never raises."""
    global _runtime_probe
    if not settings.container_runtime:
        return False
    if not _oauth_token():
        return False
    now = time.monotonic()
    if _runtime_probe and now - _runtime_probe[0] < _PROBE_TTL_SECONDS:
        return _runtime_probe[1]
    ok = False
    try:
        if shutil.which(settings.container_runtime):
            res = subprocess.run(
                [settings.container_runtime, "info"],
                capture_output=True, timeout=10,
            )
            ok = res.returncode == 0
    except Exception as exc:  # noqa: BLE001 — availability probe must not raise
        logger.warning("container runtime probe failed: %s", exc)
    _runtime_probe = (now, ok)
    return ok


def _oauth_token() -> str:
    return settings.claude_code_oauth_token or os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "")


# ── Cancel support ──────────────────────────────────────────────────────────


async def interrupt_container(job_id: str) -> bool:
    """Kill the container running job_id. Returns True if one was found."""
    name = _running_containers.get(str(job_id))
    if not name:
        return False
    try:
        proc = await asyncio.create_subprocess_exec(
            settings.container_runtime, "kill", name,
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("container kill failed for %s: %s", job_id, exc)
        return False


# ── Pure helpers (unit-tested) ──────────────────────────────────────────────


def container_name_for_job(job_id: str) -> str:
    return f"ai-job-{str(job_id)[:8]}"


def build_container_command(
    *,
    job_id: str,
    prompt: str,
    system_prompt: str,
    model: str,
    permission_mode: str,
    allowed_tools: list[str],
    max_turns: int | None,
    workspace: Path,
    context_dir: Path,
    image: str,
    runtime: str,
    memory: str,
    cpus: str,
) -> list[str]:
    """Build the full `docker run` argv for a containerized session.

    Mounts:
      workspace       → /work   (rw — the per-job clone; the ONLY writable mount)
      server .context → /ctx    (ro — protocol/docs the directive references)
    Pure function (no I/O) so the exact command is testable.
    """
    cmd = [
        runtime, "run", "--rm",
        "--name", container_name_for_job(job_id),
        "-v", f"{workspace}:/work",
        "-v", f"{context_dir}:/ctx:ro",
        "-w", "/work",
        "--memory", memory,
        "--cpus", cpus,
        "-e", "CLAUDE_CODE_OAUTH_TOKEN",       # value comes from the runner env
        "-e", "GIT_TERMINAL_PROMPT=0",
        image,
        "claude", "-p", prompt,
        "--output-format", "stream-json",
        "--verbose",
        "--permission-mode", permission_mode,
        "--append-system-prompt", system_prompt,
    ]
    if model:
        cmd += ["--model", model]
    if allowed_tools:
        cmd += ["--allowedTools", ",".join(allowed_tools)]
    if max_turns:
        cmd += ["--max-turns", str(max_turns)]
    return cmd


def parse_stream_json_line(line: str) -> list[dict[str, Any]]:
    """Map one `claude -p --output-format stream-json` line to audit-event
    dicts of the same shape the in-process executor produces.

    Returns [] for lines we don't understand (defensive by design — CLI
    output evolves). Pure function.
    """
    line = line.strip()
    if not line or not line.startswith("{"):
        return []
    try:
        obj = json.loads(line)
    except json.JSONDecodeError:
        return []

    events: list[dict[str, Any]] = []
    typ = obj.get("type")

    if typ == "assistant":
        for block in (obj.get("message") or {}).get("content", []) or []:
            btype = block.get("type")
            if btype == "text" and block.get("text"):
                events.append({"kind": "text", "text": block["text"]})
            elif btype == "tool_use":
                events.append({
                    "kind": "tool_use",
                    "tool_name": block.get("name", ""),
                    "tool_use_id": block.get("id", ""),
                    "input": block.get("input"),
                })
            elif btype == "thinking" and block.get("thinking"):
                events.append({"kind": "thinking", "text": block["thinking"]})

    elif typ == "user":
        for block in (obj.get("message") or {}).get("content", []) or []:
            if block.get("type") == "tool_result":
                events.append({
                    "kind": "tool_result",
                    "tool_use_id": block.get("tool_use_id", ""),
                    "is_error": bool(block.get("is_error")),
                    "content": block.get("content"),
                })

    elif typ == "result":
        events.append({
            "kind": "result",
            "subtype": obj.get("subtype", ""),
            "result": obj.get("result", "") or "",
            "usage": obj.get("usage") or {},
            "is_error": bool(obj.get("is_error")),
        })

    return events


# ── Container executor ──────────────────────────────────────────────────────


async def run_in_container(
    *,
    job_id: str,
    prompt: str,
    system_prompt: str,
    model: str,
    permission_mode: str,
    allowed_tools: list[str],
    max_turns: int | None,
    workspace: Path,
    publish_stream,
    truncate_for_log,
    preview_text,
) -> ExecutionResult:
    """Run a session via `claude -p` inside a container, streaming stdout
    into the audit log + Redis exactly like the in-process path.

    Raises quota.QuotaExhausted on detected quota errors so the runner's
    pause/requeue logic applies unchanged.
    """
    cmd = build_container_command(
        job_id=job_id,
        prompt=prompt,
        system_prompt=system_prompt,
        model=model,
        permission_mode=permission_mode,
        allowed_tools=allowed_tools,
        max_turns=max_turns,
        workspace=workspace,
        context_dir=settings.context_dir,
        image=settings.agent_image,
        runtime=settings.container_runtime,
        memory=settings.container_memory,
        cpus=settings.container_cpus,
    )

    env = dict(os.environ)
    env.pop("ANTHROPIC_API_KEY", None)              # INV-3, defense in depth
    env["CLAUDE_CODE_OAUTH_TOKEN"] = _oauth_token()

    audit_log.append(job_id, "container_started",
                     image=settings.agent_image,
                     container=container_name_for_job(job_id),
                     workspace=str(workspace))

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    _running_containers[job_id] = container_name_for_job(job_id)

    final_chunks: list[str] = []
    usage: dict[str, Any] = {}
    result_error_text = ""

    try:
        assert proc.stdout is not None
        async for raw in proc.stdout:
            try:
                line = raw.decode("utf-8", errors="replace")
            except Exception:  # noqa: BLE001
                continue
            for evt in parse_stream_json_line(line):
                kind = evt["kind"]
                if kind == "text":
                    audit_log.append(job_id, "text", text=evt["text"])
                    final_chunks.append(evt["text"])
                    await publish_stream(job_id, {"kind": "text", "text": evt["text"]})
                elif kind == "tool_use":
                    audit_log.append(job_id, "tool_use",
                                     tool_name=evt["tool_name"],
                                     tool_use_id=evt["tool_use_id"],
                                     input=truncate_for_log(evt.get("input")))
                    await publish_stream(job_id, {
                        "kind": "tool_use",
                        "tool_name": evt["tool_name"],
                        "tool_use_id": evt["tool_use_id"],
                    })
                elif kind == "thinking":
                    audit_log.append(job_id, "thinking", text=evt["text"])
                elif kind == "tool_result":
                    audit_log.append(job_id, "tool_result",
                                     tool_use_id=evt["tool_use_id"],
                                     is_error=evt["is_error"],
                                     result_preview=preview_text(evt.get("content")))
                elif kind == "result":
                    usage = evt.get("usage") or {}
                    if evt.get("is_error"):
                        result_error_text = str(evt.get("result", ""))[:1000]
                    # The CLI's result.result is the final text; use it if we
                    # somehow saw no assistant text blocks.
                    if not final_chunks and evt.get("result"):
                        final_chunks.append(str(evt["result"]))

        stderr_bytes = await proc.stderr.read() if proc.stderr else b""
        rc = await proc.wait()
        stderr_text = stderr_bytes.decode("utf-8", errors="replace")[:2000]

        # Quota detection on both stderr and result error text
        for probe in (stderr_text, result_error_text):
            if probe:
                detected = quota.detect_quota_error(probe)
                if detected is not None:
                    from datetime import datetime
                    reset_at = detected if isinstance(detected, datetime) else None
                    raise quota.QuotaExhausted(reset_at, reason=probe[:500])

        if rc != 0:
            raise RuntimeError(
                f"container session exited {rc}: {result_error_text or stderr_text or 'no error output'}"
            )
        if result_error_text:
            raise RuntimeError(f"container session reported error: {result_error_text}")

        return ExecutionResult(final_summary="\n".join(final_chunks).strip(), usage=usage)

    finally:
        _running_containers.pop(job_id, None)
        if proc.returncode is None:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
