## 2026-10-09 — Preload `.context/SYSTEM.md` via context_files

**Files created**: none
**Files changed**: `skills/alpha-scout/SKILL.md` (frontmatter `context_files`)
**Why**: review-and-improve Rec 2 context-files audit (proposal
138421f5-e363-42b0-bb9a-ae0fbe2dbb76, src/runner/retrospective.py:
context_consumption) found alpha-scout Read `.context/SYSTEM.md` on 31 of
32 runs (97%) over the last 30 days without the file being in the skill's
`context_files` frontmatter. Adding it makes the Read deterministic
(every run, driven by the directive's "Read these files first" list the
runner builds at `src/runner/session.py:174-177`) instead of ad-hoc. The
Read tool call is NOT eliminated — `context_files` is a reading LIST, not
a content preload — so the proposal's "~32 Reads/month saved" framing is
wrong (flagged in-session by the code-review subagent for the
review-and-improve retrospective analyzer to correct upstream).
Frontmatter-only change; no markdown-body edits, so the system prompt
body and skill behavior are unchanged.
**Side effects**: None — body unchanged; directive gains one bullet
pointing at a file the agent was already reading 97% of the time.
**Gotchas discovered**: review-and-improve Rec 2 analyzer treats
`context_files` as a content preload. It is not — it is a reading list
appended to the directive. Proposals framed as "eliminate N Reads/month"
via `context_files` should be re-framed as "make the Read deterministic";
if content-preload is genuinely desired, that is a different change
(runner would have to read + inject file contents into the system
prompt).

## 2026-10-05 — GOTCHAS: 3 runtime learnings from evening scout run (job c515b971)

**Agent task**: docs append — record three GOTCHAS entries the read-only
  evening scout session (job c515b971) could not write itself (INV-20)
**Files changed**:
- `skills/alpha-scout/GOTCHAS.md` — three entries inserted before the
  F-08 scope entry: (1) Grep's `glob=` filter has the SAME single-`*`
  directory-wildcard blind spot as Glob's pattern — `glob="*/state.json"`
  returns zero matches even when 14 files match; use absolute `**` Glob
  + per-file Reads; (2) F-04/F-06/F-07 are virgin families never filed
  into — generative ground when mining existing families runs dry (with
  F-06's discharge criteria referenced); (3) F-08 NAV source working
  endpoints proved by A-0013 cycle-1 (keyless SSGA 6c-11 navhist/pdhist
  xlsx URLs confirmed).

**Why**: The Grep `glob=` false-zero is a third variant of the false-zero
capacity-check failure class the file already documents twice; all three
must be on record so future runs choose the absolute-`**`-Glob + Reads
pattern consistently. The virgin-families entry prevents needless lesson
sweeps when F-01/F-05/F-08 run dry. The F-08 NAV endpoint entry avoids
future runs inventing an unverified source when a proved one is on record.
**Side effects**: None — documentation-only change.

## 2026-10-04 — GOTCHAS: corrected Glob remedy + 4 new runtime learnings

**Agent task**: correct the 'capacity-check Glob false-zero' gotcha (the
  `path=` remedy recorded earlier this day DOES NOT WORK) and add four new
  scout gotchas from the evening run (job 3cfb6098)
**Files changed**:
- `skills/alpha-scout/GOTCHAS.md` — inserted 5 bullets before the F-08
  entry: (1) corrected Glob mechanism — `path=` is ignored, single-`*`
  across a directory level silently matches nothing, `**` in an absolute
  pattern is required; (2) Bash sandbox covers atlas path, use
  Glob+Read+Grep instead; (3) sealed-but-unrun blind spot — `carded`
  ideas absent from trial registries must be caught by a second Grep pass
  before filing; (4) all current refinement slots are spent-or-declined;
  (5) mining the DECISION's uncovered-ground section beats inventing, with
  F-03 PEAD routing note (consensus-free EDGAR path only).

**Why**: The earlier `path=` remedy was measured in production and failed;
leaving it unqualified would cause future runs to continue hitting the
false-zero capacity bug and over-filing ideas.
**Side effects**: None — documentation-only change.

## 2026-10-04 — GOTCHAS: capacity-check Glob false-zero + F-08 NAV-source scope

**Agent task**: docs append — record two runtime-discovered gotchas
**Files changed**:
- `skills/alpha-scout/GOTCHAS.md` — two entries appended: (1) Glob
  false-zero when capacity check runs from ai-server workspace cwd instead
  of the atlas repo path; (2) F-08 candidates require an explicit free NAV
  source name or triage blocks them as BLOCKED-ON-DATA.

**Why**: Glob with a relative path returns false-zero in the ai-server
workspace context; F-08 candidates consistently fail triage without a
named free NAV source. Documenting both to prevent recurrence.
**Side effects**: None — documentation-only change.
