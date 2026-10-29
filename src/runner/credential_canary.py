"""
Daily credential canary — E10 (spec §0a last rows, §6 "Credential canaries",
§9 Phase-1 row; design of record P0 plan Task 12, renamed and made
self-contained by the re-cut E10 Deltas; D-P1-9).

`scripts/credential-canary.sh` runs `python -m src.runner.credential_canary`
once a day under launchd (06:50). The ping goes through the SAME path the
runner uses — the claude_agent_sdk in the runner venv (its bundled CLI, the
Keychain login), a ClaudeAgentOptions built the way the runner builds its
one-shot sessions (server-root cwd, plan mode, no tools, one turn,
`setting_sources=["project"]`, E7's env overlay) — and is judged by the SAME
rule the runner applies to every session (`result_capture.served_model_violation`),
tightened for a probe. Never the brew `claude`; never the CLI's OAuth-skipping
mode; never the sealed setup-token — a pass means the Keychain login the fleet
runs on still serves, and the process env must be WITHOUT CLAUDE_CODE_OAUTH_TOKEN
for a pass to mean that.

Settings scope is part of the assertion (spec §6): before pinging, the canary
clears the server root with E1's `settings_override` AND `~/.claude/settings*.json`
with a stricter rule (no tracked-file allowance; `statusLine` is the one allowed
extra key there — D-P1-9, the owner's D8 status-line feed; any other refused key
is a FAIL). A user-scope `apiKeyHelper` or `env.ANTHROPIC_BASE_URL` would make a
green ping meaningless, so the ping is skipped when a scope is dirty.

Exit codes: 0 ok · 1 the ping ran and failed the assertion (or a scope/env
precondition failed) · 2 the SDK could not run at all (CLI missing, transport
error, timeout) — also an alert.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections.abc import AsyncIterator, Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    query,
)

from src.config import settings
from src.runner.claude_env import claude_subprocess_env, vendor_keys_in
from src.runner.result_capture import (
    ResultCapture,
    capture_result_message,
    served_model_violation,
)

PING_PROMPT = "Reply with exactly the word: pong"
DEFAULT_TIMEOUT_S = 180

#: What the canary refuses in USER scope (~/.claude/settings*.json): the auth
#: keys (they outrank /login for every session on the host), the two code
#: channels the SDK honours from any scope (`hooks`, `env`), `apiKeyHelper`,
#: and `statusLine` (a command run on every session) — spec §6 "any auth or
#: `hooks` key", plan E10. NOT the editor-side keys (`permissions`,
#: `mcpServers`, …): the fleet runs with `setting_sources=["project"]`, so a
#: user-scope `permissions` never reaches a job, and refusing it would turn
#: the owner's own Claude Code choices into a red canary — inside the prod
#: deploy gate (whole-branch review 2026-10-29). Pinned equal to
#: `session.SETTINGS_AUTH_KEYS ∪ {hooks, env, apiKeyHelper, statusLine}`.
USER_SETTINGS_REFUSED_KEYS: tuple[str, ...] = (
    "apiKeyHelper", "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN",
    "CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_BASE_URL",
    "hooks", "env", "statusLine",
)
#: … and D-P1-9 allows exactly `statusLine`: D8 asks the owner to put a
#: status-line command into ~/.claude/settings.json (the rate-limit feed).
#: Widening this is an owner decision, not a drift.
USER_SETTINGS_ALLOWED_KEYS: frozenset[str] = frozenset({"statusLine"})


def canary_options(model: str) -> ClaudeAgentOptions:
    """The runner's conventions for a one-shot utility session: server-root
    cwd, low effort, plan mode, no tools, one turn, E7's subprocess env
    overlay (telemetry off), and the runner's own `setting_sources` — pinned
    rather than left default because the canary's whole job is to prove WHICH
    credential the fleet runs on; reading a different settings scope would
    prove the wrong thing."""
    return ClaudeAgentOptions(
        cwd=str(settings.server_root),
        model=model,
        effort="low",
        permission_mode="plan",
        allowed_tools=[],
        max_turns=1,
        env=claude_subprocess_env(),
        setting_sources=["project"],
    )


def settings_scopes() -> tuple[Path, Path]:
    """(project scope = the runner's cwd, user scope = the owner's home). A
    function so tests can isolate it."""
    return Path(settings.server_root), Path.home()


def settings_precheck() -> tuple[str, str] | None:
    """(offending key, "<scope>/.claude/<file>") or None.

    Project scope: E1's `settings_override(root, canonical=root)` — the server
    root's own tracked `permissions` is allowed per key, a hook is not. User
    scope is STRICTER: no tracked-file allowance, every auth and code-channel
    key refused plus `statusLine`, with `statusLine` then exempted as the one
    allowed key (D-P1-9). The auth key inside `env` is named before the
    container, as in E1."""
    from src.runner.session import SETTINGS_AUTH_KEYS, settings_override

    project, home = settings_scopes()
    found = settings_override(project, canonical=project)
    if found is not None:
        return found.key, str(project / ".claude" / found.file)

    for name in ("settings.local.json", "settings.json"):
        path = home / ".claude" / name
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        env = data.get("env") if isinstance(data.get("env"), dict) else {}
        for key in SETTINGS_AUTH_KEYS:          # the auth key inside `env` is named first
            if key in env:
                return key, str(path)
        for key in USER_SETTINGS_REFUSED_KEYS:
            if key in USER_SETTINGS_ALLOWED_KEYS:
                continue
            if key in data:
                return key, str(path)
    return None


async def run_ping(
    model: str,
    *,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    query_fn: Callable[..., AsyncIterator[Any]] | None = None,
) -> tuple[ResultCapture | None, str]:
    """One ping through the SDK. (capture, final_text); capture is None when
    no ResultMessage arrived (the CLI died before answering). `query_fn` is
    resolved at call time so tests can inject a fake."""
    q = query_fn or query
    capture: ResultCapture | None = None
    chunks: list[str] = []

    async def _consume() -> None:
        nonlocal capture
        async for message in q(prompt=PING_PROMPT, options=canary_options(model)):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        chunks.append(block.text)
            elif isinstance(message, ResultMessage):
                capture = capture_result_message(message)

    await asyncio.wait_for(_consume(), timeout=timeout_s)
    return capture, "\n".join(chunks).strip()


def evaluate_ping(capture: ResultCapture | None, final_text: str,
                  requested_model: str) -> tuple[bool, str]:
    """Pure. The runner's served-model rule first, then the canary-only
    tightening: a probe must see `model_usage`, real API time and non-zero
    usage — the "absent model_usage" leniency the runner grants a short chat
    job does not apply to a ping whose whole point is proving the credential."""
    if capture is None:
        return False, "no ResultMessage (CLI exited without a result — logged out? unknown model?)"
    if capture.is_error:
        err = capture.result_text or "; ".join(capture.errors)
        return False, f"is_error ({capture.subtype}): {err[:200] or 'no detail'}"
    violation = served_model_violation(capture, requested_model, final_text=final_text)
    if violation:
        return False, violation
    if not capture.model_usage:
        return False, "model_usage missing (unknown model id? logged out?)"
    if (capture.duration_api_ms or 0) <= 0:
        return False, "duration_api_ms is 0 (no API call happened)"
    if capture.usage_empty:
        return False, "usage all-zero"
    total = (capture.input_tokens + capture.output_tokens + capture.cache_read_tokens
             + capture.cache_write_1h_tokens + capture.cache_write_5m_tokens)
    return True, f"ok served={capture.model_served} api_ms={capture.duration_api_ms} tokens={total}"


def telemetry_record(ok: bool, detail: str, requested_model: str, now: datetime) -> dict[str, Any]:
    return {"ok": ok, "detail": detail, "requested_model": requested_model,
            "checked_at": now.isoformat()}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m src.runner.credential_canary")
    p.add_argument("--model", default=settings.utility_model)
    p.add_argument("--telemetry", default=None, help="write the verdict JSON here")
    p.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_S)
    args = p.parse_args(argv)

    def _finish(ok: bool, detail: str, rc: int) -> int:
        if args.telemetry:
            try:
                out = Path(args.telemetry)
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(json.dumps(telemetry_record(
                    ok, detail, args.model, datetime.now(timezone.utc)), indent=2))
            except OSError as exc:
                print(f"telemetry write failed: {exc}", file=sys.stderr)
        print(detail)
        return rc

    # A pass must prove the KEYCHAIN login. The setup token would be served
    # instead of /login; ANTHROPIC_AUTH_TOKEN / ANTHROPIC_BASE_URL / a vendor
    # key would re-bill or redirect the ping while `model_usage` still names
    # the model — so the whole E7 refusal set (the contract the runner itself
    # refuses to start on) is a FAIL here (whole-branch review 2026-10-29).
    leaked = vendor_keys_in(os.environ)
    if leaked:
        what = ("the setup token" if leaked == ["CLAUDE_CODE_OAUTH_TOKEN"]
                else "a re-billed or redirected call")
        return _finish(False, f"{', '.join(leaked)} set in the canary's environment — a ping "
                              f"here would prove {what}, not the Keychain login", 1)

    # Prove the credential SOURCE before trusting the ping (spec §6).
    scope_hit = settings_precheck()
    if scope_hit is not None:
        key, where = scope_hit
        return _finish(False, f"settings_override:{key}@{where}", 1)

    try:
        capture, text = asyncio.run(run_ping(args.model, timeout_s=args.timeout, query_fn=query))
    except asyncio.TimeoutError:
        ok, detail, rc = False, f"canary timeout after {args.timeout:g}s", 2
    except Exception as exc:  # noqa: BLE001 — CLINotFoundError, ProcessError, transport errors
        ok, detail, rc = False, f"sdk failed to run: {type(exc).__name__}: {str(exc)[:160]}", 2
    else:
        ok, detail = evaluate_ping(capture, text, args.model)
        rc = 0 if ok else 1
    return _finish(ok, detail, rc)


if __name__ == "__main__":
    sys.exit(main())
