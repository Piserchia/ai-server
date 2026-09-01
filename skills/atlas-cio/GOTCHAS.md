# atlas-cio — gotchas

- 2026-09-01 (build): F-numbers are claimed only by commits on
  origin/master — `git pull --rebase` BEFORE picking the next number and
  again before pushing.
- 2026-09-01 (build): value's shadow book is SPY-only (no BIL leg) and the
  owner book may lack both legs until SPY/BIL live in candles — cite
  `benchmark_pair:*` warns as known gaps, not as desk failures.
- 2026-09-01 (build): swing/value with zero open positions is a legitimate
  state ("no-trade is success") — an empty book is not an idle desk.
