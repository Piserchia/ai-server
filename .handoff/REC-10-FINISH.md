# Rec 10: Proposal tracking — finish and ship

## TL;DR

~95% of Rec 10 was built in repeated chat sandboxes but never committed.
See `REC-10-FILES/` for the full content of every new/modified file.

Two ways to get the work back into a fresh working tree:

**Option A (preferred — fastest):** recreate each file by copying content
from `REC-10-FILES/` into the repo at the indicated paths. This is
guaranteed to apply cleanly.

**Option B:** try `git apply .handoff/rec-10-current-diff.patch` first. If
it applies cleanly, you're done — skip to the "Remaining items" section
below. If it fails (likely if the patch was generated against a slightly
different base), fall back to Option A.

---

## Files to recreate (Option A)

### New files

| Path | Source in handoff |
|------|-------------------|
| `alembic/versions/002_proposals_table.py` | `REC-10-FILES/alembic-002.py` |
| `src/runner/proposals.py` | `REC-10-FILES/proposals.py` |
| `tests/test_proposals.py` | `REC-10-FILES/test_proposals.py` |

### Modified files (edit in place; see `REC-10-FILES/EDITS.md` for exact patches)

| Path | Edits |
|------|-------|
| `src/models.py` | Add ProposalChangeType + ProposalOutcome enums after ProjectType; append Proposal ORM class at end |
| `src/gateway/telegram_bot.py` | 4 edits: module docstring, cmd_proposals handler (after cmd_resume), register CommandHandler, help text |
| `skills/review-and-improve/SKILL.md` | 2 edits: Gotchas bullet (CHANGELOG grep → proposals table check), insert "Proposal tracking (Rec 10)" section before Gotchas |
| `skills/server-patch/SKILL.md` | Insert "### 9. Mark proposal applied" section before `## Gotchas` |
| `.context/SYSTEM.md` | 2 edits: models.py row lists Proposal, add proposals.py row |
| `.context/modules/db/CONTEXT.md` | 2 edits: `Schema (3 tables)` → `Schema (4 tables)` with proposals detail; migrations section references 002 |
| `.context/modules/db/CHANGELOG.md` | Prepend Rec 10 entry |
| `.context/modules/gateway/CHANGELOG.md` | Prepend Rec 10 entry |

---

## Remaining items (things NOT yet in the sandbox)

### 1. `.context/modules/runner/CHANGELOG.md`

Prepend this entry **just after** the `<!-- Newest entries at top. -->` comment,
**before** the existing `## 2026-04-18 — Added learning extractor post-session hook (Rec 1)` entry:

```markdown
## 2026-04-18 — Added proposals.py helper module (Rec 10)

**Files changed**:
- `src/runner/proposals.py` (NEW, ~230 lines) — pure helpers + async DB
  ops for proposal tracking table. Public interface: `extract_proposal_id`,
  `is_valid_change_type`, `is_valid_outcome`, `format_proposal_line`,
  `find_recent_duplicate`, `insert_proposal`, `mark_proposal_merged`,
  `list_pending_proposals`, `list_recent_proposals`, `get_proposal_by_id_prefix`.

**Why**: Supports the `/proposals` Telegram command + dedup/merge-stamping
in the review-and-improve and server-patch skills per § 7 Rec 10.

**Side effects**: None on runner execution — this module is imported lazily
by the Telegram handler and by skills that need it.
```

### 2. `.context/modules/runner/CONTEXT.md`

Two edits:

**Edit 2a**: Add `src/runner/proposals.py` to the Paths line. Find the line
that starts with `**Paths:** \`src/runner/main.py\`` and append
`, \`src/runner/proposals.py\`` at the end of the path list (order doesn't
matter but by convention proposals goes last).

**Edit 2b**: Add these 4 bullets to the "Public interface" section (or wherever
other `runner.*` helpers are listed — review the existing file structure):

```markdown
- `proposals.extract_proposal_id(text)` — parse `Proposal-ID: <uuid>` marker (pure).
- `proposals.find_recent_duplicate(target_file, change_type, lookback_days=30)` — dedup check for review-and-improve.
- `proposals.insert_proposal(...)` / `proposals.mark_proposal_merged(proposal_id, pr_url)` — lifecycle mutations.
- `proposals.list_pending_proposals(...)` / `proposals.list_recent_proposals(...)` / `proposals.get_proposal_by_id_prefix(...)` — query helpers for the /proposals command.
```

### 3. `docs/EVALUATION_2026-04-18.md` — status table

In the Status Table (top of doc), find the row:

```
| 10 | P1 | Proposal-applied tracking | planned | — | — |
```

Change it to:

```
| 10 | P1 | Proposal-applied tracking | **SHIPPED** | _pending_ | 2026-04-18 |
```

(The `_pending_` placeholder will be replaced with the actual SHA in a
follow-up commit after the main commit lands.)

---

## Run lint + tests

```bash
python3 scripts/lint_docs.py
# expected: 5/5 PASS

# If deps aren't installed (sandbox):
pip install --break-system-packages --ignore-installed \
  pytest pyyaml pydantic pydantic-settings structlog claude-agent-sdk

SERVER_ROOT=$(pwd) POSTGRES_DSN="postgresql+asyncpg://x:y@localhost/x" PYTHONPATH=. \
  python3 -m pytest tests/ -v
# expected: 155 existing + 27 new = 182 passing
```

Note: the 27 new tests are pure-function — they don't touch the DB. The
async DB ops in `src/runner/proposals.py` are only exercised via integration
testing (no sandbox Postgres available).

---

## Commit + push

### Primary commit

```bash
git add -A
git commit -m "feat(rec-10): proposal tracking table + dedup + /proposals command

Per docs/EVALUATION_2026-04-18.md § 7 Recommendation 10.
Closes the loop on retrospective proposals — they now track their fate
(pending/merged/rejected/superseded), preventing proposal zombies.

- New: alembic/versions/002_proposals_table.py (proposals table + partial index)
- New: Proposal model + ProposalChangeType/ProposalOutcome enums in src/models.py
- New: src/runner/proposals.py (pure helpers + async DB ops)
- Modified: skills/review-and-improve/SKILL.md (Proposal tracking section + dedup)
- Modified: skills/server-patch/SKILL.md (Step 9: mark_proposal_merged on merge)
- Modified: src/gateway/telegram_bot.py (/proposals command + help text)
- New: tests/test_proposals.py (~27 pure-function tests)
- Updated: SYSTEM.md, db+gateway+runner CONTEXT+CHANGELOG"

git push origin main
git rev-parse --short HEAD   # capture the SHA
```

### SHA follow-up commit

```bash
# Edit docs/EVALUATION_2026-04-18.md to replace _pending_ with the short SHA
# E.g. if SHA is abc1234:
#   | 10 | P1 | Proposal-applied tracking | **SHIPPED** | abc1234 | 2026-04-18 |

git add docs/EVALUATION_2026-04-18.md
git commit -m "docs: record rec-10 commit SHA in evaluation status table"
git push origin main
```

---

## After Rec 10 ships: move to Rec 2

Read `REC-2-SPEC.md` in this folder.
