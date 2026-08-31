# atlas-report — Gotchas

## Subagent text-format mismatch ≠ file write failure (2026-08-23)

**Applied manually as remediation for job `b96a4976` (`_learning_apply` for
parent `fd233e64`, atlas-report on META), which failed to auto-record this
learning due to the session-ID-collision bug documented in
`docs/TROUBLESHOOTING.md` (§ "Session ID <uuid> is already in use").**

**Symptom**: A lens subagent (business or technical) returns malformed or
non-standard text — e.g. missing the required 4-line
`LENS/REPORT_ID/EVAL/DETAIL` format — and the aggregator initially treats
that lens as failed. But the lens's JSON dossier
(`/tmp/atlas-bizrep-<token>.json` or `/tmp/atlas-techrep-<token>.json`) was
successfully written and the report id is valid in the atlas DB.

**Example**: parent job `fd233e64` (META). The business lens returned
non-standard text (missing the LENS/REPORT_ID/EVAL/DETAIL block). The
aggregator flagged the lens as failed. Follow-up verification found the
`/tmp/atlas-bizrep-<token>.json` dossier on disk and a `biz_*` block in the
re-fetched packet — the lens had actually succeeded and its report was
already saved. The aggregate was then authored with both lenses, not just
technical, and cited the business dossier correctly.

**Rule**: SKILL.md § Gotchas says "Subagents return exactly 4 lines … Anything
else = treat that lens as failed and aggregate without it." Refine that:
before writing the lens off, do a two-step disk check:

1. `test -f /tmp/atlas-bizrep-<token>.json` (or `atlas-techrep-<token>.json`).
2. Re-fetch the packet (`atlas-dash packet <SYMBOL> > /tmp/atlas-packet-agg-<job>.json`)
   and look for the `biz_*` block (business) or the lens's marker fields
   (technical). If either is present, the lens succeeded — use its dossier
   as an aggregator source and cite it normally.

Only when BOTH the dossier file is absent AND the re-fetched packet lacks
the lens's fields is the lens truly failed. Treat the parseable-text check
as the fast path, not the truth. This matters because the aggregate scoring
penalises a missing lens in Limitations, and losing a successful lens
degrades the report unnecessarily.

**Where this belongs long-term**: the guard should move into SKILL.md
step 3 ("Parse each subagent's 4-line return …") as a mandatory disk-check
fallback. That is a code/skill-frontmatter change and must be born in the
dev repo (`~/Documents/repos/ai-server`) — not committed here (production
is pull-only for tracked files). Until then, this GOTCHAS entry is the
runtime record.

### Related failure mode

The `_learning_apply` job that was supposed to auto-record this learning
(b96a4976) died to the session-ID-collision bug (see TROUBLESHOOTING.md).
That is a separate, already-tracked server bug awaiting `server-patch`
(Phase 5). This learning entry is the human-visible outcome the runner
failed to persist automatically.
