# alpha-scout — gotchas

- 2026-09-23 (birth): the fence is two files — FAMILIES.md `status: open`
  sections and LESSONS.md prunes. Everything else in the repo is context
  for MINING, not license to generate. When both give you nothing, zero
  files is the correct output.
- 2026-09-23: mined E-0006-class offers must quote the offering ledger
  entry verbatim in the idea_text (the A-0003 filing precedent) so triage
  can verify the provenance without a hunt.
- 2026-10-04 capacity-check Glob false-zero: the skill runs inside an
  ai-server workspace clone whose cwd is NOT the atlas repo. A bare
  `Glob("alpha-lab/ideas/*/state.json")` resolves relative to the
  workspace dir, finds nothing, and returns a false-zero active count —
  making the scout think the pipeline is empty when it is not. Always
  supply the explicit path parameter:
  `Glob(pattern="alpha-lab/ideas/*/state.json",
        path="/Users/alfredbot.ai.butler/Documents/repos/atlas")`.
  False-zero causes the scout to file new ideas past the capacity ceiling.
- 2026-10-04 capacity-check Glob, the REAL mechanism (supersedes the
  remedy in the 'capacity-check Glob false-zero' entry above): the
  `path=` parameter is IGNORED in this harness, and so is a single-`*`
  directory wildcard. Measured this run:
  Glob(pattern="alpha-lab/ideas/*/state.json", path="<atlas>") -> 0
  hits; Glob(pattern="<atlas-abs>/alpha-lab/ideas/*/state.json") -> 0
  hits TOO (single `*` across a directory level silently matches
  nothing); Glob(pattern="<atlas-abs>/alpha-lab/ideas/**/*.json") ->
  all 13 ideas. So `path=` does NOT fix the false zero. Use an
  ABSOLUTE pattern with `**`:
  `Glob(pattern="/Users/alfredbot.ai.butler/Documents/repos/atlas/alpha-lab/ideas/**/*.json")`
  then Read each A-####/state.json. Cross-check: Read on an absolute
  atlas path works fine even when Glob reports nothing, so if Glob
  says the pipeline is empty, verify with a Read of a known file
  before believing it. A false zero makes the scout file past
  max_active_ideas.
- 2026-10-04 Bash is sandboxed to the ai-server dir, not atlas:
  `wc`/`head` on an atlas path are BLOCKED ('may only … from the
  allowed working directories'). This is why the skill's 'no shell'
  framing holds in practice — do the whole capacity/mining sweep with
  Glob+Read+Grep, which all reach atlas normally. Grep with an atlas
  `path=` DOES work (unlike Glob's `path=`), including `glob=`
  filters.
- 2026-10-04 the sealed-but-unrun blind spot (E-0098/E-0099): four
  consecutive scout runs re-filed the same F-08 NAV-discount candidate
  that had been idea A-0013 since the second of them, burning three of
  12 daily job slots. A `carded` idea has run nothing, so it is in NO
  trials registry (legitimately — a card evaluates nothing) and its
  INBOX line is already checked: both registries a dedup sweep
  naturally reads report it as 'never tried'. Mandatory extra dedup
  step before filing ANYTHING: list non-terminal ideas/*/state.json
  (stage != verdict), then Grep each one's card.md and
  research/triage.md for the candidate's family string and two
  mechanism keywords. A hit => do not file.
- 2026-10-04 refinement slots are currently ALL spent-or-declined:
  A-0006/A-0007/A-0008/A-0009/A-0010 each DECLINED refinement
  explicitly with numbers in their DECISION, and the F-05 (daily +
  quarterly VRP) and F-01 (both daily-bar month-turn) expression
  questions are CLOSED by lesson. Don't hunt for §2c candidates in
  these — read the DECISION's own 'refinement DECLINED' paragraph
  first and save the sweep.
- 2026-10-04 mining beats inventing, and the richest vein is a
  DECISION's 'What this verdict explicitly does NOT cover' section —
  E-0096 item 3 handed over small-cap PEAD ('where the documented
  drift actually lives') as explicitly uncovered ground inside an open
  family. Quote that item verbatim in idea_text (the A-0003/E-0006
  precedent) so triage can verify provenance without a hunt.
  Corollary: consensus-SUE PEAD is NOT free-data feasible — swing
  DR-0005's FINNHUB_TOKEN has been unprovisioned since 2026-08-30, so
  any consensus-surprise formulation is BLOCKED-ON-DATA and must not
  be filed; the consensus-FREE (EDGAR 8-K Item 2.02 abnormal-return)
  formulation is the only F-03 route that clears the free-data gate.
- 2026-10-04 F-08 NAV-source scope: family F-08
  (etf-primary-market-frictions) requires that every candidate names the
  *exact free NAV source* in the idea_text, or triage blocks the card as
  BLOCKED-ON-DATA regardless of mechanism quality. Do not file an F-08
  candidate that mentions NAV without specifying the free source (e.g.,
  the issuer's public daily NAV CSV page, ETF.com download, or an Alpaca
  ETF spread proxy stated explicitly). The quality gate — mechanism +
  loser + free-data source — is satisfied only when the NAV provider is
  named, not implied.
