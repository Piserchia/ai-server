# Research project

## Purpose

Storage for research reports produced by the `research-report` skill. Each
report is a dated markdown file; each is committed to this directory's git
repo.

## Structure

```
projects/research/
├── .git/                         # this directory's own git repo
├── .context/
│   ├── CONTEXT.md                # this file
│   └── CHANGELOG.md              # chronological index of all reports
├── README.md
└── <topic-slug>-YYYY-MM-DD.md    # reports (many)
```

## Not hosted

No `manifest.yml`. Not exposed via Caddy. Pure content storage.

## Naming convention

- **Filename**: `<topic-slug>-YYYY-MM-DD.md`
- **Topic slug**: lowercase, hyphens, no special chars, max 60 chars
- **Date**: ISO format, UTC. Multiple reports on the same topic on the
  same day get a `-N` suffix: `btc-market-2026-04-17-2.md`

## Content conventions

See `../../skills/research-report/SKILL.md` for the full output template.
Key rules:
- TL;DR ≤ 3 sentences
- No verbatim quotes > 15 words from any source
- No more than one quote per source
- Primary sources preferred over aggregators
