#!/usr/bin/env bash
# scripts/restore-drill.sh — prove the newest backup restores (Observability
# Phase 1 exit criterion "the restore drill passes", spec §9; C1 of the re-cut
# plan). OWNER-RUN, by hand, on the production checkout (dev's volumes/backups
# is empty). Touches no live state: restores the newest tarball's db.sql and
# the newest atlas-*.dump into the throwaway databases restore_drill_assistant
# / restore_drill_atlas, counts `jobs` rows and one atlas table, unseals the
# secrets bundle into a temp dir and counts entry NAMES only (values are never
# printed), then drops both throwaways. Prints one PASS/WARN/FAIL line per leg
# and a final verdict; exit 0 (PASS, WARNs allowed) / 1 (any FAIL); one line
# appended to volumes/logs/backup.log.
#
# Legs: assistant restore (FAIL if it cannot restore or has 0 jobs rows) ·
# atlas restore (WARN when no atlas-*.dump exists; FAIL if the dump does not
# restore) · sealed secrets (WARN when the tarball has no bundle or there is
# no key; FAIL when a key is present and the bundle will not unseal) ·
# off-site copy (informational WARN only).
#
# Usage: bash scripts/restore-drill.sh [path/to/backup-YYYY-MM-DD.tar.gz]
set -uo pipefail
# APPENDED, not prepended: the operator's shell PATH wins (and so do a test's
# fake pg tools); the Homebrew dirs are only a fallback for a bare shell.
export PATH="$PATH:/opt/homebrew/opt/postgresql@15/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="$PROJECT_DIR/volumes/backups"
LOG="$PROJECT_DIR/volumes/logs/backup.log"
SEAL_KEY="${BACKUP_SEAL_KEY:-$HOME/.config/ai-server/backup-seal.key}"
DB="restore_drill_assistant"
ATLAS_DB="restore_drill_atlas"
mkdir -p "$(dirname "$LOG")"

TARBALL="${1:-$(ls -t "$BACKUP_DIR"/backup-*.tar.gz 2>/dev/null | head -1)}"
if [[ -z "$TARBALL" || ! -f "$TARBALL" ]]; then
    echo "FAIL no backup tarball in $BACKUP_DIR"
    echo "$(date -u +%FT%TZ) restore-drill (none) result=FAIL no tarball" >> "$LOG"
    exit 1
fi
ATLAS_DUMP="$(ls -t "$BACKUP_DIR"/atlas-*.dump 2>/dev/null | head -1 || true)"

TMP=$(mktemp -d)
fail=0
cleanup() {
    dropdb --if-exists "$DB" 2>/dev/null || true
    dropdb --if-exists "$ATLAS_DB" 2>/dev/null || true
    rm -rf "$TMP"
}
trap cleanup EXIT

if ! tar -xzf "$TARBALL" -C "$TMP"; then
    echo "FAIL untar $TARBALL"
    echo "$(date -u +%FT%TZ) restore-drill $(basename "$TARBALL") result=FAIL untar" >> "$LOG"
    exit 1
fi
echo "drill: $(basename "$TARBALL")${ATLAS_DUMP:+ + $(basename "$ATLAS_DUMP")}"

# 1. assistant DB → throwaway; must contain jobs rows.
dropdb --if-exists "$DB" 2>/dev/null || true
if [[ -s "$TMP/db.sql" ]] && createdb "$DB" 2>/dev/null \
        && psql -q -v ON_ERROR_STOP=0 "$DB" < "$TMP/db.sql" > /dev/null 2>&1; then
    n=$(psql -tAc "SELECT count(*) FROM jobs" "$DB" 2>/dev/null || echo 0)
    if [[ "$n" =~ ^[0-9]+$ ]] && (( n > 0 )); then
        echo "PASS assistant restore: $n jobs"
    else
        echo "FAIL assistant restore: jobs=$n"; fail=1
    fi
else
    echo "FAIL assistant restore (db.sql missing, createdb or psql failed)"; fail=1
fi

# 2. atlas DB (custom-format dump beside the tarball since C1, D-P1-6).
if [[ -n "$ATLAS_DUMP" && -s "$ATLAS_DUMP" ]]; then
    dropdb --if-exists "$ATLAS_DB" 2>/dev/null || true
    if createdb "$ATLAS_DB" 2>/dev/null \
            && pg_restore --no-owner --no-privileges -d "$ATLAS_DB" "$ATLAS_DUMP" > /dev/null 2>&1; then
        table=$(psql -tAc "SELECT table_schema||'.'||table_name FROM information_schema.tables WHERE table_schema NOT IN ('pg_catalog','information_schema') AND table_type='BASE TABLE' ORDER BY 1 LIMIT 1" "$ATLAS_DB" 2>/dev/null || true)
        if [[ -n "$table" ]]; then
            rows=$(psql -tAc "SELECT count(*) FROM $table" "$ATLAS_DB" 2>/dev/null || echo "?")
            echo "PASS atlas restore: $table $rows rows"
        else
            echo "FAIL atlas restore: no tables after pg_restore"; fail=1
        fi
    else
        # pg_restore exits non-zero on ANY warning (e.g. missing extensions);
        # a restore with tables present still counts.
        table=$(psql -tAc "SELECT table_schema||'.'||table_name FROM information_schema.tables WHERE table_schema NOT IN ('pg_catalog','information_schema') AND table_type='BASE TABLE' ORDER BY 1 LIMIT 1" "$ATLAS_DB" 2>/dev/null || true)
        if [[ -n "$table" ]]; then
            rows=$(psql -tAc "SELECT count(*) FROM $table" "$ATLAS_DB" 2>/dev/null || echo "?")
            echo "PASS atlas restore (pg_restore warned): $table $rows rows"
        else
            echo "FAIL atlas restore (createdb/pg_restore)"; fail=1
        fi
    fi
else
    echo "WARN atlas dump absent in $BACKUP_DIR (backup predates C1, or the atlas DB is missing)"
fi

# 3. Sealed secrets: unseal + count entry NAMES only (values never printed).
if [[ -s "$TMP/secrets.tar.enc" ]]; then
    if [[ ! -r "$SEAL_KEY" ]]; then
        echo "WARN sealed bundle present but no seal key at $SEAL_KEY (runbook §3)"
    elif openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 \
            -in "$TMP/secrets.tar.enc" -out "$TMP/secrets.tar" -pass file:"$SEAL_KEY" 2>/dev/null; then
        names=$(tar -tf "$TMP/secrets.tar" 2>/dev/null || true)
        if printf '%s\n' "$names" | grep -qx 'secrets/env'; then
            echo "PASS sealed secrets: $(printf '%s\n' "$names" | grep -c .) entries"
        else
            echo "FAIL sealed bundle lacks secrets/env"; fail=1
        fi
        rm -f "$TMP/secrets.tar"
    else
        echo "FAIL cannot unseal (wrong key at $SEAL_KEY?)"; fail=1
    fi
else
    echo "WARN no sealed secrets in this backup (seal key absent when it ran? runbook §3)"
fi

# 4. Off-site copy (informational — the drill is about restorability).
if command -v rclone >/dev/null 2>&1 && rclone listremotes 2>/dev/null | grep -q '^r2:'; then
    if rclone lsf "r2:ai-server-backups/$(basename "$TARBALL")" 2>/dev/null | grep -q .; then
        echo "PASS off-site copy present"
    else
        echo "WARN off-site copy of $(basename "$TARBALL") not found"
    fi
else
    echo "WARN off-site: rclone r2: remote not configured (runbook §2)"
fi

verdict=$([[ $fail == 0 ]] && echo PASS || echo FAIL)
echo "$(date -u +%FT%TZ) restore-drill $(basename "$TARBALL") result=$verdict" >> "$LOG"
echo "$verdict"
exit $fail
