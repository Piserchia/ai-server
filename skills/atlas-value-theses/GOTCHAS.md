# atlas-value-theses GOTCHAS

- EDGAR fetches cache under value/.cache in the CLONE — a cold cache means
  the first run spends minutes fetching ~77 companyfacts at ≤10 req/s.
  That is normal; don't parallelize around the throttle.
- next_earnings is unknown until FINNHUB_TOKEN lands (owner P0) — every put
  card must SAY "earnings date unverified" until then (the earnings veto
  can't check what it can't see; the card must carry the caveat).
- Portfolio-blind mode (no stated value, no holdings): caps aren't
  checkable; cards show % sizes and say so. Don't guess a portfolio value.
- Booked passes are deliberate: the pass with its failing gate named is
  part of the advisor's audit surface.
- Payload must carry '{"project_slug":"atlas"}' + 3600s timeout.
