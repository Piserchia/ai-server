#!/usr/bin/env bash
# scripts/schedule-monitor.sh — schedule-adherence watchdog (firm WS1).
#
# OUT-OF-BAND by design: the scheduler cannot watchdog itself (08-17
# governor-dark incident; healthcheck-all.sh codifies the doctrine). Daily
# via launchd (com.assistant.schedule-monitor). Deterministic — no LLM.
# DMs the owner when findings exist (>=12h between alert DMs) and always
# sends the Sunday fleet summary.
#
# Usage: bash scripts/schedule-monitor.sh
set -uo pipefail
# launchd gives this timer a minimal PATH — add common bin dirs so pipenv (if
# any), brew tools, etc. resolve. $HOME/.local/bin covers `pip install --user
# pipenv`; brew bins cover `brew install pipenv`.
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG="$PROJECT_DIR/volumes/logs/schedule-monitor.log"
ALERT_STATE="$PROJECT_DIR/volumes/schedule-monitor-alert.epoch"
ALERT_INTERVAL=43200   # one findings-DM per 12h; Sunday summary bypasses

cd "$PROJECT_DIR"

# Resolve the project venv's Python directly — never through the pipenv shim.
# launchd's minimal env has previously made this script silently rc=127 since
# 2026-09-14 (`pipenv: command not found`), killing the only out-of-band
# schedule-adherence alerter. Order (A7, 2026-10-21): the timer plist's
# VENV_PY if exported → install-launchd.sh's `pipenv --venv` resolution
# (VENV_DIR/bin/python) → pipenv's deterministic venv location
# (~/.local/share/virtualenvs/<basename>-<hash>) if the pipenv binary itself
# isn't on PATH.
VENV_PY="${VENV_PY:-}"
if [[ -z "$VENV_PY" ]]; then
    PIPENV_VENV=""
    if command -v pipenv >/dev/null 2>&1; then
        PIPENV_VENV="$(pipenv --venv 2>/dev/null || true)"
    fi
    if [[ -z "$PIPENV_VENV" || ! -x "$PIPENV_VENV/bin/python" ]]; then
        base="$(basename "$PROJECT_DIR")"
        for d in "$HOME/.local/share/virtualenvs/${base}-"*; do
            if [[ -x "$d/bin/python" ]]; then PIPENV_VENV="$d"; break; fi
        done
    fi
    VENV_PY="${PIPENV_VENV:+$PIPENV_VENV/bin/python}"
fi
if [[ -z "$VENV_PY" || ! -x "$VENV_PY" ]]; then
    echo "$(date -u +%FT%TZ) FATAL schedule-monitor cannot locate project venv python (searched: PATH pipenv, ~/.local/share/virtualenvs/$(basename "$PROJECT_DIR")-*)" >> "$LOG"
    exit 0
fi

out=$("$VENV_PY" -m src.runner.schedule_adherence 2>>"$LOG")
rc=$?
echo "$(date -u +%FT%TZ) run rc=$rc" >> "$LOG"
printf '%s\n' "$out" >> "$LOG"
(( rc != 0 )) && exit 0   # collector failure already logged; not a finding

findings=$(printf '%s\n' "$out" | grep '^FINDING ' || true)
summary=$(printf '%s\n' "$out" | grep '^OK ' | tail -1)
dow=$(date -u +%u)
now=$(date +%s)

# D1's provisioning_gap pre-check appends `schedule_deferred` records to
# volumes/audit_log/schedules/<schedule_id>.jsonl (a SUBDIRECTORY, so the job
# index never sees them). Counting the last 24 h here, out-of-band, is the
# second signal beside the scheduler's own one-DM-per-project-per-day: a
# deferred governed row is never silently dark. `ts` is the audit log's
# ISO-8601 UTC stamp, so a string compare against the cutoff is exact.
count_schedule_deferred() {
    local dir="$PROJECT_DIR/volumes/audit_log/schedules" cutoff
    [[ -d "$dir" ]] || { echo 0; return 0; }
    cutoff=$(date -u -v-24H +%FT%T 2>/dev/null || date -u -d '24 hours ago' +%FT%T 2>/dev/null || echo "")
    cat "$dir"/*.jsonl 2>/dev/null | awk -v cutoff="$cutoff" '
        /"kind": "schedule_deferred"/ {
            if (match($0, /"ts": "[^"]+"/)) {
                ts = substr($0, RSTART + 7, RLENGTH - 8)
                if (ts >= cutoff) n++
            }
        }
        END { print n + 0 }'
}

deferred_n=$(count_schedule_deferred)
[[ "$deferred_n" =~ ^[0-9]+$ ]] || deferred_n=0
echo "$(date -u +%FT%TZ) schedule_deferred_24h=$deferred_n" >> "$LOG"
if (( deferred_n > 0 )); then
    findings="${findings:+$findings
}FINDING deferred: ${deferred_n} schedule_deferred record(s) in the last 24h (provisioning_gap — /status names the rows)"
fi
summary="$summary deferred_24h=$deferred_n"

# Owner DM: the notifications outbox CLI first (direct Telegram HTTP + a
# `notifications` row = the alert history), the raw curl as the fallback when
# the CLI cannot run or did not deliver (it exits non-zero then). Out-of-band
# either way — no dependency on the bot or the runner. Never reads
# `NOTIFY_OUTBOX` (the switch is the bot's, D-P1-10).
send_dm() {
    local msg="$1" token chat_ids chat_id
    if [[ -n "$VENV_PY" ]] && (cd "$PROJECT_DIR" && "$VENV_PY" -m src.notify send --kind ops_alert --severity warn \
            --text "$msg" >> "$LOG" 2>&1); then
        echo "$(date -u +%FT%TZ) ALERT sent via notify" >> "$LOG"; return 0
    fi
    token=$(grep -E '^TELEGRAM_BOT_TOKEN=' "$PROJECT_DIR/.env" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'" || true)
    chat_ids=$(grep -E '^TELEGRAM_ALLOWED_CHAT_IDS=' "$PROJECT_DIR/.env" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'" || true)
    chat_id=$(printf '%s' "$chat_ids" | cut -d, -f1 | tr -d '[:space:]')
    [[ -z "$token" || -z "$chat_id" ]] && { echo "$(date -u +%FT%TZ) WARN DM skipped: creds missing" >> "$LOG"; return 0; }
    curl -sf --max-time 10 "https://api.telegram.org/bot${token}/sendMessage" \
        --data-urlencode "chat_id=${chat_id}" \
        --data-urlencode "text=${msg}" > /dev/null 2>&1 \
        && echo "$(date -u +%FT%TZ) ALERT DM sent (curl fallback)" >> "$LOG" \
        || echo "$(date -u +%FT%TZ) WARN DM failed" >> "$LOG"
}

if [[ -n "$findings" ]]; then
    last_alert=$(cat "$ALERT_STATE" 2>/dev/null || echo 0)
    [[ "$last_alert" =~ ^[0-9]+$ ]] || last_alert=0
    if (( now - last_alert >= ALERT_INTERVAL )); then
        n=$(printf '%s\n' "$findings" | wc -l | tr -d ' ')
        send_dm "🕳 Schedule monitor: ${n} finding(s)
$findings
$summary"
        echo "$now" > "$ALERT_STATE" 2>/dev/null || true
    fi
elif (( dow == 7 )); then
    send_dm "🗓 Schedule monitor (Sunday): all clear. $summary"
fi
exit 0
