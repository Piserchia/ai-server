#!/usr/bin/env bash
# scripts/seed-module-skills.sh — ensure every module in .context/modules/ has
# a skills/ directory with stub GOTCHAS.md, PATTERNS.md, DEBUG.md files that
# Claude sessions can append to when they discover something non-obvious.
#
# Idempotent. Safe to re-run. Existing files are never overwritten.
#
# Rationale: PROTOCOL.md expects sessions to append learnings to these files,
# but if the files don't exist, sessions skip the write-back ("no directory
# → no findings"). Having stubs with the expected format reduces that
# friction and gives Claude a template to follow.
#
# Recommended invocation: runs automatically via scripts/bootstrap.sh; can
# also be run manually after adding a new module to .context/modules/.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
MODULES_DIR="$PROJECT_DIR/.context/modules"

if [[ ! -d "$MODULES_DIR" ]]; then
    echo "ERROR: $MODULES_DIR does not exist"
    exit 1
fi

_write_stub() {
    local dest="$1"
    local category="$2"
    local description="$3"
    local when_to_add="$4"

    if [[ -f "$dest" ]]; then
        return 0  # never overwrite existing content
    fi

    cat > "$dest" <<STUB
# $category

> **What this file is for**: $description
>
> **When to add an entry here**: $when_to_add
>
> Append entries newest-first. Each entry should include a date header,
> the symptom or pattern, the fix or approach, and (when possible) a
> reference to the audit log that led to the finding.
>
> This file is seeded empty. Claude sessions working in this module should
> append here when they learn something reusable (see \`.context/PROTOCOL.md\`).

<!-- Append entries below this marker. Do not delete the marker. -->
<!-- APPEND_ENTRIES_BELOW -->
STUB
    echo "  created: $dest"
}

SEEDED=0
for module_dir in "$MODULES_DIR"/*/; do
    module_name=$(basename "$module_dir")
    skills_dir="$module_dir/skills"

    if [[ ! -d "$skills_dir" ]]; then
        mkdir -p "$skills_dir"
        echo "Created $skills_dir"
        SEEDED=$((SEEDED + 1))
    fi

    _write_stub "$skills_dir/GOTCHAS.md" "Gotchas" \
        "Non-obvious traps, unexpected behaviors, and things that look like they should work but don't." \
        "When a session hit a trap — something implicit, an ordering requirement, a race condition, an environment-specific behavior — that a future session should know about before making similar changes."

    _write_stub "$skills_dir/PATTERNS.md" "Patterns" \
        "Correct, reusable patterns for extending or working within this module." \
        "When a session figured out the right way to add a feature, integrate with another module, or extend an existing abstraction — and that right way isn't obvious from the code alone."

    _write_stub "$skills_dir/DEBUG.md" "Debug shortcuts" \
        "Fast paths for diagnosing failures in this module." \
        "When a session debugged a failure and found a useful diagnostic command, a log location that was non-obvious, or an error message whose real meaning differs from its text."
done

if [[ $SEEDED -eq 0 ]]; then
    echo "All modules already have skills/ directories. Stub files written where missing."
else
    echo ""
    echo "Seeded $SEEDED new skills/ directories."
fi
