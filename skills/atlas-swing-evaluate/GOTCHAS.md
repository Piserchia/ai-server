# atlas-swing-evaluate GOTCHAS

- Dual-row DST crons: exactly one of -edt/-est lands in-window per day;
  the sibling's off_window run row is DESIGNED coverage, not a gap.
- Realized expectancy comes from swing.orders realized_pnl only — never
  from research YAMLs or backtest JSONs (poisoned-denominator rule).
- A stopless open stock lot = kernel breach = freeze recommendation now.
- 529-as-completed killed a governor before (08-17 incident): verify your
  own psql pulls returned rows before grading "no activity".
