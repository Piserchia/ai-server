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
