#!/usr/bin/env bash
# scripts/credential-canary.sh — daily Claude subscription credential canary (E10).
#
# OUT-OF-BAND by design (same doctrine as healthcheck-all.sh): if the Max login
# lapses, the runner's first job of the day fails only after burning a slot and
# an escalation. This probe fails BEFORE that and DMs the owner via
# `python -m src.notify send` (outbox row = the alert history), with the raw
# Telegram curl as the last-resort fallback when the notify CLI itself is broken.
# The ping runs INSIDE `python -m src.runner.credential_canary` — through the
# claude_agent_sdk in the runner venv (bundled CLI, Keychain login), the runner's
# option conventions, env overlay and served-model rule. Never the brew `claude`,
# never the sealed setup-token: a pass means the Keychain login serves.
#
# launchd: com.assistant.credential-canary, daily 06:50 (install-launchd.sh
# `timers-only` installs it). Usage: bash scripts/credential-canary.sh [model]
set -uo pipefail
export PATH="/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
unset ANTHROPIC_API_KEY        # INV-3: subscription auth only — never API billing

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG="$PROJECT_DIR/volumes/logs/credential-canary.log"
TELEMETRY="$PROJECT_DIR/volumes/telemetry/credential_canary.json"
MODEL="${1:-${CANARY_MODEL:-}}"
mkdir -p "$(dirname "$LOG")" "$(dirname "$TELEMETRY")"
cd "$PROJECT_DIR" || exit 2

# Interpreter: NEVER pipenv's shim here (launchd's `bash -lc` cannot see it —
# rc=127, prod schedule-monitor.log 2026-09-24). Order (§4, as schedule-monitor
# / cost-reconcile-run): the timer plist's VENV_PY → `pipenv --venv` → fail.
VENV_PY="${VENV_PY:-}"
if [[ -z "$VENV_PY" ]]; then
    PIPENV_VENV=""
    if command -v pipenv >/dev/null 2>&1; then
        PIPENV_VENV="$(cd "$PROJECT_DIR" && pipenv --venv 2>/dev/null || true)"
    fi
    VENV_PY="${PIPENV_VENV:+$PIPENV_VENV/bin/python}"
fi
if [[ -n "$VENV_PY" && -x "$VENV_PY" ]] && ! (cd "$PROJECT_DIR" && "$VENV_PY" -c 'import src.config' >/dev/null 2>&1); then
    echo "$(date -u +%FT%TZ) WARN venv python unusable ($VENV_PY): cannot import src.config from $PROJECT_DIR" >> "$LOG"
    VENV_PY=""
fi

notify_fail() {   # $1 = detail
    local msg token chat_ids chat_id
    msg="🔑 Claude credential canary FAILED on $(hostname -s): $1${MODEL:+ (model $MODEL)}. Fix on the Mini: \`claude login\` (Max, Keychain — the fleet's only credential), then re-run scripts/credential-canary.sh."
    if [[ -n "$VENV_PY" ]] && (cd "$PROJECT_DIR" && "$VENV_PY" -m src.notify send --kind credential_canary --severity critical \
            --text "$msg" >> "$LOG" 2>&1); then
        echo "$(date -u +%FT%TZ) ALERT sent via notify" >> "$LOG"
        return 0
    fi
    # Fallback: the notify CLI itself is broken → direct curl (healthcheck-all.sh pattern).
    token=$(grep -E '^TELEGRAM_BOT_TOKEN=' "$PROJECT_DIR/.env" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'" || true)
    chat_ids=$(grep -E '^TELEGRAM_ALLOWED_CHAT_IDS=' "$PROJECT_DIR/.env" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'" || true)
    chat_id=$(printf '%s' "$chat_ids" | cut -d, -f1 | tr -d '[:space:]')
    if [[ -z "$token" || -z "$chat_id" ]]; then
        echo "$(date -u +%FT%TZ) WARN alert skipped: telegram creds missing in .env" >> "$LOG"
        return 0
    fi
    curl -sf --max-time 10 "https://api.telegram.org/bot${token}/sendMessage" \
        --data-urlencode "chat_id=${chat_id}" --data-urlencode "text=${msg}" > /dev/null 2>&1 \
        && echo "$(date -u +%FT%TZ) ALERT sent via curl fallback" >> "$LOG" \
        || echo "$(date -u +%FT%TZ) WARN alert failed (telegram unreachable?)" >> "$LOG"
}

# The venv must exist and import the server AND the SDK before anything else
# is trusted: the SDK (and its bundled CLI) live there — the runner's path,
# never the brew `claude` — and the canary needs the server config.
if [[ -z "$VENV_PY" ]] || ! (cd "$PROJECT_DIR" && "$VENV_PY" -c 'import src.config, claude_agent_sdk' 2>>"$LOG"); then
    echo "$(date -u +%FT%TZ) FAIL venv python not found or SDK missing (VENV_PY='${VENV_PY:-}')" >> "$LOG"
    notify_fail "venv python not found / claude_agent_sdk missing — reinstall the timer with scripts/install-launchd.sh timers-only"
    exit 1
fi

# One ping through the runner's own SDK path (options, env overlay and the
# served-model rule live in src/runner/credential_canary.py; 180 s ceiling inside).
# rc 0 ok · 1 ran and failed the assertion · 2 the SDK could not run at all.
verdict=$(cd "$PROJECT_DIR" && "$VENV_PY" -m src.runner.credential_canary ${MODEL:+--model "$MODEL"} --telemetry "$TELEMETRY" --timeout 180 2>>"$LOG")
vrc=$?
echo "$(date -u +%FT%TZ) verdict rc=$vrc $verdict" >> "$LOG"
if (( vrc != 0 )); then
    notify_fail "${verdict:-canary produced no verdict (rc=$vrc)}"
    exit 1
fi
exit 0
