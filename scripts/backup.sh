#!/usr/bin/env bash
# scripts/backup.sh — nightly backup of Postgres + audit_log + recent logs.
# Runs via launchd com.assistant.backup.plist at 04:00 daily.
# No retention cap — 2TB SSD has plenty of space.
set -euo pipefail

# launchd provides a minimal PATH; Homebrew tools (pg_dump, tar helpers, rclone)
# live outside it. Explicit PATH so the 04:00 timer works (exit-127 incident,
# broken since 2026-04; see EVALUATION_2026-07-10 §3.7).
export PATH="/opt/homebrew/opt/postgresql@15/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

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

# 6. Off-site replication — push the tarball off this disk so a single hardware
#    failure can't erase the DB, audit logs, AND every backup at once.
#    Guarded: absence of rclone / the 'r2' remote is not an error, and a failed
#    upload NEVER fails the local backup (the local copy is the source of truth).
#    Human one-time setup: create R2 bucket 'ai-server-backups' + API token, then
#    `rclone config` a remote named 'r2'. See docs — no secrets live in the repo.
if command -v rclone >/dev/null 2>&1 && rclone listremotes 2>/dev/null | grep -q '^r2:'; then
    if rclone copy "$OUT" r2:ai-server-backups/ --no-traverse 2>>"$PROJECT_DIR/volumes/logs/backup.log"; then
        echo "$(date -u +%FT%TZ) offsite OK r2:ai-server-backups/$(basename "$OUT")" \
            >> "$PROJECT_DIR/volumes/logs/backup.log"
    else
        echo "$(date -u +%FT%TZ) WARN off-site upload failed for $OUT" \
            >> "$PROJECT_DIR/volumes/logs/backup.log"
    fi
else
    echo "$(date -u +%FT%TZ) offsite SKIP (rclone or r2: remote not configured)" \
        >> "$PROJECT_DIR/volumes/logs/backup.log"
fi

# 7. No retention cap locally — 2TB SSD, keep everything

echo "$(date -u +%FT%TZ) backup $OUT ($(du -h "$OUT" | cut -f1))" \
    >> "$PROJECT_DIR/volumes/logs/backup.log"
