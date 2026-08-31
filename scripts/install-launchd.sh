#!/usr/bin/env bash
# install-launchd.sh — install launchd plists so the 3 processes auto-start on login
# and auto-restart on crash.
#
# Usage:
#   bash scripts/install-launchd.sh           # install
#   bash scripts/install-launchd.sh uninstall
#
# NOT installed by this script (documented 2026-08-31, EVALUATION_2026-08-30 F7):
#   - cloudflared: runs as a SYSTEM LaunchDaemon at
#     /Library/LaunchDaemons/com.cloudflare.cloudflared.plist (installed via
#     `sudo cloudflared service install` after `cloudflared tunnel login` +
#     tunnel config). A user-level script must not install system daemons;
#     a rebuild MUST re-install it by hand or the public domain stays dark.
#   - postgresql@15 + redis: Homebrew services (`brew services start ...`).
#   - Caddy + per-project units: scripts/register-project.sh / hosting docs.
#
# KeepAlive semantics (deliberate): SuccessfulExit=false + Crashed=true means
# a crash restarts the service but a CLEAN exit (sys.exit(0), launchctl stop)
# STAYS DOWN until next login/kickstart. That is the intended operator
# behavior — use `launchctl kickstart -k gui/$UID/com.assistant.<name>` to
# restart a healthy service.
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
    for svc in "${SERVICES[@]}" "com.assistant.sync-learnings|"; do
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

# ── Timer: hourly runtime-learnings sync (P0.2) ────────────────────────────
# Publishes runtime-written docs (GOTCHAS/CHANGELOG/Troubleshooting) to the
# origin `runtime-learnings` branch so the dev repo can merge them. See
# scripts/sync-learnings.sh for the single-writer rationale.
SYNC_LABEL="com.assistant.sync-learnings"
SYNC_PLIST="$LAUNCH_DIR/${SYNC_LABEL}.plist"
cat > "$SYNC_PLIST" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${SYNC_LABEL}</string>

  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>-lc</string>
    <string>cd "${PROJECT_DIR}" && bash scripts/sync-learnings.sh</string>
  </array>

  <key>WorkingDirectory</key>
  <string>${PROJECT_DIR}</string>

  <key>StartInterval</key><integer>3600</integer>
  <key>RunAtLoad</key><false/>

  <key>StandardOutPath</key>
  <string>${LOG_DIR}/sync-learnings.out.log</string>
  <key>StandardErrorPath</key>
  <string>${LOG_DIR}/sync-learnings.err.log</string>
</dict>
</plist>
PLIST
launchctl unload "$SYNC_PLIST" 2>/dev/null || true
launchctl load -w "$SYNC_PLIST"
echo "  ✓ $SYNC_LABEL (hourly timer)"

# ── Timers: nightly backup + 5-min healthcheck (DR-critical) ───────────────
# These were previously hand-created and thus ABSENT on a bare-metal rebuild —
# exactly the DR moment they're needed (EVALUATION_2026-07-28 O2). Install a
# nightly backup (04:00) and a 5-minute project healthcheck.
install_timer() {  # $1=label suffix  $2=script  $3=interval-block
  local label="com.assistant.$1"
  local plist="$LAUNCH_DIR/${label}.plist"
  cat > "$plist" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>${label}</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>-lc</string>
    <string>cd "${PROJECT_DIR}" && bash $2</string>
  </array>
  <key>WorkingDirectory</key><string>${PROJECT_DIR}</string>
  $3
  <key>RunAtLoad</key><false/>
  <key>StandardOutPath</key><string>${LOG_DIR}/$1.out.log</string>
  <key>StandardErrorPath</key><string>${LOG_DIR}/$1.err.log</string>
</dict>
</plist>
PLIST
  launchctl unload "$plist" 2>/dev/null || true
  launchctl load -w "$plist"
  echo "  ✓ $label (timer)"
}
install_timer "backup" "scripts/backup.sh" \
  "<key>StartCalendarInterval</key><dict><key>Hour</key><integer>4</integer><key>Minute</key><integer>0</integer></dict>"
install_timer "healthcheck-all" "scripts/healthcheck-all.sh" \
  "<key>StartInterval</key><integer>300</integer>"

echo ""
echo "Done. Services will auto-start on login and auto-restart on crash."
echo ""
echo "Controls:"
echo "  launchctl list | grep com.assistant"
echo "  launchctl unload ~/Library/LaunchAgents/com.assistant.<name>.plist"
echo "  launchctl load   ~/Library/LaunchAgents/com.assistant.<name>.plist"
echo "  bash scripts/install-launchd.sh uninstall"
