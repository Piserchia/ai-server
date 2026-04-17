# Research

Storage project for research reports produced by the `research-report` skill.

Each report is a dated markdown file: `<topic-slug>-YYYY-MM-DD.md`.
Each report is committed to git (this directory is its own git repo,
separate from the ai-server repo).

## Organization

No subdirectories — all reports live at this level. Listing is
chronological by filename. If the catalog grows past ~100 reports, the
`review-and-improve` skill may propose a restructure.

## Not a hosted service

This is a "project" in the ai-server directory convention, but unlike
service/api/static projects, it has no manifest.yml and is not exposed
via Caddy. It's just where research outputs land.

## Reading the catalog

The one-line index of all reports lives in `.context/CHANGELOG.md`.

## Git remote (optional)

If you want these backed up to GitHub:
```bash
cd projects/research
gh repo create Piserchia/research --private
git push -u origin main
```
