# ARCHIVED — Handoff to Opus 4.6 CLI session

> **Status**: All evaluation recommendations shipped (2026-04-19/20) except
> Rec 14 (chunk-level doc retrieval, deferred). This folder is historical
> reference only. See `docs/EVALUATION_2026-04-18.md` for final status.

---

# Original handoff document

**Date**: 2026-04-18
**Origin**: Claude chat sessions (claude.ai web) hit tool-call budget limits across
~8 sessions. Each session recreated the same Rec-10 sandbox state from transcript
but ran out of budget before `git push`. Switching to CLI session where tool
limits aren't a blocker.

**Your job**: finish shipping Rec 10 (currently ~95% staged in a patch file here),
then work through the remaining evaluation recommendations in priority order.

---

## Strict workflow (user's standing instruction — do not skip steps)

For each recommendation:

1. **Implement** the change
2. **Test + lint**: `python3 scripts/lint_docs.py` must pass 5/5; `SERVER_ROOT=$(pwd) POSTGRES_DSN="postgresql+asyncpg://x:y@localhost/x" PYTHONPATH=. python3 -m pytest tests/ -v` must pass (155 existing + any new)
3. **Commit**: `git commit -m "feat(rec-N): <one-line summary>"` with a body referencing `docs/EVALUATION_2026-04-18.md § 7 Recommendation N`
4. **Push**: `git push origin main`
5. **Update status table** in `docs/EVALUATION_2026-04-18.md` with the short SHA (format: `**SHIPPED** | <sha> | 2026-04-18`)
6. **Commit the status table**: `git commit -m "docs: record rec-N commit SHA in evaluation status table"`
7. **Push**: `git push origin main`

**Never skip step 5** — the status table is how we track what's shipped.

---

## Priority order for remaining recs

Per `docs/EVALUATION_2026-04-18.md` § 8:

1. **Rec 10 — Proposal tracking** → ~95% done, just needs final 4 items + commit/push. See `REC-10-FINISH.md`.
2. **Rec 2 — Context consumption signal** → See `REC-2-SPEC.md`
3. **Recs 4, 6, 7, 8, 9, 12, 13, 14, 15** — See `REC-REMAINING-SPECS.md`

**Rec 11 is already resolved** (non-issue: sandbox-specific missing claude_agent_sdk, production has it).

---

## Repo state snapshot at handoff

- **HEAD**: `bf7337b docs: record rec-1 commit SHA + mark rec-11 resolved (non-issue)`
- **Shipped**: Rec 1 (`542334c`), Rec 3 (`adc1cbf`), Rec 5 (`599e577`), Rec 11 RESOLVED
- **Status table**: 4 of 15 recs tracked; 11 remaining

---

## Files in this handoff folder

| File | Purpose |
|------|---------|
| `README.md` | This file |
| `REC-10-FINISH.md` | Finish Rec 10 — exact remaining items + commit/push recipe |
| `rec-10-current-diff.patch` | Git diff of 8 modified files from the Rec 10 work in progress (apply with `git apply` if needed, but the files are NOT in the repo state; they're in a sandbox) |
| `REC-10-FILES/` | Full contents of new files (alembic 002, proposals.py, test_proposals.py) and full contents of edits for fast recreation |
| `REC-2-SPEC.md` | Rec 2 implementation spec |
| `REC-REMAINING-SPECS.md` | Recs 4, 6, 7, 8, 9, 12, 13, 14, 15 — specs pulled from evaluation doc |
| `CONTEXT.md` | Project-level context the CLI session should know (architecture, conventions, gotchas) |

---

## PAT rotation

The PAT `ghp_REDACTED` has been in plaintext
across 8+ session transcripts. **Rotate it** — ideally before any further
work.

---

## Quick start for CLI session

```bash
cd /path/to/ai-server
git pull origin main
cat .handoff/README.md
cat .handoff/REC-10-FINISH.md
# Start with Rec 10 — recreate the 11 sandbox files per REC-10-FILES/,
# then do the final 4 items and commit/push per REC-10-FINISH.md.
```
