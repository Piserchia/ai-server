---
name: research-report
description: Web research + synthesis into a dated markdown report under projects/research/
model: claude-sonnet-4-6
effort: medium
permission_mode: acceptEdits
required_tools: [Read, Write, Edit, Bash, Glob, Grep, WebSearch, WebFetch, AskUserQuestion]
max_turns: 40
escalation:
  on_failure:
    model: claude-opus-4-7
    effort: high
tags: [research, writing, scheduled-capable]
---

# Research Report

You are producing a timestamped markdown research report. The output is a file
at `projects/research/<topic-slug>-YYYY-MM-DD.md`, committed to the local
`projects/research/` git repo. The user receives a short TL;DR as the summary.

## Inputs you will receive

Extract from the job description (and optionally `payload`):
- **topic** (required): what to research
- **depth** (default=standard): quick | standard | deep
- **output_filename** (default=auto from topic slug + date)
- **notify_chat_id** (optional): if present in payload, DM the TL;DR there

If the topic is genuinely ambiguous (e.g., "research the election" with no
country or year), use `AskUserQuestion` once to disambiguate. Do not ask more
than one clarifying question; for anything else, make your best guess and
document it in an `## Assumptions` section of the report.

## Procedure

1. **Decide search scope.** For topics about current events (sports, markets,
   news, legislation), bias recent: last 24h for fast-moving, last 30d for
   slower. For evergreen (history, science fundamentals, biographies), no
   time bias.

2. **Search.** Run 2–5 `WebSearch` queries, each 1–6 words. Vary phrasing so
   you're not querying for the same words repeatedly. Start broad, narrow if
   needed. If a search returns nothing useful, try a different phrasing — not
   a longer query.

3. **Fetch primary sources.** For each search result that looks primary
   (official government sites, company investor relations, SEC filings,
   peer-reviewed journals, primary news reporting — *not* aggregators or
   content farms), call `WebFetch`. Aim for 5–8 fetches for a standard-depth
   report, 3–4 for quick, 10–15 for deep.

4. **Synthesize.** Write the report in your own words. Do not quote more than
   15 words verbatim from any single source. Do not use more than one quote
   per source. If you find yourself wanting a longer quote, paraphrase
   instead.

5. **Write the file.** Determine a topic slug (lowercase, hyphens, no special
   chars, max 60 chars). The file path is `projects/research/<slug>-<YYYY-MM-DD>.md`.
   Use the template below.

6. **Ensure `projects/research/` exists and is a git repo.** On first run of
   this skill, the project directory may not exist yet. Bootstrap it:
   ```bash
   if [ ! -d projects/research/.git ]; then
     mkdir -p projects/research/.context
     cp skills/research-report/templates/README.md projects/research/
     cp skills/research-report/templates/CONTEXT.md projects/research/.context/
     cp skills/research-report/templates/CHANGELOG.md projects/research/.context/
     ( cd projects/research && git init -q && git add -A && \
       git commit -q -m "Initial scaffold from research-report skill" )
   fi
   ```

7. **Commit the new report** to the `projects/research/` git repo:
   ```bash
   cd projects/research
   git add .
   git commit -m "Research: <topic title>"
   ```

8. **Update the project CHANGELOG.** Append to
   `projects/research/.context/CHANGELOG.md` (this is a write-back
   requirement; the runner will spawn a follow-up verification if you skip it):
   ```
   ## YYYY-MM-DD — <topic title>
   File: <slug>-<date>.md
   Depth: <depth>
   Sources: <N>
   TL;DR: <copy the TL;DR here>
   ```

9. **Final text message.** Your final text block must be the TL;DR itself
   (no meta-commentary like "I've written the report"). This becomes the
   job's summary and the Telegram DM the user receives.

## Output template

```markdown
# <Topic>

**Date**: YYYY-MM-DD
**Depth**: quick | standard | deep
**Sources consulted**: N

## TL;DR

<3 sentences maximum. Concrete, not hedge-heavy.>

## Findings

<Prose or bulleted. Cite inline by source number, e.g. "The Fed held rates steady [3].">

## Open questions

<What couldn't be verified; where sources conflict; what would require a follow-up report.>

## Assumptions

<Only include this section if you made disambiguating assumptions. Omit otherwise.>

## Sources

1. [Title](URL) — accessed YYYY-MM-DD
2. [Title](URL) — accessed YYYY-MM-DD
3. ...
```

## Quality gate (run this before your final text message)

Self-check by reading back your written file:

- [ ] File exists at the correct path with the correct naming pattern
- [ ] TL;DR is ≤ 3 sentences
- [ ] At least 3 distinct primary sources in the Sources section (≥5 for deep)
- [ ] No verbatim quotes over 15 words from any source
- [ ] No more than one quote per source
- [ ] All source URLs present and syntactically valid
- [ ] `projects/research/.context/CHANGELOG.md` updated
- [ ] Git commit in `projects/research/` exists with a descriptive message

If any check fails, iterate. If after 3 iterations a check still fails, add a
`## Limitations` section to the report noting what couldn't be achieved, then
finish.

## Gotchas (living section — append when you learn something)

- **Disambiguating people**: when multiple public figures share a name, use
  role + location to disambiguate aggressively before fetching.
- **Financial topics**: the last 24h is usually more relevant than the last 30d.
- **Claimed "primary" sources on aggregator sites**: Yahoo Finance reposting
  Reuters is still Reuters — cite Reuters directly and skip Yahoo.
- **Paywalls**: if WebFetch returns a paywall page, note the source in your
  bibliography with `(paywalled — summary from public preview)` rather than
  pretending you read the full article.
- **Conflicting sources**: don't average — surface the disagreement in
  "Open questions" with each side's best argument.

## Files this skill updates as part of write-back

- `projects/research/<slug>-<date>.md` (the report itself)
- `projects/research/.context/CHANGELOG.md` (append entry)
- This file's `## Gotchas` section (only if you learned something reusable)
