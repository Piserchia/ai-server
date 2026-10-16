# atlas-advisors-ingest — gotchas

Seeded 2026-08-30 at commissioning. Append mechanical lessons here; never
rewrite old entries.

- 2026-08-30: An all-placeholder roster is a SUCCESS state (`empty_roster`
  run row + stop), not a failure — the owner hasn't filled roster.yaml yet.
- 2026-08-30: yt-dlp auto-subs repeat cue lines; always go through
  `advisors.ingest.vtt_to_text` (it dedupes) rather than reading .vtt raw.
- 2026-08-30: "Vibes are not claims" — a video with no explicit call
  produces zero claims.jsonl lines and that's the correct output; padding
  extraction to look productive poisons the tier-1 book's honesty.
- 2026-10-16: Partial-work loss on quota-mid-run (`88f99e74`). Long ingest
  (5+ personas × dispatched extraction subagents) crossed the five_hour
  reset mid-run; `rate_limit_status: rejected` fired, job requeued, retry
  hit the standing SDK Session-ID-already-in-use bug (TROUBLESHOOTING §
  "Session ID collision", instance #9). Three personas' claims had been
  written to the ephemeral workspace clone but NEVER pushed; the workspace
  was cleaned so those writes are gone. Twice-weekly cadence healed — the
  2026-10-15 cycle re-processes everyone — but ANY long ingest should
  (a) commit+push after each persona so a requeue can resume from the last
  committed state, or (b) be idempotent on partial state so a retry simply
  recomputes what's missing. Today the skill does neither; mid-run quota
  rejection = total loss of in-flight work. Underlying bug depends on
  server-patch Phase 5 (session-id rotation).
