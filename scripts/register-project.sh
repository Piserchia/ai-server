#!/usr/bin/env bash
# scripts/register-project.sh — register a project with Caddy, launchd, and Postgres.
#
# Reads projects/<slug>/manifest.yml and generates:
#   - Caddyfile.d/<slug>.conf
#   - ~/Library/LaunchAgents/com.assistant.project.<slug>.plist (service-type only)
#   - projects table row (slug, subdomain, type, port, manifest_path)
#
# For multi-service projects (manifest has `services` array), generates additional
# launchd plists and Caddy handle blocks for each sub-service.
#
# Idempotent: running twice with no manifest changes is a no-op.
#
# Usage:
#   bash scripts/register-project.sh <slug> [--dry-run]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

DRY_RUN=false
if [[ "${2:-}" == "--dry-run" ]]; then DRY_RUN=true; fi

SLUG="${1:?Usage: $0 <slug> [--dry-run]}"
MANIFEST="$PROJECT_DIR/projects/$SLUG/manifest.yml"
[[ -f "$MANIFEST" ]] || { echo "ERROR: No manifest at $MANIFEST"; exit 1; }

# ── Load domain from .env ────────────────────────────────────────────────
DOMAIN=$(grep -E '^SERVER_DOMAIN=' "$PROJECT_DIR/.env" | cut -d'=' -f2)
[[ -n "$DOMAIN" ]] || { echo "ERROR: SERVER_DOMAIN not set in .env"; exit 1; }

# ── Parse manifest ───────────────────────────────────────────────────────
TYPE=$(yq '.type' "$MANIFEST")
SUBDOMAIN=$(yq '.subdomain' "$MANIFEST")
PORT=$(yq '.port // ""' "$MANIFEST")
HEALTHCHECK=$(yq '.healthcheck // ""' "$MANIFEST")
START_CMD=$(yq '.start_command // ""' "$MANIFEST")
WEB_ROOT=$(yq '.web_root // ""' "$MANIFEST")
NUM_SERVICES=$(yq '.services | length' "$MANIFEST" 2>/dev/null || echo 0)

HOSTNAME="${SUBDOMAIN}.${DOMAIN}"
SNIPPET_PATH="$PROJECT_DIR/Caddyfile.d/$SLUG.conf"
PLIST_PATH="$HOME/Library/LaunchAgents/com.assistant.project.$SLUG.plist"
LOG_DIR="$PROJECT_DIR/volumes/logs"

echo "=== Registering project: $SLUG ==="
echo "  Type:      $TYPE"
echo "  Hostname:  $HOSTNAME"
[[ -n "$PORT" ]] && echo "  Port:      $PORT"
echo ""

# ── Generate Caddy snippet ───────────────────────────────────────────────
TMP_SNIPPET=$(mktemp)

case "$TYPE" in
  static)
    SERVE_DIR="$PROJECT_DIR/projects/$SLUG"
    [[ -n "$WEB_ROOT" ]] && SERVE_DIR="$SERVE_DIR/$WEB_ROOT"
    cat > "$TMP_SNIPPET" <<EOF
http://$HOSTNAME {
    root * "$SERVE_DIR"
    file_server
}
EOF
    ;;
  service|api)
    [[ -n "$PORT" ]] || { echo "ERROR: Port required for type '$TYPE'"; rm -f "$TMP_SNIPPET"; exit 1; }

    # Start building the Caddy block
    {
      echo "http://$HOSTNAME {"

      # If there are sub-services, add handle blocks for their API routes and path prefixes
      if [[ "$NUM_SERVICES" -gt 0 ]]; then
        for i in $(seq 0 $((NUM_SERVICES - 1))); do
          SVC_PORT=$(yq ".services[$i].port" "$MANIFEST")
          SVC_API_ROUTES=$(yq ".services[$i].api_routes[]" "$MANIFEST" 2>/dev/null || true)
          SVC_PATH_PREFIX=$(yq ".services[$i].path_prefix // \"\"" "$MANIFEST")

          # API route handlers (no path stripping)
          if [[ -n "$SVC_API_ROUTES" ]]; then
            while IFS= read -r route; do
              [[ -n "$route" ]] || continue
              echo "    handle $route {"
              echo "        reverse_proxy localhost:$SVC_PORT"
              echo "    }"
            done <<< "$SVC_API_ROUTES"
          fi

          # Path prefix handler (strip prefix before forwarding)
          if [[ -n "$SVC_PATH_PREFIX" ]]; then
            echo "    handle_path ${SVC_PATH_PREFIX}/* {"
            echo "        reverse_proxy localhost:$SVC_PORT"
            echo "    }"
          fi
        done
      fi

      # Default handler: main service
      echo "    handle {"
      echo "        reverse_proxy localhost:$PORT"
      echo "    }"
      echo "}"
    } > "$TMP_SNIPPET"
    ;;
  *)
    echo "ERROR: Unknown type: $TYPE"
    rm -f "$TMP_SNIPPET"
    exit 1
    ;;
esac

# Idempotence: skip if unchanged
SNIPPET_CHANGED=true
if [[ -f "$SNIPPET_PATH" ]] && diff -q "$SNIPPET_PATH" "$TMP_SNIPPET" > /dev/null 2>&1; then
    SNIPPET_CHANGED=false
fi

# ── Dry-run output ───────────────────────────────────────────────────────
if $DRY_RUN; then
    echo "[dry-run] Would write $SNIPPET_PATH (changed: $SNIPPET_CHANGED)"
    echo "[dry-run] Caddy config:"
    cat "$TMP_SNIPPET" | sed 's/^/    /'
    [[ "$TYPE" != "static" ]] && echo "[dry-run] Would write $PLIST_PATH"
    if [[ "$NUM_SERVICES" -gt 0 ]]; then
        for i in $(seq 0 $((NUM_SERVICES - 1))); do
            SVC_NAME=$(yq ".services[$i].name" "$MANIFEST")
            echo "[dry-run] Would write com.assistant.project.$SLUG-$SVC_NAME.plist"
        done
    fi
    echo "[dry-run] Would upsert projects row for '$SLUG'"
    rm -f "$TMP_SNIPPET"
    exit 0
fi

# ── Commit the snippet ───────────────────────────────────────────────────
mkdir -p "$(dirname "$SNIPPET_PATH")" "$LOG_DIR"
mv "$TMP_SNIPPET" "$SNIPPET_PATH"
echo "  Wrote $SNIPPET_PATH"

# ── Generate launchd plist for main service ──────────────────────────────
_write_plist() {
    local label="$1" working_dir="$2" cmd="$3" log_name="$4" plist_file="$5"

    cat > "$plist_file" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$label</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>-lc</string>
    <string>cd "$working_dir" && $cmd</string>
  </array>
  <key>WorkingDirectory</key>
  <string>$working_dir</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>$HOME/.pyenv/shims:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
    <key>PYENV_ROOT</key>
    <string>$HOME/.pyenv</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key>
  <dict>
    <key>SuccessfulExit</key><false/>
    <key>Crashed</key><true/>
  </dict>
  <key>StandardOutPath</key>
  <string>$LOG_DIR/$log_name.out.log</string>
  <key>StandardErrorPath</key>
  <string>$LOG_DIR/$log_name.err.log</string>
  <key>ThrottleInterval</key><integer>30</integer>
</dict>
</plist>
PLIST
    launchctl unload "$plist_file" 2>/dev/null || true
    launchctl load -w "$plist_file"
    echo "  Started $label"
}

if [[ "$TYPE" == "service" || "$TYPE" == "api" ]]; then
    PROJ_DIR="$PROJECT_DIR/projects/$SLUG"
    _write_plist \
        "com.assistant.project.$SLUG" \
        "$PROJ_DIR" \
        "$START_CMD" \
        "project.$SLUG" \
        "$PLIST_PATH"

    # Sub-services
    if [[ "$NUM_SERVICES" -gt 0 ]]; then
        for i in $(seq 0 $((NUM_SERVICES - 1))); do
            SVC_NAME=$(yq ".services[$i].name" "$MANIFEST")
            SVC_CMD=$(yq ".services[$i].start_command" "$MANIFEST")
            SVC_PLIST="$HOME/Library/LaunchAgents/com.assistant.project.$SLUG-$SVC_NAME.plist"
            _write_plist \
                "com.assistant.project.$SLUG-$SVC_NAME" \
                "$PROJ_DIR" \
                "$SVC_CMD" \
                "project.$SLUG-$SVC_NAME" \
                "$SVC_PLIST"
        done
    fi
fi

# ── Reload Caddy ─────────────────────────────────────────────────────────
if $SNIPPET_CHANGED; then
    echo "  Reloading Caddy..."
    caddy reload --config "$PROJECT_DIR/Caddyfile" 2>&1 | tail -3 || true
fi

# ── Upsert into projects table ───────────────────────────────────────────
PORT_VAL="NULL"
[[ -n "$PORT" ]] && PORT_VAL="$PORT"

psql assistant -v ON_ERROR_STOP=1 <<SQL
INSERT INTO projects (id, slug, subdomain, type, port, manifest_path, created_at)
VALUES (
    gen_random_uuid(),
    '$SLUG',
    '$HOSTNAME',
    '$TYPE',
    $PORT_VAL,
    '$MANIFEST',
    NOW()
)
ON CONFLICT (slug) DO UPDATE SET
    subdomain = EXCLUDED.subdomain,
    type = EXCLUDED.type,
    port = EXCLUDED.port,
    manifest_path = EXCLUDED.manifest_path;
SQL

echo "  Upserted projects row"

# ── Healthcheck probe (service-type only) ─────────────────────────────────
if [[ "$TYPE" != "static" && -n "$HEALTHCHECK" ]]; then
    echo ""
    echo "Waiting for healthcheck at http://localhost:$PORT$HEALTHCHECK ..."
    for _ in $(seq 1 30); do
        if curl -sf "http://localhost:$PORT$HEALTHCHECK" > /dev/null; then
            echo ""
            echo "=== $SLUG registered and healthy at https://$HOSTNAME ==="
            exit 0
        fi
        sleep 1
        printf "."
    done
    echo ""
    echo "WARNING: $SLUG did not pass healthcheck within 30s"
    echo "  Check: tail $LOG_DIR/project.$SLUG.err.log"
    exit 2
fi

echo ""
echo "=== $SLUG registered at https://$HOSTNAME ==="
