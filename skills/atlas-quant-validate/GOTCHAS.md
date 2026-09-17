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
