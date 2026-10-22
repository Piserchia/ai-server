#!/usr/bin/env bash
# scripts/backup.sh — nightly backup of Postgres + audit_log + recent logs.
# Runs via launchd com.assistant.backup.plist at 04:00 daily.
# Retention: 60 days locally and off-site for the tarball, 7 days locally /
# 35 days off-site for the atlas dump (step 7, D-P1-6). The root disk on this
# host is 228 GB with ~75 GB free (2026-10-21) — "keep everything" never fit.
set -euo pipefail

# launchd provides a minimal PATH; Homebrew tools (pg_dump, tar helpers, rclone)
# live outside it. Explicit PATH so the 04:00 timer works (exit-127 incident,
# broken since 2026-04; see EVALUATION_2026-07-10 §3.7).
export PATH="/opt/homebrew/opt/postgresql@15/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="$PROJECT_DIR/volumes/backups"
LOG="$PROJECT_DIR/volumes/logs/backup.log"
mkdir -p "$BACKUP_DIR" "$(dirname "$LOG")"

STAMP=$(date -u +%Y-%m-%d)
OUT="$BACKUP_DIR/backup-$STAMP.tar.gz"
ATLAS_DUMP="$BACKUP_DIR/atlas-$STAMP.dump"
TMP=$(mktemp -d)
SEAL_TMP=""
# A run killed mid-way (launchd unload, ENOSPC under set -e, SIGTERM) must not
# leave db.sql or the 4b plaintext secret copies under $TMPDIR.
trap 'rm -rf "$TMP" "${SEAL_TMP:-}"' EXIT

# 1. Postgres dumps. `assistant` is the server DB (plain text, small,
#    grep-friendly — travels inside the tarball). `atlas` (the trading
#    verticals, 5.9 GB on 2026-10-21) was dumped nowhere until Observability
#    Phase 1 C1 (D-P1-6): custom-format (`-Fc`, compressed, pg_restore-able)
#    to its OWN file beside the tarball, only when the database exists, never
#    fatal, size logged. A plain dump inside a 60-day tarball series does not
#    fit the disk; the dump has its own retention (step 7).
pg_dump assistant > "$TMP/db.sql"
# One query, no pipeline: a `psql -l | … | grep -q` chain under pipefail can report
# "no atlas database" on SIGPIPE when grep exits early.
if [[ "$(psql -tAc "SELECT 1 FROM pg_database WHERE datname = 'atlas'" 2>/dev/null)" == "1" ]]; then
    if pg_dump -Fc atlas > "$BACKUP_DIR/atlas-$STAMP.dump" 2>>"$LOG"; then
        echo "$(date -u +%FT%TZ) atlas dump OK ($(du -h "$ATLAS_DUMP" | cut -f1)) $ATLAS_DUMP" >> "$LOG"
    else
        echo "$(date -u +%FT%TZ) WARN atlas dump failed" >> "$LOG"
        rm -f "$ATLAS_DUMP"
    fi
else
    echo "$(date -u +%FT%TZ) atlas dump SKIP (no atlas database)" >> "$LOG"
fi

# 2. Audit log snapshot (last 30 days; older files are already archived by server-upkeep)
find "$PROJECT_DIR/volumes/audit_log" -name '*.jsonl' -mtime -30 \
     -exec cp {} "$TMP/" \; 2>/dev/null || true

# 3. Recent logs (last 7 days)
find "$PROJECT_DIR/volumes/logs" -name '*.log' -mtime -7 \
     -exec cp {} "$TMP/" \; 2>/dev/null || true

# 4. Config snapshot — plain copies NEVER include .env; secrets travel only in
#    the sealed bundle (4b).
cp "$PROJECT_DIR/.env.example" "$TMP/env.example" 2>/dev/null || true
cp "$PROJECT_DIR/alembic.ini" "$TMP/" 2>/dev/null || true

# 4b. Sealed secrets (Observability Phase 1 C1, spec §9 / D5): the server
#     .env, the atlas CANONICAL .env (the dev clone ~/Documents/repos/atlas —
#     the file provision_env_files copies from; the runtime clone's is a
#     different file) and ~/.cloudflared/{config.yml,cert.pem,<tunnel>.json},
#     tar'd and AES-256 encrypted with a key that lives OUTSIDE every backup
#     (~/.config/ai-server/backup-seal.key — owner-created, chmod 600, copy in
#     the password manager; runbook docs/runbooks/2026-10-21-phase1-ops-hygiene.md
#     §3). No key → SKIP (logged). Never fatal. Restore: scripts/restore-drill.sh.
SEAL_KEY="${BACKUP_SEAL_KEY:-$HOME/.config/ai-server/backup-seal.key}"
ATLAS_ENV="${ATLAS_ENV:-$HOME/Documents/repos/atlas/.env}"
if [[ -r "$SEAL_KEY" ]]; then
    SEAL_TMP=$(mktemp -d)
    mkdir -p "$SEAL_TMP/secrets/cloudflared"
    cp "$PROJECT_DIR/.env" "$SEAL_TMP/secrets/env" 2>/dev/null || true
    cp "$ATLAS_ENV" "$SEAL_TMP/secrets/atlas.env" 2>/dev/null || true
    cp "$HOME"/.cloudflared/config.yml "$HOME"/.cloudflared/cert.pem "$HOME"/.cloudflared/*.json \
        "$SEAL_TMP/secrets/cloudflared/" 2>/dev/null || true
    # Name what did NOT land (the cp's are `|| true`; tar+openssl succeed on an
    # empty tree). A plain string, not an array: under launchd this is
    # /bin/bash 3.2, where an empty array under set -u is an error. Whatever
    # landed is still sealed — the drill's `FAIL … lacks secrets/env` is the
    # stronger signal and keeps firing.
    missing=""
    [[ -s "$SEAL_TMP/secrets/env" ]]                    || missing="$missing env"
    [[ -s "$SEAL_TMP/secrets/atlas.env" ]]              || missing="$missing atlas.env"
    [[ -s "$SEAL_TMP/secrets/cloudflared/config.yml" ]] || missing="$missing cloudflared"
    if tar -cf "$SEAL_TMP/secrets.tar" -C "$SEAL_TMP" secrets 2>>"$LOG" \
        && openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -salt \
            -in "$SEAL_TMP/secrets.tar" -out "$TMP/secrets.tar.enc" \
            -pass file:"$SEAL_KEY" 2>>"$LOG"; then
        if [[ -z "$missing" ]]; then
            echo "$(date -u +%FT%TZ) sealed secrets OK (env, atlas.env, cloudflared)" >> "$LOG"
        else
            echo "$(date -u +%FT%TZ) WARN sealed secrets PARTIAL (missing:$missing) — check ATLAS_ENV=$ATLAS_ENV and ~/.cloudflared; bundle still written" >> "$LOG"
        fi
    else
        echo "$(date -u +%FT%TZ) WARN sealing failed (bundle omitted)" >> "$LOG"
        rm -f "$TMP/secrets.tar.enc"
    fi
    rm -rf "$SEAL_TMP"; SEAL_TMP=""
else
    echo "$(date -u +%FT%TZ) seal SKIP (no key at $SEAL_KEY)" >> "$LOG"
fi

# 5. Tar it up (the EXIT trap removes $TMP; an early rm keeps the window short)
tar -czf "$OUT" -C "$TMP" .
rm -rf "$TMP"

# 6. Off-site replication — push the tarball off this disk so a single hardware
#    failure can't erase the DB, audit logs, AND every backup at once.
#    Guarded: absence of rclone / the 'r2' remote is not an error, and a failed
#    upload NEVER fails the local backup (the local copy is the source of truth).
#    Human one-time setup: create R2 bucket 'ai-server-backups' + API token, then
#    `rclone config` a remote named 'r2' (runbook §2). No secrets live in the repo.
#    The atlas dump goes up on SUNDAYS only (D-P1-6: R2 is free ≤ 10 GB-month).
if command -v rclone >/dev/null 2>&1 && rclone listremotes 2>/dev/null | grep -q '^r2:'; then
    if rclone copy "$OUT" r2:ai-server-backups/ --no-traverse 2>>"$LOG"; then
        echo "$(date -u +%FT%TZ) offsite OK r2:ai-server-backups/$(basename "$OUT")" >> "$LOG"
        # 60-day retention off-site (spec §12a row 4): R2 is free only under
        # 10 GB-month on a card-on-file account, and every nightly tarball now
        # carries the sealed bundle. An unpruned bucket grows one tarball a
        # day forever.
        if rclone delete r2:ai-server-backups/ --min-age 60d --include 'backup-*.tar.gz' 2>>"$LOG"; then
            echo "$(date -u +%FT%TZ) offsite prune OK (>60d)" >> "$LOG"
        else
            echo "$(date -u +%FT%TZ) WARN offsite prune failed" >> "$LOG"
        fi
    else
        echo "$(date -u +%FT%TZ) WARN off-site upload failed for $OUT" >> "$LOG"
    fi
    if [[ "$(date -u +%u)" == "7" && -s "$ATLAS_DUMP" ]]; then
        if rclone copy "$ATLAS_DUMP" r2:ai-server-backups/ --no-traverse 2>>"$LOG"; then
            echo "$(date -u +%FT%TZ) offsite OK r2:ai-server-backups/$(basename "$ATLAS_DUMP") (weekly atlas dump)" >> "$LOG"
        else
            echo "$(date -u +%FT%TZ) WARN off-site upload failed for $ATLAS_DUMP" >> "$LOG"
        fi
        if rclone delete r2:ai-server-backups/ --min-age 35d --include 'atlas-*' 2>>"$LOG"; then
            echo "$(date -u +%FT%TZ) offsite prune OK (atlas >35d)" >> "$LOG"
        else
            echo "$(date -u +%FT%TZ) WARN offsite atlas prune failed" >> "$LOG"
        fi
    fi
else
    echo "$(date -u +%FT%TZ) offsite SKIP (rclone or r2: remote not configured)" >> "$LOG"
fi

# 7. Local retention: 60 days for the tarball (matching the off-site rule, so
#    the drill always has recent tarballs on both sides), 7 days for the atlas
#    dump (D-P1-6 — 5.9 GB uncompressed; the owner re-sizes after the first
#    measured `-Fc` size lands in the plan's §8).
find "$BACKUP_DIR" -name 'backup-*.tar.gz' -mtime +60 -delete 2>/dev/null || true
find "$BACKUP_DIR" -name 'atlas-*.dump' -mtime +7 -delete 2>/dev/null || true

echo "$(date -u +%FT%TZ) backup $OUT ($(du -h "$OUT" | cut -f1))" >> "$LOG"
