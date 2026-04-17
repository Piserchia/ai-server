# Projects registry

> Master index of hosted projects. Updated by `register-project.sh` (Phase 3+)
> and by skills that create projects (`research-report` scaffolds `research/` on
> first run).

## Currently scaffolded

| Slug | Type | Hosted? | Created by | Phase |
|---|---|---|---|---|
| `research` | content | no (content storage only) | `research-report` skill on first run | 2 |

`research` is a content-storage project: it holds dated markdown research
reports as its own git repo, gitignored from the server repo. It has no
`manifest.yml` and is not served publicly. The research-report skill appends
every run to `projects/research/.context/CHANGELOG.md`.

## Planned (Phase 3 migrations from the old repo)

| Slug | Type | Subdomain | Source | Phase |
|---|---|---|---|---|
| `bingo` | static | `bingo.<domain>` | old repo's `baseball_bingo.html` | 3 |
| `market-tracker` | service | `market-tracker.<domain>` | `github.com/Piserchia/market-tracker` | 3 |

## Port allocation

See `projects/_ports.yml`. Increment only; ports are never reused.
