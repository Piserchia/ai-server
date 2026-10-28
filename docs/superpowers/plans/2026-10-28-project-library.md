---
id: plan-2026-10-28-project-library
type: plan
status: built
date: 2026-10-28
supersedes: []
superseded_by: null
summary: >
  Give every design document a machine-readable identity (front-matter: id,
  type, status, supersedes), generate one small index from it, and let agents
  fetch a single section by id instead of reading whole files. A test fails
  the build when an index row or a status goes stale.
---

# Project library — spec + plan (2026-10-28)

> **For agentic workers:** executed inline 2026-10-28; Tasks 1–4 are the
> record of what was built. Status: BUILT.

**Goal:** agents can find and cite the right document (and only the section
they need) without loading the corpus into context, and cannot mistake a
superseded design for a current one.

**Why now:** `docs/` holds 13 specs, 21 plans, 16 reports and 37 research
documents. Supersession is recorded in prose only (the 2026-10-05 cut spec
supersedes the 2026-09-25 multi-model spec in its own §0), so an agent
reading the older file sees no mechanical signal. `.context/INDEX.md` is a
hand-maintained prose map that has grown by dated "Additions" sections and
is itself ~8k tokens.

**Architecture:** three pieces, all outside protected paths.

1. **Front-matter** on every document under `docs/**` and
   `.context/org/**` (YAML block, first thing in the file):
   `id`, `type` (spec | plan | report | research | charter | guide),
   `status` (proposed | accepted | built | shipped | superseded | historical
   | reference | living), `date`, `supersedes: [ids]`, `superseded_by: id |
   null`, `summary` (≤ 3 sentences), optional `anchors` (section ids worth
   jumping to), optional `decisions_open` (count). Markdown renderers treat
   the block as metadata; nothing else in the repo parses these files.
2. **`scripts/lib.py`** (stdlib + pyyaml, no network): `index` regenerates
   `docs/LIBRARY.md` from front-matter (one line per doc, grouped by type,
   superseded docs marked); `show <id> [--section <n|heading>]` prints one
   document or one `##`/`###` section; `grep <term>` prints matching
   paragraphs with `id §heading`; `status <id>`; `check` = the lint: every
   file has well-formed front-matter, ids are unique and match the filename
   stem convention (`<type>-<date>-<slug>`), `supersedes`/`superseded_by`
   resolve and agree both ways, a doc with `superseded_by` has
   `status: superseded`, the committed `LIBRARY.md` equals the generated one.
3. **`tests/test_library.py`** wraps `check` so the deploy gate enforces it;
   `scripts/lint_docs.py` (protected) is untouched.

**Reading contract (convention, not yet lint):** a skill or handbook that
needs a document cites it as `lib: <id> §<heading>` and reads it with
`python scripts/lib.py show <id> --section <heading>`; CLAUDE.md's "Before
you act" points at `docs/LIBRARY.md`. The research set keeps its own
`00-comparison-matrix.md` as the deep index; `LIBRARY.md` links to it.

**Non-goals:** embeddings; per-skill mandatory-reading lint; lessons-file
caps; touching `.context/INDEX.md` beyond one pointer row (it stays the
"I need to…" map; `LIBRARY.md` is the "what exists and is it current" map).

## Tasks

- [x] **Task 1 — tooling.** `scripts/lib.py` with the five commands, a
  `--root` flag for tests, exit 0/1/2 (ok / usage / check failed), last-line
  verdict `LIB <CMD> OK|FAIL`. `tests/test_library.py`: front-matter parse,
  id uniqueness, supersession symmetry, status vocabulary, index
  regeneration equality, `show --section` returns exactly one section,
  `grep` returns id-tagged paragraphs; fixtures under `tests/fixtures/library/`.
- [x] **Task 2 — front-matter sweep.** Add the block to every `docs/**/*.md`
  and `.context/org/**/*.md`; statuses from each document's own Status line
  or header (specs: the 2026-09-25 multi-model spec → `superseded`,
  `superseded_by: spec-2026-10-05-observability-and-trading-unblock`; PHASE
  plans → `historical`; EVALUATION reports → `report`/`historical` except
  the latest; research → `reference`; plans whose work shipped → `shipped`).
  Summaries are written from the document, not invented.
- [x] **Task 3 — index + pointers.** `python scripts/lib.py index` →
  `docs/LIBRARY.md`; `docs/README.md` and `.context/INDEX.md` gain one row
  pointing at it; CLAUDE.md "Before you act" step 0 names it; SYSTEM.md
  module-graph row for `scripts/lib.py`.
- [x] **Task 4 — gates + landing.** `lint_docs.py` all clean, full pytest,
  code-review LGTM, push on the INV-4 lane.

## Owner-facing effect

`python scripts/lib.py status spec-2026-09-25-multi-model-platform` answers
"superseded by spec-2026-10-05-observability-and-trading-unblock" in one
line; `lib.py show <id> --section "12"` returns a spec's decisions table
alone. The next step, if wanted, is a `reading:` key in skill front-matter
and a lint that caps mandatory reading per skill.
