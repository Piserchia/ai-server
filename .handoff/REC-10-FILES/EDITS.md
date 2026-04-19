# Rec 10 file mapping

## New files — copy straight into repo

```bash
cp .handoff/REC-10-FILES/alembic-002.py       alembic/versions/002_proposals_table.py
cp .handoff/REC-10-FILES/proposals.py          src/runner/proposals.py
cp .handoff/REC-10-FILES/test_proposals.py     tests/test_proposals.py
```

## Modified files — overwrite with post-edit versions

The files under `.handoff/REC-10-FILES/modified/` are **full post-edit copies**
of the 8 files that needed modification. They were captured from the live
sandbox after all edits were applied. Copy them straight over:

```bash
cp .handoff/REC-10-FILES/modified/models.py                    src/models.py
cp .handoff/REC-10-FILES/modified/telegram_bot.py              src/gateway/telegram_bot.py
cp .handoff/REC-10-FILES/modified/review-and-improve-SKILL.md  skills/review-and-improve/SKILL.md
cp .handoff/REC-10-FILES/modified/server-patch-SKILL.md        skills/server-patch/SKILL.md
cp .handoff/REC-10-FILES/modified/SYSTEM.md                    .context/SYSTEM.md
cp .handoff/REC-10-FILES/modified/db-CONTEXT.md                .context/modules/db/CONTEXT.md
cp .handoff/REC-10-FILES/modified/db-CHANGELOG.md              .context/modules/db/CHANGELOG.md
cp .handoff/REC-10-FILES/modified/gateway-CHANGELOG.md         .context/modules/gateway/CHANGELOG.md
```

## Still to do after that

See `.handoff/REC-10-FINISH.md` section "Remaining items":
1. Prepend entry to `.context/modules/runner/CHANGELOG.md`
2. Edit `.context/modules/runner/CONTEXT.md` (Paths + public interface)
3. Flip Rec 10 row in `docs/EVALUATION_2026-04-18.md` status table
4. Lint + tests
5. Commit + push + record SHA

## Sanity check after copying

```bash
git diff --stat     # should show 8 modified + 3 new files + whatever you do next
git diff src/models.py | head -60   # eyeball the Proposal class is there
grep -c "cmd_proposals" src/gateway/telegram_bot.py   # expect 2 (handler + registration)
grep -c "Proposal tracking (Rec 10)" skills/review-and-improve/SKILL.md   # expect 1
grep -c "### 9. Mark proposal applied" skills/server-patch/SKILL.md       # expect 1
grep -c "Schema (4 tables)" .context/modules/db/CONTEXT.md                # expect 1
```
