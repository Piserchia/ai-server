# alpha-research gotchas

- (2026-09-14, design) The schedule-free chain: this skill is dispatched
  by alpha-intake (FILE mode, payload idea_text), by itself (ADVANCE
  mode, payload idea_id), and by alpha-governor (both modes). If a
  payload arrives with NEITHER key, report the malformed dispatch and
  stop — do not guess an idea.
- (2026-09-14, design) Workspace clones drop gitignored files but the
  atlas manifest's `delivery.env_files: [".env"]` re-provisions the
  owner keys — Alpaca/FRED/Finnhub creds are available for data
  fetches; brokerage ORDER use of them is forbidden (verdicts only).
- (2026-09-14, final review) Two near-simultaneous FILE-mode jobs can race
  the A-#### max+1 assignment into a push conflict; that is recoverable by
  design (report the divergence, no dispatch — the governor re-drains).
  Same family: with 3 active chains + the governor all appending to one
  LEDGER.md, occasional rebase conflicts on push are expected — report,
  never force; the daily governor resumes the stalled chain.
