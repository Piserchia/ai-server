# atlas-quant-governor — gotchas

- 2026-09-17 (birth): the DSR recompute needs the quant venv's quantlab
  import working from OUTSIDE quant/ — run it as `cd quant &&
  .venv/bin/python -c ...`, never with bare python3 (hidden-.pth gotcha
  in ~/Documents clones; fresh workspace venvs are fine).
- 2026-09-17: A-#### audit ids share the LEDGER with R-#### validation
  ids but number independently; take max A-#### + 1, never max overall.
