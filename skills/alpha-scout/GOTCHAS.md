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
- 2026-10-04 F-08 NAV-source scope: family F-08
  (etf-primary-market-frictions) requires that every candidate names the
  *exact free NAV source* in the idea_text, or triage blocks the card as
  BLOCKED-ON-DATA regardless of mechanism quality. Do not file an F-08
  candidate that mentions NAV without specifying the free source (e.g.,
  the issuer's public daily NAV CSV page, ETF.com download, or an Alpaca
  ETF spread proxy stated explicitly). The quality gate — mechanism +
  loser + free-data source — is satisfied only when the NAV provider is
  named, not implied.
