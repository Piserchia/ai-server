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
- (2026-09-14, A-0001 triage, ledger E-0002) Daily-frequency survivorship-aware
  backtests ARE feasible on the free tier (SEC company_tickers.json universe +
  EDGAR formerNames[] point-in-time naming + near-universal free daily-bar
  retention per momentum E-0026) — do not reflexively verdict BLOCKED-ON-DATA
  on survivorship grounds; measure first. Corollary from A-0002: historical
  SIP consolidated top-of-book quotes are also free (nanosecond timestamps);
  the honest free ceiling for microstructure is ~60-80ms top-of-book, not
  "no tick data".
- (2026-09-14, A-0002) An in-session code-review CHANGES REQUESTED on probe
  code triggers a fix→rerun→re-review loop that can blow the 45-min budget
  (A-0002 ran ~80 min). Budget for it: run probes early, keep them small, and
  if the clock is gone after fixes, seal what is reviewed and let the chain
  resume rather than rehashing.
- 2026-09-23 (A-0003, job c6cfbf6b): the budget failure mode is TURNS, not
  just minutes — a FILE+triage session exhausted max_turns (80) at close-out
  with everything still in the workspace; the clone was discarded and the
  entire session's work vanished (INV-16: only pushes survive). Reserve the
  last ~15 turns for the close-out chain (ledger, state, INBOX, CHANGELOG,
  ONE commit, rebase, push, dispatch) and prefer pushing a leaner triage
  over one more probe refinement. The retry (5c1cbf39) with exactly that
  discipline finished in ~35 turns.
