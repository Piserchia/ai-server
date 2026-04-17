#!/usr/bin/env bash
# scripts/setup-tunnel.sh — one-time Cloudflare named tunnel setup.
# Prerequisite: domain is in your Cloudflare account with active nameservers.
#
# Usage:
#   bash scripts/setup-tunnel.sh
#
# Interactive: opens a browser for cloudflared login on first run.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Load domain from .env
DOMAIN=$(grep -E '^SERVER_DOMAIN=' "$PROJECT_DIR/.env" | cut -d'=' -f2)
[[ -n "$DOMAIN" ]] || { echo "ERROR: Set SERVER_DOMAIN in .env first"; exit 1; }

echo "=== Cloudflare Tunnel Setup ==="
echo "  Domain: $DOMAIN"
echo ""

# ── Check dependency ──────────────────────────────────────────────────────
command -v cloudflared >/dev/null || { echo "Install: brew install cloudflare/cloudflare/cloudflared"; exit 1; }

# ── Login (opens browser) ────────────────────────────────────────────────
if [[ ! -f "$HOME/.cloudflared/cert.pem" ]]; then
    echo "Opening browser for Cloudflare authentication..."
    cloudflared tunnel login
fi

# ── Create tunnel if missing ─────────────────────────────────────────────
TUNNEL_NAME="ai-server"
if ! cloudflared tunnel list 2>/dev/null | grep -q "$TUNNEL_NAME"; then
    echo "Creating tunnel '$TUNNEL_NAME'..."
    cloudflared tunnel create "$TUNNEL_NAME"
fi

TUNNEL_UUID=$(cloudflared tunnel list 2>/dev/null | awk -v name="$TUNNEL_NAME" '$2 == name { print $1 }')
if [[ -z "$TUNNEL_UUID" ]]; then
    echo "ERROR: Could not determine tunnel UUID. Check: cloudflared tunnel list"
    exit 1
fi
echo "  Tunnel UUID: $TUNNEL_UUID"

# ── Write config ─────────────────────────────────────────────────────────
mkdir -p "$HOME/.cloudflared"
cat > "$HOME/.cloudflared/config.yml" <<EOF
tunnel: $TUNNEL_NAME
credentials-file: $HOME/.cloudflared/$TUNNEL_UUID.json

ingress:
  - hostname: "*.$DOMAIN"
    service: http://localhost:80
  - hostname: "$DOMAIN"
    service: http://localhost:80
  - service: http_status:404
EOF

echo "  Config written to ~/.cloudflared/config.yml"

# ── Route DNS ────────────────────────────────────────────────────────────
echo "Setting up DNS routes..."
cloudflared tunnel route dns "$TUNNEL_NAME" "*.$DOMAIN" 2>&1 | grep -v "already exists" || true
cloudflared tunnel route dns "$TUNNEL_NAME" "$DOMAIN" 2>&1 | grep -v "already exists" || true

# ── Install as system service ────────────────────────────────────────────
# cloudflared service install creates a plist but with wrong arguments.
# We need to: install, fix the plist, copy config to /etc/cloudflared/, then start.
echo ""
echo "Installing cloudflared as system service (requires sudo)..."
sudo cloudflared service uninstall 2>/dev/null || true
sudo cloudflared service install

# Fix plist to include 'tunnel run' subcommand
CFTD_PLIST="/Library/LaunchDaemons/com.cloudflare.cloudflared.plist"
if [[ -f "$CFTD_PLIST" ]]; then
    sudo sed -i.bak 's|</array>|<string>tunnel</string><string>run</string></array>|' "$CFTD_PLIST"
    sudo rm -f "${CFTD_PLIST}.bak"
fi

# Copy config and credentials to /etc/cloudflared/ (system service runs as root)
sudo mkdir -p /etc/cloudflared
sudo cp "$HOME/.cloudflared/config.yml" /etc/cloudflared/
CREDS_FILE="$HOME/.cloudflared/$TUNNEL_UUID.json"
if [[ -f "$CREDS_FILE" ]]; then
    chmod 644 "$CREDS_FILE" 2>/dev/null || true
    sudo cp "$CREDS_FILE" /etc/cloudflared/
fi

# Restart the service
sudo launchctl bootout system/com.cloudflare.cloudflared 2>/dev/null || true
sudo launchctl bootstrap system "$CFTD_PLIST"
echo "  Service installed and started"

echo ""
echo "=== Tunnel setup complete ==="
echo "  Name:   $TUNNEL_NAME"
echo "  UUID:   $TUNNEL_UUID"
echo "  Domain: $DOMAIN (wildcard + apex)"
echo "  Config: $HOME/.cloudflared/config.yml"
echo ""
echo "Verify:"
echo "  sudo launchctl list | grep cloudflared"
echo "  cloudflared tunnel list"
echo "  curl -I https://$DOMAIN/ (after Caddy is running)"
