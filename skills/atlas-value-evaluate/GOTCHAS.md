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
