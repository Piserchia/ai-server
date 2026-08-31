#!/usr/bin/env bash
# run.sh — start/stop/restart/status the 3 server processes (runner, web, bot).
# Infra (postgres, redis) comes from `brew services`; caddy + cloudflared have
# their own scripts (added in Phase 3).
#
# Usage: bash scripts/run.sh {start|stop|restart|status}
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PID_DIR="$PROJECT_DIR/volumes/pids"
LOG_DIR="$PROJECT_DIR/volumes/logs"

mkdir -p "$PID_DIR" "$LOG_DIR"

# Never inherit an API key into our processes
unset ANTHROPIC_API_KEY || true

SERVICES=(runner web bot)

# ── launchd awareness (2026-08-31, EVALUATION_2026-08-30 F2.1) ──────────────
# In production the three services are OWNED BY LAUNCHD (com.assistant.*),
# which never writes PID files — so the PID-file status below reported
# "not running" while everything was up, and a well-meaning `run.sh start`
# from the dev tree would bind :8080 against the live uvicorn. When launchd
# units exist, status reports launchd truth and start refuses. Manage the
# production services with:
#   launchctl kickstart -k gui/$UID/com.assistant.runner   (restart one)
#   launchctl print gui/$UID/com.assistant.runner          (inspect)

_launchd_unit_loaded() {
    launchctl print "gui/$(id -u)/com.assistant.$1" > /dev/null 2>&1
}

_launchd_status_one() {
    local name="$1" out pid
    if out=$(launchctl print "gui/$(id -u)/com.assistant.$name" 2>/dev/null); then
        pid=$(printf '%s' "$out" | awk '/^\tpid = /{print $3; exit}')
        if [ -n "${pid:-}" ]; then
            echo "  $name: running under launchd (PID $pid)"
        else
            echo "  $name: loaded in launchd but NOT running"
        fi
    else
        echo "  $name: no launchd unit"
    fi
}

_any_launchd_unit() {
    local s
    for s in "${SERVICES[@]}"; do
        _launchd_unit_loaded "$s" && return 0
    done
    return 1
}

_start_one() {
    local name="$1"
    shift
    local pid_file="$PID_DIR/${name}.pid"

    if [ -f "$pid_file" ] && kill -0 "$(cat "$pid_file")" 2>/dev/null; then
        echo "  $name already running (PID $(cat "$pid_file"))"
        return 0
    fi
    [ -f "$pid_file" ] && rm -f "$pid_file"

    # Run command, backgrounded, redirect all output to log
    ("$@") > "$LOG_DIR/${name}.log" 2>&1 &
    echo $! > "$pid_file"
    echo "  $name started (PID $!)"
}

_stop_one() {
    local name="$1"
    local pid_file="$PID_DIR/${name}.pid"
    [ -f "$pid_file" ] || { echo "  $name: no pid file"; return 0; }
    local pid
    pid=$(cat "$pid_file")
    if ! kill -0 "$pid" 2>/dev/null; then
        echo "  $name: not running (stale pid file)"
        rm -f "$pid_file"
        return 0
    fi
    echo "  $name: SIGTERM to $pid..."
    kill -TERM "$pid" 2>/dev/null || true
    for _ in 1 2 3 4 5 6 7 8 9 10; do
        kill -0 "$pid" 2>/dev/null || { echo "  $name: stopped"; rm -f "$pid_file"; return 0; }
        sleep 1
    done
    echo "  $name: SIGKILL (didn't stop in 10s)"
    kill -KILL "$pid" 2>/dev/null || true
    rm -f "$pid_file"
}

_status_one() {
    local name="$1"
    local pid_file="$PID_DIR/${name}.pid"
    if [ -f "$pid_file" ] && kill -0 "$(cat "$pid_file")" 2>/dev/null; then
        echo "  $name: running (PID $(cat "$pid_file"))"
    else
        echo "  $name: not running"
    fi
}

do_start() {
    if _any_launchd_unit; then
        echo "REFUSING to start: com.assistant.* launchd units are loaded — the"
        echo "services are launchd-managed (probably already running). Starting a"
        echo "second copy here would collide on :8080 and the job queue."
        echo "Use: launchctl kickstart -k gui/\$UID/com.assistant.<runner|web|bot>"
        exit 1
    fi
    cd "$PROJECT_DIR"
    echo "Starting services..."
    _start_one runner pipenv run python3 -m src.runner.main
    _start_one web pipenv run uvicorn src.gateway.web:app --host 127.0.0.1 --port 8080
    _start_one bot pipenv run python3 -m src.gateway.telegram_bot
    echo "Done. Logs at $LOG_DIR"
}

do_stop() {
    echo "Stopping services..."
    for s in "${SERVICES[@]}"; do _stop_one "$s"; done
}

do_status() {
    if _any_launchd_unit; then
        echo "Service status (launchd-managed):"
        for s in "${SERVICES[@]}"; do _launchd_status_one "$s"; done
    else
        echo "Service status (PID files — dev mode):"
        for s in "${SERVICES[@]}"; do _status_one "$s"; done
    fi
}

case "${1:-start}" in
    start)   do_start ;;
    stop)    do_stop ;;
    restart) do_stop; do_start ;;
    status)  do_status ;;
    *) echo "Usage: $0 {start|stop|restart|status}"; exit 1 ;;
esac
