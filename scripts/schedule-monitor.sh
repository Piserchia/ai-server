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
export PATH="/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG="$PROJECT_DIR/volumes/logs/schedule-monitor.log"
ALERT_STATE="$PROJECT_DIR/volumes/schedule-monitor-alert.epoch"
ALERT_INTERVAL=43200   # one findings-DM per 12h; Sunday summary bypasses

cd "$PROJECT_DIR"
out=$(pipenv run python -m src.runner.schedule_adherence 2>>"$LOG")
rc=$?
echo "$(date -u +%FT%TZ) run rc=$rc" >> "$LOG"
printf '%s\n' "$out" >> "$LOG"
(( rc != 0 )) && exit 0   # collector failure already logged; not a finding

findings=$(printf '%s\n' "$out" | grep '^FINDING ' || true)
summary=$(printf '%s\n' "$out" | grep '^OK ' | tail -1)
dow=$(date -u +%u)
now=$(date +%s)

send_dm() {
    local msg="$1" token chat_ids chat_id
    token=$(grep -E '^TELEGRAM_BOT_TOKEN=' "$PROJECT_DIR/.env" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'" || true)
    chat_ids=$(grep -E '^TELEGRAM_ALLOWED_CHAT_IDS=' "$PROJECT_DIR/.env" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'" || true)
    chat_id=$(printf '%s' "$chat_ids" | cut -d, -f1 | tr -d '[:space:]')
    [[ -z "$token" || -z "$chat_id" ]] && { echo "$(date -u +%FT%TZ) WARN DM skipped: creds missing" >> "$LOG"; return 0; }
    curl -sf --max-time 10 "https://api.telegram.org/bot${token}/sendMessage" \
        --data-urlencode "chat_id=${chat_id}" \
        --data-urlencode "text=${msg}" > /dev/null 2>&1 \
        && echo "$(date -u +%FT%TZ) ALERT DM sent" >> "$LOG" \
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
