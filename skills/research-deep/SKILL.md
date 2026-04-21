---
name: research-deep
description: Deep-dive research with more sources, synthesis, and treatment of conflicting evidence
model: claude-opus-4-7
effort: high
permission_mode: bypassPermissions
required_tools: [Read, Write, Edit, Bash, Glob, Grep, WebSearch, WebFetch, AskUserQuestion]
max_turns: 80
escalation:
  on_failure:
    model: claude-opus-4-7
    effort: xhigh
context_files: ["skills/research-report/SKILL.md"]
tags: [research, writing, high-quality]
---

# Research Deep

You are producing a comprehensive, deeply researched markdown report. The output
is a file at `projects/research-deep/<topic-slug>-YYYY-MM-DD.md`, committed to
the local `projects/research-deep/` git repo. The user receives a short TL;DR as
the summary.

This skill is the heavyweight sibling of `research-report`. The key differences:
more sources, longer output, mandatory treatment of conflicting evidence, and a
transparent account of search strategy.

## Inputs you will receive

Extract from the job description (and optionally `payload`):
- **topic** (required): what to research
- **output_filename** (default=auto from topic slug + date)
- **notify_chat_id** (optional): if present in payload, DM the TL;DR there

If the topic is genuinely ambiguous (e.g., "deep research the election" with no
country or year), use `AskUserQuestion` once to disambiguate. Do not ask more
than one clarifying question; for anything else, make your best guess and
document it in an `## Assumptions` section of the report.

## Procedure

1. **Recency check.** If the topic concerns events less than 72 hours old, warn
   the user via `AskUserQuestion`: "This topic is very recent (<72h). Deep
   research works best with settled sources. Proceed anyway?" If they say no,
   suggest `research-report` instead and exit cleanly.

2. **Decide search scope.** For current events, bias last 7-30 days. For
   evergreen topics, no time bias. Deep research always starts broader than
   you think necessary.

3. **Search broadly.** Run 6-12 `WebSearch` queries. Vary phrasing, try
   different angles: chronological, by stakeholder, by counter-argument,
   by discipline. Start broad, then narrow into specific sub-claims. Each
   query should be 1-6 words. If a search returns nothing useful, try a
   different phrasing -- not a longer query.

4. **Fetch primary sources.** For each search result that looks primary
   (official government sites, company investor relations, SEC filings,
   peer-reviewed journals, primary news reporting -- *not* aggregators or
   content farms), call `WebFetch`. Target **10-20 sources minimum**. Keep
   searching until you have multiple independent primary sources for each
   major claim. If a source is paywalled, note it explicitly in the Sources
   section with `(paywalled -- summary from public preview)`.

5. **Synthesize.** Write the report in your own words. Do not quote more than
   15 words verbatim from any single source. Do not use more than one quote
   per source. If you find yourself wanting a longer quote, paraphrase
   instead. Target length: **2000-5000 words** (excluding Sources section).

6. **Write the file.** Determine a topic slug (lowercase, hyphens, no special
   chars, max 60 chars). The file path is
   `projects/research-deep/<slug>-<YYYY-MM-DD>.md`. Use the template below.

7. **Ensure `projects/research-deep/` exists and is a git repo.** On first run
   of this skill, the project directory may not exist yet. Bootstrap it:
   ```bash
   if [ ! -d projects/research-deep/.git ]; then
     mkdir -p projects/research-deep/.context
     cat > projects/research-deep/CLAUDE.md << 'SCAFF'
   # Research Deep

   Storage project for deep research reports produced by the `research-deep` skill.

   ## Key rules
   - Reports are private, not publicly served
   - Each report is a dated markdown file: `<topic-slug>-YYYY-MM-DD.md`
   - Each report is committed to git (this directory is its own git repo)
   - Read `.context/CONTEXT.md` for naming conventions
   SCAFF
     cat > projects/research-deep/.context/CONTEXT.md << 'SCAFF'
   # Research Deep project

   ## Purpose
   Storage for deep research reports produced by the `research-deep` skill.
   Heavyweight counterpart to `projects/research/`.

   ## Structure
   ```
   projects/research-deep/
   +-- .git/
   +-- .context/
   |   +-- CONTEXT.md
   |   +-- CHANGELOG.md
   +-- CLAUDE.md
   +-- <topic-slug>-YYYY-MM-DD.md  (reports)
   ```

   ## Not hosted
   No manifest.yml. Not exposed via Caddy. Pure content storage.

   ## Naming convention
   - Filename: `<topic-slug>-YYYY-MM-DD.md`
   - Topic slug: lowercase, hyphens, no special chars, max 60 chars
   - Date: ISO format, UTC
   SCAFF
     cat > projects/research-deep/.context/CHANGELOG.md << 'SCAFF'
   # Research Deep catalog

   <!--
   Every research-deep run appends an entry at the top.
   Newest entries above. Format:

   ## YYYY-MM-DD -- <topic title>
   File: <slug>-YYYY-MM-DD.md
   Sources: N
   TL;DR: <one line>

   -->
   SCAFF
     ( cd projects/research-deep && git init -q && git add -A && \
       git commit -q -m "Initial scaffold from research-deep skill" )
   fi
   ```

8. **Commit the new report** to the `projects/research-deep/` git repo:
   ```bash
   cd projects/research-deep
   git add .
   git commit -m "Research deep: <topic title>"
   ```

9. **Update the project CHANGELOG.** Append to
   `projects/research-deep/.context/CHANGELOG.md`:
   ```
   ## YYYY-MM-DD -- <topic title>
   File: <slug>-<date>.md
   Sources: <N>
   TL;DR: <copy the TL;DR here>
   ```

10. **Final text message.** Your final text block must be the TL;DR itself
    (no meta-commentary like "I've written the report"). This becomes the
    job's summary and the Telegram DM the user receives.

## Output template

```markdown
# <Topic>

**Date**: YYYY-MM-DD
**Sources consulted**: N

## TL;DR

<3-5 sentences. Concrete, not hedge-heavy. Denser than research-report.>

## Findings

<Prose organized by sub-topic with H3 headings. Cite inline by source number,
e.g. "The Fed held rates steady [3]." Target 2000-5000 words.>

### <Sub-topic 1>

...

### <Sub-topic 2>

...

## Where sources disagree

<Even if no meaningful disagreement exists, state that explicitly: "Sources
were broadly consistent on X, Y, and Z." When disagreement exists, present
each side's strongest evidence and note which side has more/better primary
support. Do not average conflicting claims.>

## How I researched this

<Search strategy: what queries you ran, what angles you explored, what got
cut from the final report and why, what you'd still want to investigate with
more time or access. This section is about transparency, not length -- 3-8
sentences.>

## Open questions

<What couldn't be verified; what would require a follow-up report; what
important questions remain unresolved.>

## Assumptions

<Only include this section if you made disambiguating assumptions. Omit otherwise.>

## Sources

1. [Title](URL) -- accessed YYYY-MM-DD
2. [Title](URL) -- accessed YYYY-MM-DD
3. ...
```

## Quality gate (run this before your final text message)

Self-check by reading back your written file:

- [ ] File exists at the correct path with the correct naming pattern
- [ ] TL;DR is 3-5 sentences
- [ ] Report body is 2000-5000 words (excluding Sources section)
- [ ] At least 10 distinct primary sources in the Sources section
- [ ] Multiple independent sources for each major claim
- [ ] `## Where sources disagree` section present and substantive
- [ ] `## How I researched this` section present
- [ ] No verbatim quotes over 15 words from any source
- [ ] No more than one quote per source
- [ ] All source URLs present and syntactically valid
- [ ] Paywalled sources marked explicitly
- [ ] `projects/research-deep/.context/CHANGELOG.md` updated
- [ ] Git commit in `projects/research-deep/` exists with a descriptive message

If any check fails, iterate. If after 3 iterations a check still fails, add a
`## Limitations` section to the report noting what couldn't be achieved, then
finish.

## Gotchas (living section -- append when you learn something)

- **Disambiguating people**: when multiple public figures share a name, use
  role + location to disambiguate aggressively before fetching.
- **Financial topics**: the last 24h is usually more relevant than the last 30d.
- **Claimed "primary" sources on aggregator sites**: Yahoo Finance reposting
  Reuters is still Reuters -- cite Reuters directly and skip Yahoo.
- **Paywalls**: if WebFetch returns a paywall page, note the source in your
  bibliography with `(paywalled -- summary from public preview)` rather than
  pretending you read the full article.
- **Conflicting sources**: don't average -- surface the disagreement in
  "Where sources disagree" with each side's best argument.
- **Too-recent topics (<72h)**: warn the user. Deep research depends on
  multiple independent sources; breaking news rarely has those yet.
- **Topic scope creep**: deep research can balloon. If the topic has more than
  3-4 natural sub-topics, narrow to the most important ones and note the rest
  in "Open questions" as follow-up candidates.

## Files this skill updates as part of write-back

- `projects/research-deep/<slug>-<date>.md` (the report itself)
- `projects/research-deep/.context/CHANGELOG.md` (append entry)
- This file's `## Gotchas` section (only if you learned something reusable)
