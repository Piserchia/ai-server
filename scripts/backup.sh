#!/usr/bin/env bash
# scripts/backup.sh — nightly backup of Postgres + audit_log + recent logs.
# Runs via launchd com.assistant.backup.plist at 04:00 daily.
# No retention cap — 2TB SSD has plenty of space.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="$PROJECT_DIR/volumes/backups"
mkdir -p "$BACKUP_DIR"

STAMP=$(date -u +%Y-%m-%d)
OUT="$BACKUP_DIR/backup-$STAMP.tar.gz"
TMP=$(mktemp -d)

# 1. Postgres dump (plain text, small, grep-friendly)
pg_dump assistant > "$TMP/db.sql"

# 2. Audit log snapshot (last 30 days; older files are already archived by server-upkeep)
find "$PROJECT_DIR/volumes/audit_log" -name '*.jsonl' -mtime -30 \
     -exec cp {} "$TMP/" \; 2>/dev/null || true

# 3. Recent logs (last 7 days)
find "$PROJECT_DIR/volumes/logs" -name '*.log' -mtime -7 \
     -exec cp {} "$TMP/" \; 2>/dev/null || true

# 4. Config snapshot — NEVER include .env (secrets!)
cp "$PROJECT_DIR/.env.example" "$TMP/env.example" 2>/dev/null || true
cp "$PROJECT_DIR/alembic.ini" "$TMP/" 2>/dev/null || true

# 5. Tar it up
tar -czf "$OUT" -C "$TMP" .
rm -rf "$TMP"

# 6. No retention cap — 2TB SSD, keep everything

echo "$(date -u +%FT%TZ) backup $OUT ($(du -h "$OUT" | cut -f1))" \
    >> "$PROJECT_DIR/volumes/logs/backup.log"
