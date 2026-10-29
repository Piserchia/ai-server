#!/usr/bin/env bash
# scripts/install-dev-hooks.sh — dev-repo protected-path commit-msg guard (E9;
# spec §6, §9 Phase-1 row; P0 plan Task 13 Step 6c).
#
# WHY: "protected path" was prose. MISSION §M lists the paths the system may
# never change autonomously, and the dev repo — the only checkout where code
# commits are born (CLAUDE.md single-writer topology) — enforced nothing but a
# CHANGELOG on src/. This makes it mechanical: a staged diff touching a §M
# path is REFUSED unless the commit message carries a trailer
#     Approved-Protected-Path: ap-<id>
# naming the owner's approval.
#
# PHASE-1 LIMIT, stated not hidden: the trailer is checked for PRESENCE and
# SHAPE only. Resolving the id against approvals(kind=protected_path) begins
# with the Phase-2 approvals migration (009); until then the run prints
# "trailer recorded, not resolved". It is never a substitute for the owner
# approval — it is the thing that notices when one is missing. The god
# break-glass (`git commit --no-verify`, skills/god/SKILL.md) is the documented
# bypass and must be pushed in the same session.
#
# Usage:  bash scripts/install-dev-hooks.sh install
#         bash scripts/install-dev-hooks.sh check <paths-file> <message-file>
# `install` honours GIT_DIR (tests point it at a throwaway repo); it is
# idempotent (marker-delimited block) and never overwrites an existing hook.
# Never pipenv: a hook runs under whatever shell git has.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 2

# MISSION §M as it reads today — ALL of its path-shaped items. Two §M items
# are not paths and are enforced elsewhere (deleting a project/skill dir →
# Telegram Y/N; TELEGRAM_ALLOWED_CHAT_IDS → an env NAME inside `.env`, which
# IS listed). Item 2's code half, "the chat-ID/web-auth checks", is
# src/gateway/web.py (`_check_auth`). D6's first half (owner PR) adds
# .claude/settings.json, .claude/settings.local.json and THIS script's list to
# §M; extend this array only with that PR. tests/test_protected_paths_hook.py
# pins the array two-way against MISSION §M.
PROTECTED_PATTERNS=(
  'src/runner/guards.py'
  'scripts/lint_docs.py'
  '.env'
  '.context/PROTOCOL.md'
  'MISSION.md'
  '.context/org/ORG.md'
  'src/gateway/web.py'
  'skills/server-patch/SKILL.md'
  'skills/server-deploy/SKILL.md'
  'skills/new-skill/SKILL.md'
)
TRAILER_RE='^Approved-Protected-Path:[[:space:]]*ap-[A-Za-z0-9_-]{4,}[[:space:]]*$'
MARK_BEGIN='# >>> ai-server protected-path guard >>>'
MARK_END='# <<< ai-server protected-path guard <<<'

hits() {                      # $1 = file of staged paths, one per line
  local p pat
  while IFS= read -r p; do
    [[ -z "$p" ]] && continue
    for pat in "${PROTECTED_PATTERNS[@]}"; do
      [[ "$p" == "$pat" || "$p" == */"$pat" ]] && echo "$p"
    done
  done < "$1" | sort -u
}

cmd_check() {                 # $1 = paths file, $2 = message file
  local touched; touched="$(hits "$1")"
  [[ -z "$touched" ]] && return 0
  echo "protected path(s) in this commit:" >&2
  echo "$touched" | sed 's/^/  /' >&2
  if ! grep -Eq "$TRAILER_RE" "$2"; then
    cat >&2 <<'MSG'
REFUSED: a protected path needs an owner approval (MISSION §M).
  1. get the approval from the owner (approvals kind=protected_path)
  2. add the trailer to the commit message:
       Approved-Protected-Path: ap-<id>
God break-glass: skills/god/SKILL.md documents the bypass (--no-verify); a
bypassed commit must be pushed in the same session.
MSG
    return 1
  fi
  local id; id="$(grep -Eo 'ap-[A-Za-z0-9_-]{4,}' "$2" | head -1)"
  echo "protected path approved by $id (trailer present)" >&2
  echo "note: approvals row not resolved here — trailer recorded only; resolution begins with the Phase-2 approvals migration (009)" >&2
  return 0
}

cmd_install() {
  # commit-msg, NOT the CHANGELOG hook: git hands the message file to
  # commit-msg as $1 and passes the other hook no arguments at all (where the
  # editor file still holds the PREVIOUS commit's message). The CHANGELOG hook
  # is a separate file and is not touched.
  local git_dir="${GIT_DIR:-.git}"
  local hook="$git_dir/hooks/commit-msg"
  mkdir -p "$git_dir/hooks"
  local block
  block="$MARK_BEGIN
staged=\$(mktemp)
git diff --cached --name-only --diff-filter=ACMRD > \"\$staged\"
bash scripts/install-dev-hooks.sh check \"\$staged\" \"\$1\" || { rm -f \"\$staged\"; exit 1; }
rm -f \"\$staged\"
$MARK_END"
  if [[ -f "$hook" ]]; then
    if grep -qF "$MARK_BEGIN" "$hook"; then          # idempotent re-arm
      awk -v b="$MARK_BEGIN" -v e="$MARK_END" '
        $0==b{skip=1} !skip{print} $0==e{skip=0}' "$hook" > "$hook.tmp"
      printf '%s\n' "$block" >> "$hook.tmp" && mv "$hook.tmp" "$hook"
    else
      printf '\n%s\n' "$block" >> "$hook"     # append, never overwrite an existing hook
    fi
  else
    printf '#!/usr/bin/env bash\nset -uo pipefail\n%s\n' "$block" > "$hook"
  fi
  chmod +x "$hook"
  echo "installed/re-armed the protected-path guard in $hook"
  echo "note: the CHANGELOG guard is a separate hook file and was not touched"
}

case "${1:-}" in
  install) cmd_install ;;
  check)   [[ $# -eq 3 ]] || { echo "usage: $0 check <paths-file> <message-file>" >&2; exit 2; }
           cmd_check "$2" "$3" ;;
  *) echo "usage: $0 install | check <paths-file> <message-file>" >&2; exit 2 ;;
esac
