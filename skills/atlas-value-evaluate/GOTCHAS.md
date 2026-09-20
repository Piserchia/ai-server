# atlas-value-evaluate GOTCHAS

- Process compliance dominates: a great return with a gate violation is a
  FAIL week (that ordering is the product).
- Regime annotation is mandatory — a melt-up lag is expected behavior;
  grading it as failure is the documented mistake to avoid.
- STOP_READING thresholds are deterministic; do not soften them with
  judgment. You recommend; the owner decides.
- value.grades insert AND ledger append — both, always.
- **At N=0 the step-1 row checks are VACUOUS — read the gate CODE too.**
  Empty `value.theses` makes every compliance query return 0/0/0, which
  looks like a clean week and is actually no evidence at all. G-0002 found
  an *armed* violation only by reading `value/theses.py`: with the earnings
  feed dark (`weekly.py` hardcodes `next_earnings=None`), the veto branch is
  skipped, yet `theses.py` still writes `evals["earnings_veto"] = "pass
  (expiry precedes next report)"` for every `msp` card. A dark feed emitting
  a specific pass string is false provenance, not a missing caveat. When the
  tables are empty, grep the gate writer for unconditional `evals[...] =
  "pass..."` assignments and report them as latent-but-armed.
- Corollary for the owner recommendation: when a vertical is blocked on
  credential A but a compliance defect is armed by missing credential B,
  say so explicitly — provisioning A alone can be strictly worse than the
  blocked status quo. Order the provisioning; don't just list the gaps.
- Distinguish a silent worker from a dead server before calling liveness.
  Per-day counts across ALL skills in the ai-server `jobs` table settle it
  in one query; G-0002's two "missed" slots were a 3-day server-wide outage
  (0 jobs/day vs 25–68 either side), not a value-worker defect.
- The ledger's `G-####` sequence is SHARED with the research protocol's
  cycle grades (G-0001 was a research-card grade). Read the existing
  `^## \[` headers and take the next free number — don't assume governor
  grades have their own counter.
- `volumes/telemetry/schedule_adherence.json` reports a never-ran schedule
  as `"status": "ok"` with `"observed_job_at": null` — it will NOT flag a
  governor that has never fired. Read the `jobs` table directly for
  liveness; the watchdog is corroboration, not evidence.
- **`jsonb` silently eats duplicate keys — read the row back after inserting.**
  G-0006's `value.grades` payload used `"bar"` twice inside `stop_reading`;
  Postgres kept the last and dropped the other threshold with no error. Always
  `SELECT payload->'…'` the fields you care about after the INSERT, and if you
  repair your own row, declare the repair in the ledger entry rather than
  fixing it quietly.
- **Do not inherit a predecessor grade's claim about the code — re-read the
  call site.** G-0004 recorded the SPY/200-DMA regime leg as "Tradier-gated and
  therefore unobtainable"; it is `self._data().get_daily_bars` (Alpaca,
  credentialed and working). The Tradier call is the line *above* it. A prior
  grade is evidence about the prior grader, never about today's code. The
  regime annotation is mandatory — if a leg looks unobtainable, try to fetch it
  before writing that it cannot be.
- **Audit gate writers for the SILENT skip, not just the false `pass`.** The
  `msp` branch of `theses.py:gate()` declares its own blindness
  (`evals["sizing"] = "portfolio-blind: …"`); the `long` branch is
  `if kind == "long" and pv:` with **no else**, so a missing portfolio writes
  nothing and the card's gates blob reads as "cap checked, not breached". Grep
  every gate branch for a guard with no else — absence-by-silence is the same
  provenance defect class as a false `pass`, and it is harder to see.
- **Read the week's worker job summaries, not only the `value.*` rows.** A
  worker that correctly declines an owner-surface change and "routes the
  decision to the governor" has no write surface on `evaluation/LEDGER.md` —
  if the governor does not file the DR, the finding evaporates. G-0006's
  DR-0006 item 3 existed only because the Monday theses job summary was read.
- **Verify apparent dead code before filing it.** `weekly.py:285` hardcodes
  `"regime_breaker_on": False` with a comment claiming it is applied upstream;
  it is (`weekly.py:211` converts the card to a half-slug `long`), so the
  `theses.py` regime-FAIL branch is unreachable *by design*. That was one read
  away from being a false finding in a grade.
