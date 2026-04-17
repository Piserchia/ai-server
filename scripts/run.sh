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
    echo "Service status:"
    for s in "${SERVICES[@]}"; do _status_one "$s"; done
}

case "${1:-start}" in
    start)   do_start ;;
    stop)    do_stop ;;
    restart) do_stop; do_start ;;
    status)  do_status ;;
    *) echo "Usage: $0 {start|stop|restart|status}"; exit 1 ;;
esac
