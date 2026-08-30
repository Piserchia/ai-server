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
