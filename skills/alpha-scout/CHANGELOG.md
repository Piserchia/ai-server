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
