#!/usr/bin/env bash
# scripts/healthcheck-all.sh — probe every project's healthcheck, update DB.
#
# Designed to run every 5 minutes via launchd (com.assistant.healthcheck-all).
# Fast (< 30s total for dozens of projects). No LLM involved.
#
# Usage:
#   bash scripts/healthcheck-all.sh
set -uo pipefail

# launchd gives us a minimal PATH; add Homebrew so `yq`, `curl`, `psql` resolve.
export PATH="/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG="$PROJECT_DIR/volumes/logs/healthcheck.log"

CHECKED=0
HEALTHY=0
FAILED=0

# Read from manifest files (source of truth, not DB)
while IFS= read -r manifest; do
    SLUG=$(yq '.slug' "$manifest")
    PORT=$(yq '.port // ""' "$manifest")
    HC=$(yq '.healthcheck // ""' "$manifest")
    TYPE=$(yq '.type' "$manifest")

    # Skip static projects (no healthcheck)
    [[ "$TYPE" == "static" ]] && continue
    # Skip if no healthcheck or port configured
    [[ -z "$HC" || -z "$PORT" ]] && continue

    CHECKED=$((CHECKED + 1))
    URL="http://localhost:$PORT$HC"

    if curl -sf --max-time 5 "$URL" > /dev/null 2>&1; then
        psql assistant -qc "UPDATE projects SET last_healthy_at = NOW() WHERE slug = '$SLUG';" > /dev/null 2>&1
        HEALTHY=$((HEALTHY + 1))
    else
        echo "$(date -u +%FT%TZ) FAIL $SLUG $URL" >> "$LOG"
        FAILED=$((FAILED + 1))
    fi

    # Also check sub-services if present
    NUM_SERVICES=$(yq '.services | length' "$manifest" 2>/dev/null || echo 0)
    if [[ "$NUM_SERVICES" -gt 0 ]]; then
        for i in $(seq 0 $((NUM_SERVICES - 1))); do
            SVC_NAME=$(yq ".services[$i].name" "$manifest")
            SVC_PORT=$(yq ".services[$i].port" "$manifest")
            SVC_HC=$(yq ".services[$i].healthcheck // \"\"" "$manifest")
            [[ -z "$SVC_HC" || -z "$SVC_PORT" ]] && continue

            CHECKED=$((CHECKED + 1))
            SVC_URL="http://localhost:$SVC_PORT$SVC_HC"

            if curl -sf --max-time 5 "$SVC_URL" > /dev/null 2>&1; then
                HEALTHY=$((HEALTHY + 1))
            else
                echo "$(date -u +%FT%TZ) FAIL $SLUG/$SVC_NAME $SVC_URL" >> "$LOG"
                FAILED=$((FAILED + 1))
            fi
        done
    fi
done < <(find "$PROJECT_DIR/projects" -name manifest.yml -not -path '*/.git/*' 2>/dev/null)

# Summary (visible in healthcheck.out.log)
echo "$(date -u +%FT%TZ) checked=$CHECKED healthy=$HEALTHY failed=$FAILED"
