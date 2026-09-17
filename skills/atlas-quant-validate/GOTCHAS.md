# atlas-quant-validate — gotchas

- 2026-09-17 (birth): IEX free daily bars effectively start late 2018 for
  SPY despite the configured 2016 start — the window in each report shows
  the ACTUAL joined dates; never claim the configured start as coverage.
- 2026-09-17: the sweep is a batch by design — all trials.jsonl lines land
  before any report so every report's lifetime N includes the whole sweep.
  Do not "optimize" it into per-entry append-and-report.
- 2026-09-17: quant/.venv in ~/Documents clones needs the sitecustomize
  rescue (hidden-.pth gotcha); workspace clones under Application Support
  are unaffected but the venv is created fresh there anyway.
- 2026-09-17 (run 2, first scheduled live run): the DSR bar RATCHETS every
  week. The sweep appends 4 trials/run and lifetime N is all lines ever, so
  identical Sharpes deflate further each run (N=4 -> N=8 moved buy_hold
  0.9903 -> 0.9876, sma_gate 0.9283 -> 0.9157, donchian 0.9669 -> 0.9599).
  Left alone, every roster entry falls under threshold from the calendar
  alone. Filed as LEDGER D-0001 (owner decision); do NOT "fix" it by
  editing thresholds, the protocol, or by skipping trial lines.
- 2026-09-17: venv self-heal in a fresh workspace clone is ~40s and needs
  no sitecustomize rescue; preflight resolved Alpaca creds from the clone's
  own .env copy (workspace clones carry the gitignored .env).
- 2026-09-17 (adversarial audit): the /quant page renders the RUNTIME
  clone's reports directory — a push alone never updates it. Procedure
  step 6 (gated redeploy dispatch) is load-bearing; skipping it leaves the
  page a week behind the desk.
