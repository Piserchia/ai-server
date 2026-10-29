#!/usr/bin/env bash
# scripts/q2-settings-sandbox-probe.sh — answers spec §14 Q2 on the PINNED CLI
# (the SDK-bundled binary in the runner venv, never brew's). Hand-run, once per
# CLI pin; the answers go in .context/modules/runner/skills/GOTCHAS.md beside the
# CLI version. Exit 0 = both questions answered (the answers are printed, not
# judged). Never in the pytest gate: it spawns the CLI.
#
#   Q2a  does the pinned CLI honour sandbox.failIfUnavailable / strictAllowlist
#        from project scope?            → honoured | ignored | rejected
#   Q2b  does it honour an AUTH key (ANTHROPIC_BASE_URL) from project scope?
#        → honoured (connection error) | ignored (ping succeeds on the Keychain login)
#
# Safety: every probe runs in a THROWAWAY directory (mktemp -d, removed on
# exit), the auth probe points at a closed localhost port (127.0.0.1:1), and no
# real credential is ever written anywhere. Nothing leaves the box; nothing can
# bill anywhere. E1's refusal ships regardless of Q2b's answer: hooks /
# permissions / mcpServers are honoured from project scope either way.
set -uo pipefail
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR" || exit 2

# Resolve the project venv's Python directly — never through the pipenv shim
# (§4 contract; same order as scripts/schedule-monitor.sh).
VENV_PY="${VENV_PY:-}"
if [[ -z "$VENV_PY" ]]; then
    PIPENV_VENV=""
    if command -v pipenv >/dev/null 2>&1; then
        PIPENV_VENV="$(pipenv --venv 2>/dev/null || true)"
    fi
    if [[ -n "$PIPENV_VENV" && -x "$PIPENV_VENV/bin/python" ]]; then
        VENV_PY="$PIPENV_VENV/bin/python"
    fi
fi
if [[ -z "$VENV_PY" || ! -x "$VENV_PY" ]]; then
    echo "q2-probe: cannot resolve the runner venv python (set VENV_PY)" >&2
    exit 2
fi
CLI_VERSION="$("$VENV_PY" -c 'from claude_agent_sdk import _cli_version as v; print(getattr(v, "__cli_version__", "unknown"))' 2>/dev/null || echo unknown)"
echo "pinned CLI version: $CLI_VERSION (venv python: $VENV_PY)"

PROBE="$(mktemp -d /tmp/q2-probe.XXXXXX)"; trap 'rm -rf "$PROBE"' EXIT
mkdir -p "$PROBE/.claude"

run_probe() {
    # $1 = label for the printed lines. Reads the probe dir's settings.json as
    # project scope, exactly as the runner's _build_options does.
    ( cd "$PROBE" && "$VENV_PY" - "$1" <<'PY' 2>&1 | tail -20 )
import asyncio, sys
from claude_agent_sdk import ClaudeAgentOptions, query
label = sys.argv[1]
async def main():
    try:
        async for m in query(prompt="reply with the single word ok",
                             options=ClaudeAgentOptions(model="claude-sonnet-4-6",
                                                        setting_sources=["project"],
                                                        max_turns=1, cwd=".",
                                                        allowed_tools=[])):
            name = type(m).__name__
            extra = getattr(m, "subtype", "") or ""
            res = str(getattr(m, "result", "") or "")[:120]
            err = getattr(m, "is_error", None)
            print(f"[{label}] {name} {extra} is_error={err} {res}")
    except Exception as exc:  # noqa: BLE001 — the exception IS an answer
        print(f"[{label}] EXCEPTION {type(exc).__name__}: {str(exc)[:200]}")
asyncio.run(main())
PY
}

# ── Q2a: are sandbox.failIfUnavailable / strictAllowlist honoured? ───────────
cat > "$PROBE/.claude/settings.json" <<'JSON'
{"sandbox": {"failIfUnavailable": true, "strictAllowlist": true}}
JSON
echo "--- Q2a: sandbox keys from project scope (expect a run, or a clear 'sandbox unavailable' refusal)"
run_probe Q2a

# ── Q2b: are project-scope AUTH keys honoured? ──────────────────────────────
# ANTHROPIC_BASE_URL is pointed at a closed localhost port: if the CLI honours
# it the request cannot connect (that failure IS the answer); if it ignores it
# the ping succeeds on the Keychain login.
cat > "$PROBE/.claude/settings.json" <<'JSON'
{"env": {"ANTHROPIC_BASE_URL": "http://127.0.0.1:1"}}
JSON
echo "--- Q2b: project-scope ANTHROPIC_BASE_URL (connection error = honoured; a normal 'ok' = ignored)"
run_probe Q2b

# ── Q2c: does the CLI parse LENIENT JSON (trailing comma / comments)? ───────
# E1 treats an unparseable settings file as "no override" (a malformed file is
# the CLI's problem). That is only safe if the CLI's parser is no more lenient
# than Python's json: if a trailing comma still gets the base URL applied,
# E1 must fail closed on unparseable-but-present files instead.
printf '%s\n' '{"env": {"ANTHROPIC_BASE_URL": "http://127.0.0.1:1"},}' > "$PROBE/.claude/settings.json"
echo "--- Q2c: lenient JSON (trailing comma) from project scope (connection error = PARSED → E1 must fail closed; 'ok' = ignored)"
run_probe Q2c

cat <<TXT
--- Record in .context/modules/runner/skills/GOTCHAS.md with CLI $CLI_VERSION:
  Q2c  lenient JSON parsed:                          parsed | ignored
  Q2a  sandbox.failIfUnavailable / strictAllowlist: honoured | ignored | rejected
  Q2b  project-scope ANTHROPIC_BASE_URL:            honoured | ignored
A verified "ignored" for Q2b removes only the AUTH half of the spec §6 hole —
hooks / permissions / mcpServers are honoured from project scope regardless, so
E1's refusal ships either way (spec §14 Q2, last sentence).
TXT
