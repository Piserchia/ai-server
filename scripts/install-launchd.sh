#!/usr/bin/env bash
# install-launchd.sh — install launchd plists so the 3 processes auto-start on login
# and auto-restart on crash.
#
# Usage:
#   bash scripts/install-launchd.sh           # install
#   bash scripts/install-launchd.sh uninstall
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LAUNCH_DIR="$HOME/Library/LaunchAgents"
LOG_DIR="$PROJECT_DIR/volumes/logs"

mkdir -p "$LAUNCH_DIR" "$LOG_DIR"

# Find pipenv's venv so we can invoke python directly (launchd doesn't love pipenv)
VENV_DIR="$(cd "$PROJECT_DIR" && pipenv --venv 2>/dev/null)" || true
if [ -z "${VENV_DIR:-}" ] || [ ! -d "$VENV_DIR" ]; then
    echo "ERROR: Could not find pipenv venv. Run 'pipenv install' first."
    exit 1
fi
PY="$VENV_DIR/bin/python"
UVICORN="$VENV_DIR/bin/uvicorn"

SERVICES=(
    "com.assistant.runner|python3 -m src.runner.main"
    "com.assistant.web|$UVICORN src.gateway.web:app --host 127.0.0.1 --port 8080"
    "com.assistant.bot|python3 -m src.gateway.telegram_bot"
)

uninstall() {
    echo "Uninstalling launchd services..."
    for svc in "${SERVICES[@]}"; do
        label="${svc%%|*}"
        plist="$LAUNCH_DIR/${label}.plist"
        if [ -f "$plist" ]; then
            launchctl unload "$plist" 2>/dev/null || true
            rm -f "$plist"
            echo "  Removed $label"
        fi
    done
    exit 0
}

[ "${1:-}" = "uninstall" ] && uninstall

echo "Installing launchd services..."
echo "  Project: $PROJECT_DIR"
echo "  Venv:    $VENV_DIR"
echo ""

for svc in "${SERVICES[@]}"; do
    label="${svc%%|*}"
    cmd="${svc#*|}"
    plist="$LAUNCH_DIR/${label}.plist"
    log_name="${label##*.}"

    # Substitute $VENV_DIR/bin/python for "python3" in the command
    full_cmd="${cmd//python3/$PY}"

    # Build the ProgramArguments as a bash -lc invocation so venv and PATH work
    cat > "$plist" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${label}</string>

  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>-lc</string>
    <string>cd "${PROJECT_DIR}" && unset ANTHROPIC_API_KEY && ${full_cmd}</string>
  </array>

  <key>WorkingDirectory</key>
  <string>${PROJECT_DIR}</string>

  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>${VENV_DIR}/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
  </dict>

  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key>
  <dict>
    <key>SuccessfulExit</key><false/>
    <key>Crashed</key><true/>
  </dict>

  <key>StandardOutPath</key>
  <string>${LOG_DIR}/${log_name}.out.log</string>
  <key>StandardErrorPath</key>
  <string>${LOG_DIR}/${log_name}.err.log</string>

  <key>ThrottleInterval</key><integer>30</integer>
</dict>
</plist>
PLIST

    launchctl unload "$plist" 2>/dev/null || true
    launchctl load -w "$plist"
    echo "  ✓ $label"
done

echo ""
echo "Done. Services will auto-start on login and auto-restart on crash."
echo ""
echo "Controls:"
echo "  launchctl list | grep com.assistant"
echo "  launchctl unload ~/Library/LaunchAgents/com.assistant.<name>.plist"
echo "  launchctl load   ~/Library/LaunchAgents/com.assistant.<name>.plist"
echo "  bash scripts/install-launchd.sh uninstall"
