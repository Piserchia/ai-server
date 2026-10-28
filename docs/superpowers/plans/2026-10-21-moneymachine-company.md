---
id: plan-2026-10-21-moneymachine-company
type: plan
status: shipped
date: 2026-10-21
supersedes: []
superseded_by: null
summary: >-
  Stand up the moneymachine project (canonical repo + runtime clone), the
  mmcore tooling, four bucket directories, nine mm-* skills, the
  moneymachine org division, three schedule rows and the registry paperwork.
  The spec records it BUILT-IN-SESSION; amendment 2026-10-27: the project
  became a hosted service (port 8794, /healthz).
---

# MoneyMachine Company Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the `moneymachine` project (canonical repo + prod runtime clone), its `mmcore` tooling, four bucket directories, nine `mm-*` ai-server skills, the `moneymachine` org division, three schedule rows and the registry paperwork — lint-clean, gate-green, landed on `origin/main`, armed at phase-0 cadence.

**Architecture:** Two repos. `~/Documents/repos/moneymachine` (new, GitHub `alfredbot-ai-butler/moneymachine`) holds the company constitution, bucket data, `shared/mmcore` (stdlib + pyyaml) and `shared/adapters` (keyless urllib). The ai-server worktree `.claude/worktrees/moneymachine` (branch `moneymachine/bootstrap` off `origin/main`) holds the skills, tests, charter, registries, schedules and docs. Skills are shared across buckets and parameterised by `bucket=` in the job description; all state lives in committed files; no `src/` change.

**Tech Stack:** Python 3.12 (per-job venv: `python3.12 -m venv .venv && .venv/bin/pip install -q pytest pyyaml`), pyyaml, pytest; ai-server skill frontmatter; bash for seeding; `gh` CLI (account `alfredbot-ai-butler`).

**Spec:** `docs/superpowers/specs/2026-10-21-moneymachine-company-design.md` (this plan cites its sections as §n; the spec travels with the plan).

## Global Constraints

- Never set `ANTHROPIC_API_KEY`; subscription auth only (CLAUDE.md).
- Never edit a protected path: `.context/PROTOCOL.md`, auth config/`.env`, `src/runner/guards.py`, `scripts/lint_docs.py`, `MISSION.md`, ORG.md § Operating model / § Privilege classes, `skills/{server-patch,server-deploy,new-skill}/SKILL.md`; never delete a project or skill (§3.1).
- Never touch a file owned by the in-flight `multi-model/cross-vendor-writer` branch: anything under `src/`, `.context/modules/**`, `.context/SYSTEM.md`, `skills/README.md`, `skills/TEMPLATE.md`, `tests/test_skill_contracts.py`, `docs/TROUBLESHOOTING.md`, `models.yml` (§3.1). All shared-registry edits are append-only at the anchors named in Task 13.
- No order path, no credentials, no paid data, no third-party packages beyond pyyaml + pytest (§10.1, §9.2). `mmcore` makes no network calls and runs no psql (§9.1). The only network code is `shared/adapters/`, routed through `_guard`.
- Interpreter contract everywhere: `python3.12`, never `python`/`python3`; `.venv/bin/python` once the venv exists (§3.1).
- Every `mm-*` SKILL.md body contains verbatim: `Dispatch only kinds matching \`mm-*\` with \`payload.project_slug\` = \`moneymachine\`. Any other kind — \`server-patch\`, \`new-skill\`, \`atlas-*\`, anything — is a DECISION-REQUEST ledger entry, never a dispatch.` (§7).
- Every schedule row and every dispatched child carries `{"project_slug":"moneymachine"}` (§3.1).
- Builders working in parallel write only the files their task lists and do not run `git commit` (the orchestrator commits after gates); they do run their task's tests.
- Commit messages end with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- Verification before any claim: run the command, paste the output.

## Review Focus

1. **A governor's budget check counts the wrong kinds** (the round-1 blocker): `budget.decide` must ignore governor/resumer/CEO/reporter counts and the skills' psql must list the five stage kinds exactly — pinned by `test_budget.py::test_decide_counts_only_stage_inputs` (Task 4) and `tests/test_mm_skills.py::test_budget_query_lists_stage_kinds_only` (Task 11).
2. **A stale clone**: a stage that works on the dev clone's old HEAD and then rebases could silently drop another stage's ledger lines — `mmcore preflight` fails when `HEAD..origin/main` is non-empty (`test_preflight.py::test_preflight_fails_when_behind_origin`, Task 6).
3. **A doc that quotes a forbidden token trips the tripwire** and halts a research stage: the scan is path-scoped to code/config and excludes `forbidden.py` + the test by name (`test_no_order_path.py::test_scan_scope_excludes_docs_and_forbidden_module`, Task 6).
4. **An agent opens a hypothesis family**: `families.assert_owner_opened` rejects any `open` row without `opened_by: owner`, and `saturate` refuses fewer than two ids (`test_families.py`, Task 4).
5. **A Telegram-originated `mm-report` run auto-continues forever** without `TASK_COMPLETE:`: pinned in `tests/test_mm_skills.py::test_report_and_govern_bodies_end_with_task_complete_rule` (Task 11).

---

## Repo layout decisions (locked for every task)

Canonical repo root `R = ~/Documents/repos/moneymachine`. Tree per §5.1. Extra decisions not in the spec:

- `shared/mmcore/forbidden.py` holds `FORBIDDEN_TOKENS: tuple[str, ...]`, `FORBIDDEN_IMPORT_RE: str`, `FORBIDDEN_URL_FRAGMENTS: tuple[str, ...]`, `ALLOWED_PUBLIC_PREFIXES: dict[str, tuple[str, ...]]` (host → allowed path prefixes). The tripwire test imports it and excludes it from the scan by name; `_guard.py` imports it. Owner-owned (listed in CLAUDE.md rule 3).
- Root resolution: `mmcore.root()` returns `$MM_ROOT` if set, else walks up from cwd to the first directory containing `company/config/settings.yaml`; raises `MMRootNotFound`.
- "No active cycle" = `buckets/<b>/state/cycle.json` absent; `cycle.load()` returns `None`.
- `FAMILIES.md` and `LIBRARY.md` are markdown tables (formats in Task 4 / Task 8).
- `trials.jsonl` line: `{"ts","bucket","cycle","family","sublane","params_hash","verdict","note"}`; `distinct_n` counts distinct `(family, params_hash)`.
- All dates/timestamps ISO-8601 UTC; `date -u +%F` style for ledger dates.

## ai-server worktree

`W = ~/Documents/repos/ai-server/.claude/worktrees/moneymachine`, venv python `V = ~/.local/share/virtualenvs/ai-server-SOXcmoRD/bin/python`. `.env` is symlinked into `W` already. Gate commands: `cd $W && $V scripts/lint_docs.py` and `cd $W && SERVER_ROOT="$PWD" $V -m pytest tests/test_doc_lint.py tests/test_skill_contracts.py tests/test_mm_skills.py -q`.

---

### Task 1: Repo skeleton, manifest, directive, project docs

**Files:**
- Create: `R/.gitignore`, `R/manifest.yml`, `R/CLAUDE.md`, `R/README.md`, `R/.context/CONTEXT.md`, `R/.context/CHANGELOG.md`, `R/skills/GOTCHAS.md`, `R/docs/DEVELOPMENT.md`, `R/docs/OWNER.md`, `R/integrations/ai-server/README.md`, `R/shared/pyproject.toml`, `R/reports/weekly/.gitkeep`, `R/reports/monthly/.gitkeep`
- Test: manifest validation command (below)

**Interfaces:**
- Produces: the repo root every other task writes into; `CLAUDE.md` Rule 1 text asserted by Task 6's tripwire.

- [ ] **Step 1: Create the root and git repo**

Run: `mkdir -p ~/Documents/repos/moneymachine && cd ~/Documents/repos/moneymachine && git init -b main && git status --short | wc -l`
Expected: `0`

- [ ] **Step 2: Write `.gitignore`**

Contents: `.env`, `.venv/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`, `*.tmp`, `.DS_Store`.

- [ ] **Step 3: Write `manifest.yml` exactly as §5.2** (no `web_root`, no `platforms`, no `env_files`; description's first line `NOT HOSTED — runner-scoping manifest only; never run scripts/register-project.sh.`)

- [ ] **Step 4: Validate the manifest with the server's loader**

Run: `cd ~/Documents/repos/ai-server/.claude/worktrees/moneymachine && ~/.local/share/virtualenvs/ai-server-SOXcmoRD/bin/python -c "from pathlib import Path; from src.registry.manifest import load; m=load(Path.home()/'Documents/repos/moneymachine/manifest.yml'); print(m.slug, m.type, m.delivery.topology, m.delivery.runtime_clone, m.delivery.deployable)"`
Expected: `moneymachine static dev-repo pull-only False`

- [ ] **Step 5: Write `CLAUDE.md`**

Sections, in order: title; **Rule 1** verbatim from §10.1 (bold lead, nine lines, the family clause included); **Rule 2 — deterministic spine** (numbers come from committed code and `mmcore`, never in-session arithmetic; one writer per artifact per §6.1); **Rule 3 — owner-owned files agents never edit**: `company/config/budget.yaml`, `company/config/settings.yaml`, `company/MM_AUTHORITY.md`, `company/LOOP.md`, `company/PROTOCOL.md`, `shared/mmcore/forbidden.py`, `shared/tests/test_no_order_path.py`, `shared/tests/test_owner_owned.py`, `shared/tests/test_protocol_phrases.py`, this file; **Topology** (GitHub-canonical `alfredbot-ai-butler/moneymachine`, branch `main`; dev clone `~/Documents/repos/moneymachine`; prod clone pull-only and read for `manifest.yml` only; `git pull --ff-only origin main` before work and `git pull --rebase origin main` before push; never commit in the prod clone; never force-push); **Interpreter contract** (`python3.12 -m venv .venv && .venv/bin/pip install -q pytest pyyaml`; `PYTHONPATH=shared .venv/bin/python -m mmcore …`; never `python`/`python3`); **Verification-first** (`PYTHONPATH=shared .venv/bin/python -m pytest shared/tests -q` and `.venv/bin/python -m mmcore check` before any claim of done); **Where the contracts live** (table: `company/COMPANY.md`, `LOOP.md`, `PROTOCOL.md`, `MM_AUTHORITY.md`, `officers/`, `buckets/<b>/CHARTER.md`, §8 grammar); **Write-back** (`.context/CHANGELOG.md` entry per run, `skills/GOTCHAS.md` for surprises, per `.context/PROJECT_PROTOCOL.md`).

- [ ] **Step 6: Write `README.md`** — what the company is (two paragraphs from §0), how to read a week (`reports/weekly/<Saturday>.md`), the honest expectation line (§1), the three schedule rows (§12.1), the kill switch, and a link to `docs/OWNER.md`.

- [ ] **Step 7: Write `.context/CONTEXT.md`** with the five standard sections: Mission (§0 first paragraph); Platforms (`primary: none — repo + Telegram`, web relationship none); Web Serving (`NOT HOSTED — manifest exists only for runner scoping; never register`); Architecture (the two-repo split, `mmcore` module table from §9.1, `shared/adapters`, the bucket tree, the nine skills with their archetypes from §4.2, the loop from §6.1, correlation keys §6.3); Status (built 2026-10-21, armed phase 0, first fires, D0–D8 open).

- [ ] **Step 8: Write `.context/CHANGELOG.md`** with one entry `## 2026-10-21 — bootstrap` (what: the tree; why: spec §0; verify: the two test commands).

- [ ] **Step 9: Write `skills/GOTCHAS.md`** seeded with four entries in the PROJECT_PROTOCOL §3.4 format (Symptom / Root cause / Fix): `python3` is Apple 3.9 in runner sessions; the dev clone can lag origin until a workspace job succeeds; `job.payload` is never in the prompt; `max_turns` exhaustion reads as completed and deletes the workspace.

- [ ] **Step 10: Write `docs/DEVELOPMENT.md`** — adopt atlas `docs/DEVELOPMENT.md`'s multi-machine rules (sync before/after, runtime clone rules) in MoneyMachine terms; the interpreter contract; how to run a stage locally: `export MM_ROOT=$PWD; PYTHONPATH=shared .venv/bin/python -m mmcore preflight --bucket etf`; how to run tests; the `~/Documents` hidden-`.pth` gotcha (use `PYTHONPATH`, never an editable install).

- [ ] **Step 11: Write `docs/OWNER.md`** — one page: how to read the memo; `/schedule pause|resume mm-ceo-weekly` (and `mm-report-weekly`, `mm-resume-daily`); the manual CEO trigger `psql assistant -c "UPDATE schedules SET next_run_at = NOW() WHERE name='mm-ceo-weekly'"` and why never `/task --kind=mm-ceo`; stopping in-flight chains (`enabled: false` committed and pushed from the Mini dev clone takes effect at the next job start); the on-demand pull `/task --project=moneymachine --kind=mm-report latest`; applying an approved `[system]` item (`/task --project=moneymachine --kind=mm-govern bucket=<b> mode=apply-system item=<n>`); the prod clone refresh `git -C "$SRV/projects/moneymachine" pull --ff-only`; the decisions outstanding D0–D8 copied from §16.

- [ ] **Step 12: Write `integrations/ai-server/README.md`** — the two-repo contract: skills are authored ONLY in ai-server `skills/mm-*/` (no byte-copies here, the alpha-lab precedent); schedule rows ONLY in ai-server `scripts/seed-schedules.sh`; what this repo must keep true for the skills (the `mmcore` CLI subcommand list of §9.1, the description grammar §8.1, the file paths of §5.1, the `TASK_COMPLETE:` rule).

- [ ] **Step 13: Write `shared/pyproject.toml`** — `[project] name="mmcore" version="0.1.0" requires-python=">=3.12" dependencies=["pyyaml>=6"]`; `[tool.pytest.ini_options] testpaths=["tests"]`.

- [ ] **Step 14: Verify the tree**

Run: `cd ~/Documents/repos/moneymachine && find . -path ./.git -prune -o -type f -print | sort`
Expected: the thirteen files above (plus the two `.gitkeep`).

---

### Task 2: Company constitution (COMPANY, LOOP, PROTOCOL, MM_AUTHORITY, ledgers, config)

**Files:**
- Create: `R/company/COMPANY.md`, `R/company/LOOP.md`, `R/company/PROTOCOL.md`, `R/company/MM_AUTHORITY.md`, `R/company/LEDGER.md`, `R/company/LESSONS.md`, `R/company/config/budget.yaml`, `R/company/config/settings.yaml`
- Test: `R/shared/tests/test_protocol_phrases.py`, `R/shared/tests/test_owner_owned.py` (written here; they pass once Tasks 2 and 8 exist — Task 2 writes them RED-aware)

**Interfaces:**
- Produces: the phrases Task 6's `test_protocol_phrases.py` asserts; the yaml keys `mmcore.budget.load` and `mmcore.settings.is_enabled` read (Task 3).

- [ ] **Step 1: Write the failing tests**

`shared/tests/test_protocol_phrases.py`:
```python
REQUIRED_PROTOCOL = ["momentum/evaluation/PROTOCOL.md", "Criteria observables:", "Success criterion:",
    "Kill criterion:", "Prior-art check:", "Survivorship probe:", "trials.jsonl", "INADMISSIBLE",
    "BLOCKED-ON-DATA", "budget death", "95th percentile", "Deflated Sharpe",
    "distinct (family, params_hash)", "pessimistic fills", "pre-seal fence"]
REQUIRED_LOOP = ["one writer per artifact", "dispatch AFTER the push", "cap-stalled",
    "Dispatch only kinds matching `mm-*`"]
def test_protocol_has_load_bearing_phrases(): ...  # each phrase in company/PROTOCOL.md
def test_loop_has_load_bearing_phrases(): ...      # each phrase in company/LOOP.md
```
`shared/tests/test_owner_owned.py`:
```python
BUDGET_KEYS = {"max_stage_jobs_per_day", "max_stage_jobs_per_bucket_per_week", "max_active_cycles_per_bucket",
    "max_governors_per_ceo_run", "max_engineer_attempts_per_cycle", "max_cycles_per_card", "weekly_list_spend_target_usd"}
def test_budget_yaml_has_exactly_documented_keys(): ...   # yaml.safe_load keys == BUDGET_KEYS; header line starts "# Owner-owned caps"
def test_settings_yaml_has_enabled_only(): ...           # keys == {"enabled"}; value is bool
def test_mm_authority_has_sections(): ...                # headings "## 0", "## 1", "## 2", "## 3", "## 4", "## 5 Decision log" present
def test_every_open_family_row_is_owner_opened(): ...    # for each buckets/*/knowledge/FAMILIES.md: mmcore.families.assert_owner_opened(path) raises nothing
```
Run: `cd R && python3.12 -m venv .venv && .venv/bin/pip install -q pytest pyyaml && PYTHONPATH=shared .venv/bin/python -m pytest shared/tests/test_protocol_phrases.py shared/tests/test_owner_owned.py -q`
Expected: FAIL (files missing / `mmcore` missing).

- [ ] **Step 2: Write `company/config/budget.yaml`** exactly as §12.2 and `company/config/settings.yaml`:
```yaml
# Owner-owned switch. `enabled: false` stops every mm-* session at preflight
# (fail-closed: a missing file or key also reads as disabled). Edit by hand in
# the Mini dev clone, commit, push; takes effect at the next job start.
enabled: true
```

- [ ] **Step 3: Write `company/COMPANY.md`** — §0 and §1 of the spec in company voice: mission; the objective function and the honest expectation (quote §3.2's three money lines); the five-bucket structure with D1 reserved; the hierarchy table (§4.2 columns 1–3); contracts index (which file governs what); feedback loops (§13 bullets); "how we report" (§11); "how we get better" (§13).

- [ ] **Step 4: Write `company/LOOP.md`** — the constitution, §6 in full with these headings: `## 0. Why this exists`, `## 1. Stages and movers` (§6.1 table + rhythm), `## 2. The audit spine` (§6.3 + the single-writer table: one writer per artifact), `## 3. Cycle state machine` (§6.2 incl. the edge table), `## 4. Chain mechanics` (§6.4 verbatim incl. the timeout table and the sentence `Dispatch only kinds matching \`mm-*\` …`), `## 5. Arbitrage-first` (§6.5), `## 6. Recovery matrix` (§6.6), `## 7. Ceilings` (§6.7), `## 8. Front door` (`[system]` item or DECISION-REQUEST → owner nod → owner commit or `mode=apply-system`), `## 9. Information passing` (§8.1–§8.6 verbatim).

- [ ] **Step 5: Write `company/PROTOCOL.md`** — child of atlas `momentum/evaluation/PROTOCOL.md` (parent, cited by that path) via `alpha-lab/evaluation/PROTOCOL.md` and `quant/evaluation/PROTOCOL.md` (read all three from `~/Documents/repos/atlas` before writing). Sections: `## 1 Pre-registration` (card sealed AND pushed before any backtest dispatch; `Success criterion:` / `Kill criterion:` / `Criteria observables:`; `Prior-art check:` across every atlas ledger + every bucket, killed-elsewhere ⇒ NOT-ACTIONABLE same day; ≤2 parameters per confirmatory cycle; every grid cell is a trial); `## 2 Data regimes` (TRAIN / VALIDATION / FORWARD; ≤3 validation touches per year logged; failed validation is dead; the pre-seal fence: the probe may not compute any signal × forward-return statistic; `Survivorship probe:` for universe-selection ideas; provenance `manifest.json` per run and shadow book: source_url, fetch timestamp, sha256, row counts, adjustment note); `## 3 Evidence law` (costs ≥3 bps/side + spread, pessimistic fills, random-entry placebo M ≥ 200 and the candidate must beat its 95th percentile, Deflated Sharpe vs lifetime N where N = distinct (family, params_hash), worst-fold walk-forward, 8-check critic; PASS iff DSR > quant `dsr_threshold` (0.95 today) AND worst fold > 0 AND no critic FAIL AND placebo beaten; LLM-signal strategies INADMISSIBLE on historical data ⇒ BLOCKED-ON-DATA; regime tags, NON-ROBUST if profit concentrates in one regime); `## 4 Budgets` (`max_cycles_per_card`, budget death ⇒ not_actionable; the §12.2 keys are owner-owned); `## 5 Separation of duties` (researcher ≠ bridge ≠ engineer ≠ governor; frozen evaluator never edits harnesses, budgets, cards, skills; independent DSR recompute, mismatch > 1e-6 ⇒ PROTOCOL-VIOLATION); `## 6 Ledgers and lessons` (append-only, ids strictly increasing, trials rows before verdicts, one LESSON line per terminal decision, null result = process success); `## 7 Graduation` (points at MM_AUTHORITY.md).

- [ ] **Step 6: Write `company/MM_AUTHORITY.md`** — §10.3 with headings `## 0 Decide honestly`, `## 1 Evidence preconditions`, `## 2 The offer and the per-target route`, `## 3 Automatic demotion`, `## 4 Standing controls`, `## 5 Decision log` (empty, owner appends).

- [ ] **Step 7: Write `company/LEDGER.md`** header (append-only rules; entry format §8.4 with prefix `C-`; kinds DECISION, AUDIT, DECISION-REQUEST, LESSON) and `company/LESSONS.md` header (format `- [<cycle or week>] <bucket>/<family> | <kill-class> | <reusable constraint>`), each with no entries.

- [ ] **Step 8: Run the phrase/owner tests**

Run: `cd R && PYTHONPATH=shared .venv/bin/python -m pytest shared/tests/test_protocol_phrases.py -q`
Expected: PASS (the owner-owned test's family check stays RED until Tasks 3 and 8 land — note it in the task report).

---

### Task 3: `mmcore` core — root, settings, budget, ledger, artifacts

**Files:**
- Create: `R/shared/mmcore/__init__.py`, `R/shared/mmcore/root.py`, `R/shared/mmcore/settings.py`, `R/shared/mmcore/budget.py`, `R/shared/mmcore/ledger.py`, `R/shared/mmcore/artifacts.py`
- Test: `R/shared/tests/conftest.py` (a `tmp_root` fixture that builds a minimal company tree with config + one bucket `demo`), `R/shared/tests/test_settings_fail_closed.py`, `R/shared/tests/test_budget.py`, `R/shared/tests/test_ledger.py`, `R/shared/tests/test_artifacts.py`

**Interfaces:**
- Produces:
  - `mmcore.root.root(start: Path | None = None) -> Path` (honours `MM_ROOT`; raises `MMRootNotFound`)
  - `mmcore.settings.is_enabled(root: Path | None = None) -> bool`
  - `mmcore.budget.load(root: Path) -> dict`; `mmcore.budget.decide(budget: dict, bucket: str, jobs_today: int, jobs_week: int, active_cycles: int) -> tuple[str, str]`
  - `mmcore.ledger.Entry` dataclass (`id: int, prefix: str, kind: str, cycle: str, date: str, job: str, body: str`); `next_id(path: Path, prefix: str) -> int`; `append(path: Path, kind: str, cycle: str, job: str, body: str, date: str) -> str` (returns the new id string e.g. `B-0007`); `parse(path: Path) -> list[Entry]`; `audit(path: Path) -> list[str]`
  - `mmcore.artifacts.parse_header(path: Path) -> dict[str, str]`; `next_artifact_id(root: Path, bucket: str, prefix: str) -> str`; `new_artifact(root: Path, bucket: str, prefix: str, header: dict[str, str], body: str) -> Path`
  - Artifact dirs by prefix: `RB` → `research/`, `AC` → `cards/`, `AP` → `plans/`, `IM` → `projects/_records/`, `XR` → `runs/_records/`
  - Ledger kinds (bucket): `BRIEF CARD PLAN IMPL EXEC GRADE AUDIT DECISION-REQUEST GRADUATION-OFFER LESSON PROTOCOL-VIOLATION`; (company): `DECISION AUDIT DECISION-REQUEST LESSON`
  - Ledger header regex: `^## \[(?P<prefix>[A-Z])-(?P<num>\d{4})\] (?P<kind>[A-Z-]+) · (?P<cycle>\S+) · (?P<date>\d{4}-\d{2}-\d{2}) · job (?P<job>[0-9a-f]{8})$`

- [ ] **Step 1: Write the failing tests**

`test_settings_fail_closed.py`: `test_missing_file_is_disabled`, `test_missing_key_is_disabled`, `test_enabled_true_reads_true`, `test_enabled_string_is_disabled` (`enabled: "yes"` → False).
`test_budget.py`: `test_allow_when_under_every_cap`; `test_deny_when_day_cap_hit` (jobs_today=4 with cap 4 → DENY, reason contains `max_stage_jobs_per_day`); `test_deny_when_bucket_week_cap_hit`; `test_deny_when_active_cycles_exceeded` (active_cycles=2, cap 1); `test_decide_counts_only_stage_inputs` (the function signature has no governor/report inputs and the yaml header contains "Governors, the resumer, the CEO and the reporter are never counted" — assert the header text).
`test_ledger.py`: `test_append_allocates_sequential_ids` (B-0001 then B-0002); `test_parse_roundtrip`; `test_audit_flags_gap_and_duplicate` (hand-write B-0001, B-0003 → finding; B-0001 twice → finding); `test_audit_flags_unknown_kind`; `test_append_refuses_unknown_kind` (`ValueError`); `test_append_refuses_when_history_edited` (append, then mutate an old entry's header, then append → `LedgerIntegrityError`; implement by storing a trailing `<!-- mm-ledger-sha: … -->` line over all prior entries).
`test_artifacts.py`: `test_new_artifact_writes_header_then_body_and_increments_id`; `test_parse_header_reads_key_value_lines_until_blank`; `test_unknown_prefix_raises`.
Run: `cd R && PYTHONPATH=shared .venv/bin/python -m pytest shared/tests/test_settings_fail_closed.py shared/tests/test_budget.py shared/tests/test_ledger.py shared/tests/test_artifacts.py -q`
Expected: FAIL (`ModuleNotFoundError: mmcore`).

- [ ] **Step 2: Implement `root.py`, `settings.py`, `budget.py`** per the signatures. `decide` reasons are the yaml key names that bound.

- [ ] **Step 3: Implement `ledger.py`** — append-only with the integrity line; `audit` returns one string per finding (`gap before B-0003`, `duplicate id B-0001`, `unknown kind FOO in B-0002`, `header malformed at line N`, `integrity sha mismatch`).

- [ ] **Step 4: Implement `artifacts.py`** — header = `key: value` lines until the first blank line; `new_artifact` writes `<prefix>-<nnnn>.md` with the header (adds `id:` first) then a blank line then the body.

- [ ] **Step 5: Run the four test files**

Run: as Step 1. Expected: PASS.

---

### Task 4: `mmcore` state and knowledge — cycle, trials, families, data, shadow, report

**Files:**
- Create: `R/shared/mmcore/cycle.py`, `R/shared/mmcore/trials.py`, `R/shared/mmcore/families.py`, `R/shared/mmcore/data.py`, `R/shared/mmcore/shadow.py`, `R/shared/mmcore/report.py`
- Test: `R/shared/tests/test_cycle_state.py`, `R/shared/tests/test_trials.py`, `R/shared/tests/test_families.py`, `R/shared/tests/test_shadow.py`, `R/shared/tests/test_report.py`, fixture `R/shared/tests/fixtures/closes_spy.csv`, `closes_bil.csv`, `closes_x.csv` (20 rows each, `date,close`)

**Interfaces:**
- Consumes: Task 3 `root`, `ledger.parse`.
- Produces:
  - `mmcore.cycle`: `STAGES = ("open","research","bridge","architect","engineer","execute","graded","closed")`; `OUTCOMES = ("graded","not_actionable","blocked_on_data","plan_rejected","blocked","rejected","halted")`; `TRANSITIONS: dict[str, set[str]]` = open→{research}; research→{bridge}; bridge→{architect, closed:not_actionable, closed:blocked_on_data}; architect→{engineer, closed:plan_rejected}; engineer→{execute, closed:blocked, closed:rejected}; execute→{graded, closed:halted}; graded→{closed:graded}. Functions: `load(root, bucket) -> dict | None`; `open(root, bucket, question, family, sublane, job_id, now=None) -> dict` (allocates `<bucket>-C####` from `history/` + current); `advance(root, bucket, to_stage, job_id, artifact: tuple[str,str] | None = None, now=None) -> dict`; `close(root, bucket, outcome, job_id, now=None) -> Path` (moves to `history/<cycle_id>.json`); `validate(root, bucket) -> list[str]`; `is_stale(cycle: dict, now: datetime, hours: float = 6) -> bool`; `IllegalTransition(ValueError)`.
  - `mmcore.trials`: `append(root, bucket, family, sublane, params_hash, verdict, note, cycle, ts=None) -> dict`; `distinct_n(root, bucket) -> int`; `verdicts` allowed: `registered reject pass placebo-fail blocked`.
  - `mmcore.families`: table columns `| family | sublane | status | opened_by | ids | note |`; `parse(path) -> list[dict]`; `assert_owner_opened(path) -> None` (raises `FamilyGovernanceError` listing offending rows); `saturate(path, family, sublane, ids: list[str], reason: str) -> None` (requires ≥2 ids and current status `open`; rewrites the row); `propose(path, family, sublane, note) -> None` (appends `proposed` row with `opened_by: agent`); `next_arbitrage_sublane(path) -> str | None` (first `arbitrage` row with status `open`, else None).
  - `mmcore.data.load_closes(path) -> dict[date, float]` (CSV `date,close`, sorted).
  - `mmcore.shadow`: `Book` dataclass (`bucket, cash: float, positions: dict[str, float], trades: list[dict], curve: list[dict]`) with `load(root, bucket) -> Book` (new book with cash 100000.0 when absent) / `save(root, bucket)`; `trade(book, date, symbol, units, price, cost_bps=3.0, side_cost_bps=0.0)` (pessimistic: buys pay `price*(1+cost_bps/1e4)`, sells receive `price*(1-cost_bps/1e4)`); `mark(book, date, closes: dict[str, float], spy: float, bil: float)` appends `{"date","equity","spy","bil"}`; `excess_vs(book) -> dict` with keys `book_return spy_return bil_return excess_vs_spy excess_vs_bil sessions` (returns from first to last curve point; zeros when < 2 points).
  - `mmcore.report`: `weekly_skeleton(root, saturday: str) -> str` (markdown with the seven §11 sections; the scoreboard rows from each bucket's cycle/history/last GRADE/`distinct_n`/`excess_vs`; CEO status line left as `{{CEO_STATUS}}` placeholder); `monthly_skeleton(root, month: str, jobs_rows: list[dict], usage_rows: list[dict]) -> str` (jobs by kind vs the structural ceiling 22/week, failure + cap-stall rates, spend sum).

- [ ] **Step 1: Write the failing tests**

`test_cycle_state.py`: `test_open_allocates_first_id_and_writes_file`; `test_open_refuses_when_active_cycle_exists`; `test_advance_legal_path_to_graded`; `test_illegal_edge_raises` (research→architect); `test_close_from_bridge_with_not_actionable_moves_to_history`; `test_close_with_outcome_not_allowed_from_stage_raises` (bridge→halted); `test_validate_reports_unknown_stage`; `test_is_stale_true_after_six_hours`; `test_advance_refreshes_last_advanced_and_job`.
`test_trials.py`: `test_append_writes_line_and_distinct_n_counts_pairs` (same `(family, params_hash)` twice → N=1); `test_unknown_verdict_raises`.
`test_families.py`: `test_parse_table`; `test_assert_owner_opened_passes_on_seed`; `test_open_row_without_owner_raises`; `test_saturate_requires_two_ids`; `test_saturate_rewrites_row_and_keeps_others`; `test_propose_appends_agent_row`; `test_next_arbitrage_sublane_skips_saturated`.
`test_shadow.py`: `test_buy_then_mark_applies_pessimistic_cost`; `test_excess_vs_computes_returns_from_curve`; `test_load_new_book_has_default_cash`.
`test_report.py`: `test_weekly_skeleton_has_seven_sections_and_one_row_per_bucket`; `test_monthly_skeleton_reports_against_ceiling`.
Run: `cd R && PYTHONPATH=shared .venv/bin/python -m pytest shared/tests/test_cycle_state.py shared/tests/test_trials.py shared/tests/test_families.py shared/tests/test_shadow.py shared/tests/test_report.py -q`
Expected: FAIL.

- [ ] **Step 2: Implement the six modules** per the interfaces (no network, no psql; whole-file replace with validation for FAMILIES.md; `cycle.json` written atomically via temp file + rename).

- [ ] **Step 3: Run the five test files** — Expected: PASS.

---

### Task 5: Adapters with the public-path guard, and the forbidden registry

**Files:**
- Create: `R/shared/mmcore/forbidden.py`, `R/shared/adapters/__init__.py`, `R/shared/adapters/_guard.py`, `R/shared/adapters/stooq.py`
- Test: `R/shared/tests/test_adapters_guard.py`, `R/shared/tests/test_stooq.py`, fixture `R/shared/tests/fixtures/stooq_spy.csv` (Stooq's `Date,Open,High,Low,Close,Volume` header + 5 rows)

**Interfaces:**
- Produces:
  - `mmcore.forbidden.FORBIDDEN_TOKENS` = union of the six atlas tripwire lists (copy verbatim from `~/Documents/repos/atlas/{trader/tests/test_paper_only.py, value/tests/test_no_order_path.py, firm/tests/test_advisory_only.py, quant/tests/test_reports_only.py, alpha-lab/tests/test_verdicts_only.py, swing/tests/test_live_guard.py}`) + the §10.2 additions; `FORBIDDEN_IMPORT_RE = r"^\s*(from|import)\s+(tradingcore|swing|trader|alpaca|tradier|ccxt|quantlab\.data|quantlab\.cli)\b"`; `FORBIDDEN_URL_FRAGMENTS = ("/private/", "/trade/", "/orders", "/asset/", "/accounts/")`; `ALLOWED_PUBLIC_PREFIXES = {"stooq.com": ("/q/d/l/",), "api.kraken.com": ("/0/public/",), "api.exchange.coinbase.com": ("/products/",), "www.okx.com": ("/api/v5/market/", "/api/v5/public/")}`.
  - `adapters._guard.check_url(url: str) -> str` (returns the url; raises `ForbiddenEndpoint` on a non-allowlisted host, a disallowed prefix, or any forbidden fragment); `adapters._guard.open_public(url: str, timeout: float = 20.0) -> bytes` (the ONLY place `urllib.request.urlopen` is called in the repo; no headers beyond `User-Agent: moneymachine/0.1`).
  - `adapters.stooq.fetch_daily_closes(symbol: str, start: str | None = None, end: str | None = None) -> dict[date, float]` (URL `https://stooq.com/q/d/l/?s=<symbol>&i=d`; symbol like `spy.us`, `bil.us`); `parse_csv(text: str) -> dict[date, float]`; `save_csv(closes, path)`.

- [ ] **Step 1: Write the failing tests**

`test_adapters_guard.py`: `test_allows_stooq_daily`; `test_rejects_kraken_private`; `test_rejects_coinbase_orders_path`; `test_rejects_okx_trade_path`; `test_rejects_unknown_host`; `test_open_public_is_only_urlopen_call_site` (grep `shared/` for `urlopen(` → exactly one file: `_guard.py`).
`test_stooq.py`: `test_parse_csv_reads_close_column_sorted` (fixture); `test_fetch_builds_guarded_url` (monkeypatch `open_public` to return the fixture bytes, assert the url passed equals `https://stooq.com/q/d/l/?s=spy.us&i=d`); `test_live_probe` skipped unless `MM_LIVE_PROBE=1` (fetches `spy.us`, asserts ≥ 100 rows).
Run: `cd R && PYTHONPATH=shared .venv/bin/python -m pytest shared/tests/test_adapters_guard.py shared/tests/test_stooq.py -q`
Expected: FAIL.

- [ ] **Step 2: Implement `forbidden.py`, `_guard.py`, `stooq.py`** per the interfaces.

- [ ] **Step 3: Run the tests; then the live probe once**

Run: `cd R && PYTHONPATH=shared .venv/bin/python -m pytest shared/tests/test_adapters_guard.py shared/tests/test_stooq.py -q && MM_LIVE_PROBE=1 PYTHONPATH=shared .venv/bin/python -m pytest shared/tests/test_stooq.py -q -k live`
Expected: PASS both (if the live probe fails for network reasons, record the exact error in the task report; the fixture tests must still pass).

---

### Task 6: Tripwire, preflight, bucket template, `new-bucket`, and the CLI

**Files:**
- Create: `R/shared/mmcore/preflight.py`, `R/shared/mmcore/new_bucket.py`, `R/shared/mmcore/cli.py`, `R/shared/mmcore/__main__.py`, `R/buckets/_TEMPLATE/**` (every file of §5.1's bucket tree with `<BUCKET>`/`<NAME>` placeholders: `CHARTER.md`, `officers/{research,bridge,architect,engineer,execute,govern}.md`, `knowledge/LIBRARY.md`, `knowledge/FAMILIES.md`, `evaluation/LEDGER.md`, `evaluation/LESSONS.md`, `evaluation/trials.jsonl` (empty), `BACKLOG.md`, `research/.gitkeep`, `cards/.gitkeep`, `plans/.gitkeep`, `projects/.gitkeep`, `runs/.gitkeep`, `shadow/.gitkeep`, `state/history/.gitkeep`)
- Test: `R/shared/tests/test_no_order_path.py`, `R/shared/tests/test_preflight.py`, `R/shared/tests/test_new_bucket.py`, `R/shared/tests/test_cli.py`

**Interfaces:**
- Consumes: Tasks 3–5.
- Produces:
  - `mmcore.preflight.run(root, bucket: str | None, read_only: bool = False) -> tuple[bool, list[str]]` — checks in order: python ≥ 3.12; `import yaml`; settings enabled (read-only mode reads `git show origin/main:company/config/settings.yaml`); git branch == `main`; `git fetch origin` then `git rev-list --count HEAD..origin/main` == 0 (skipped when `MM_SKIP_GIT=1`, used by tests); bucket dir exists when given; tripwire tests pass (`pytest shared/tests/test_no_order_path.py -q` subprocess, skipped when `MM_SKIP_TRIPWIRE=1`).
  - `mmcore.new_bucket.stamp(root, slug: str, name: str) -> Path` (copies `_TEMPLATE`, substitutes placeholders, refuses an existing slug or a slug not matching `^[a-z][a-z0-9-]{1,23}$`).
  - CLI (`python -m mmcore …`), every command prints as its LAST line `MMCORE <COMMAND> <VERDICT>[ <detail>]`, exit codes 0 ok / 1 error / 2 DENY-or-FAIL:
    - `preflight [--bucket b] [--read-only]`
    - `budget --bucket b --jobs-today N --jobs-week M --active-cycles K`
    - `cycle show|open|advance|close --bucket b [--question Q --family F --sublane S] [--to STAGE] [--artifact KEY=ID] [--outcome O] --job J`
    - `ledger append (--bucket b | --company) --kind K --cycle C --job J --body-file F [--date D]`; `ledger audit (--bucket b | --company | --all)`
    - `trials append --bucket b --family F --sublane S --params-hash H --verdict V --note N --cycle C`; `trials n --bucket b`
    - `families next|saturate|propose --bucket b [--family F --sublane S --ids A,B --reason R | --note N]`
    - `shadow trade|mark|report --bucket b [...]`
    - `report weekly --saturday YYYY-MM-DD [--out PATH]`; `report monthly --month YYYY-MM --jobs-csv F --usage-csv F [--out PATH]`
    - `new-bucket SLUG --name NAME`
    - `check` (= preflight without bucket + `ledger audit --all` + `cycle validate` for every bucket + `families assert` for every bucket)
  - The tripwire: `test_no_order_path.py` scans files matching `*.py *.yaml *.yml *.json *.toml` under `shared/`, `buckets/*/projects/`, `buckets/*/shadow/`, `company/config/`, excluding `.git`, `.venv`, `shared/mmcore/forbidden.py` and itself; fails on any `FORBIDDEN_TOKENS` substring or `FORBIDDEN_IMPORT_RE` match; asserts the five Rule-1 phrases of §10.1 in `CLAUDE.md` after whitespace normalisation; asserts `shared/mmcore/atlas_bridge.py` (Task 7) contains neither `tradingcore` nor `quantlab.data` (skip if the file does not exist yet); asserts every `http` URL literal under `shared/adapters/` passes `check_url`.

- [ ] **Step 1: Write the failing tests**

`test_no_order_path.py` as specified, plus `test_scan_scope_excludes_docs_and_forbidden_module` (a temp `.md` under `shared/` containing `AddOrder` does not fail; `forbidden.py` itself is skipped).
`test_preflight.py`: `test_preflight_fails_when_disabled`; `test_preflight_passes_on_clean_enabled_root` (with `MM_SKIP_GIT=1 MM_SKIP_TRIPWIRE=1`); `test_preflight_fails_when_behind_origin` (monkeypatch the git helper to return count 1); `test_preflight_fails_on_missing_bucket`.
`test_new_bucket.py`: `test_stamp_creates_full_tree_with_substitutions`; `test_stamp_refuses_existing_slug`; `test_stamp_refuses_bad_slug`; `test_live_buckets_match_template_tree` (for each of `etf longterm shortterm crypto`: every relative file path in `_TEMPLATE` (excluding `.gitkeep`) exists in the bucket — RED until Task 8).
`test_cli.py`: `test_budget_cli_allow_exit_0_and_verdict_line`; `test_budget_cli_deny_exit_2`; `test_cycle_cli_open_then_show`; `test_ledger_cli_append_prints_id`; `test_check_cli_on_fixture_root_exit_0`; `test_unknown_command_exit_1`.
Run: `cd R && PYTHONPATH=shared .venv/bin/python -m pytest shared/tests/test_no_order_path.py shared/tests/test_preflight.py shared/tests/test_new_bucket.py shared/tests/test_cli.py -q`
Expected: FAIL.

- [ ] **Step 2: Write `buckets/_TEMPLATE/`** — placeholder content with the exact formats: `FAMILIES.md` table with rows `| arbitrage | <sublane-1> | open | owner (seed <DATE>) |  | <note> |`, `| cash-yield | - | open | owner (seed <DATE>) |  | the grade-A baseline |`, `| cost-model | - | open | owner (seed <DATE>) |  | costs always modelled |`; `LIBRARY.md` table header `| id | claim | source | checked | grade | status |`; `LEDGER.md` header (prefix `B-`, kinds list, append-only rules); `LESSONS.md` header; `BACKLOG.md` header (`## Open` / `## Done`; item format `- [ ] #<n> [<tag>] <desc> — done-evidence: <…>`); `CHARTER.md` with headings `## Mission`, `## Universe`, `## Arbitrage lane and sub-lanes`, `## Data policy (free, probed)`, `## Ceilings`, `## Atlas substrate (read-only)`, `## Cycle-1 question`; officer specialisations with headings `## Domain priors`, `## Data sources (free, probed)`, `## What NOT to retry`, `## Acceptance specifics`.

- [ ] **Step 3: Implement `preflight.py`, `new_bucket.py`, `cli.py`, `__main__.py`** per the interfaces (argparse subcommands; every command resolves `root()` once).

- [ ] **Step 4: Run the four test files**

Run: as Step 1. Expected: PASS except `test_live_buckets_match_template_tree` (RED until Task 8; state it).

---

### Task 7: `atlas_bridge` and the officer handbooks

**Files:**
- Create: `R/shared/mmcore/atlas_bridge.py`, `R/company/officers/README.md`, `R/company/officers/{ceo,govern,research,bridge,architect,engineer,execute,resume,report}.md`
- Test: `R/shared/tests/test_atlas_bridge.py`

**Interfaces:**
- Produces: `mmcore.atlas_bridge.atlas_root() -> Path` (`$ATLAS_ROOT` or `~/Documents/repos/atlas`; raises `AtlasUnavailable` if absent); `quantlab() -> types.SimpleNamespace` exposing exactly `engine metrics dsr walkforward leakage trials health sizing report` (imports each by `importlib.import_module("quantlab.<m>")` after inserting `<atlas>/quant` into `sys.path`; never imports `quantlab.data` / `quantlab.cli`); `library_paths() -> list[Path]`; `ledger_paths() -> list[Path]` (every `*/evaluation/LEDGER.md` and `*/evaluation/trials.jsonl` under atlas).

- [ ] **Step 1: Write the failing tests**

`test_atlas_bridge.py`: `test_quantlab_namespace_has_only_pure_modules` (monkeypatch `importlib.import_module` to record names; assert set equality and that no name contains `data` or `cli`); `test_source_contains_no_forbidden_tokens` (`tradingcore`, `quantlab.data` absent from the module source); `test_atlas_unavailable_raises_when_root_missing` (`ATLAS_ROOT=/nonexistent`); `test_real_quantlab_imports_if_present` (skipped unless `~/Documents/repos/atlas/quant/quantlab/dsr.py` exists; asserts `quantlab().dsr` has an attribute named like `deflated_sharpe`).
Run: `cd R && PYTHONPATH=shared .venv/bin/python -m pytest shared/tests/test_atlas_bridge.py -q`
Expected: FAIL.

- [ ] **Step 2: Implement `atlas_bridge.py`** per the interface.

- [ ] **Step 3: Write the handbooks.** Read first: `~/Documents/repos/atlas/knowledge/roles/{governor,researcher,supervisor}.md`, `~/Documents/repos/atlas/.claude/agents/{engineer,sector-architect,pipeline-scout}.md`, `~/Documents/repos/atlas/firm/charters/cio.md`. Every handbook uses the headings `# <Role> — handbook`, `## Mandate`, `## Non-negotiables`, `## Inputs you read`, `## The artifact you leave`, `## Forbidden`, `## How you get better`, `## Voice`, and cites the archetype it adopts by path. Pin per handbook:
  - `ceo.md`: the rotation default (week 1 `etf` + `crypto`, week 2 `longterm` + `shortterm`, then open-cycle-outranks-new; deviations need a stated reason); the absolute paths `~/Library/Application Support/ai-server/volumes/audit_log/<id8>*.summary.md` and `volumes/telemetry/schedule_adherence.json`; the psql queries to enumerate `mm-*` jobs since its last run and to read `job_completed.usage`; the final-text contract §8.6 with `DECISION:` / `ASK-OWNER:` lines; dispatch ≤ `max_governors_per_ceo_run`.
  - `govern.md`: the three grade questions (§13); the DSR recompute from `validation/R-####/metrics.json` via `atlas_bridge.quantlab().dsr`; family-status rules (§6.5); `mode=apply-system` write surface limited to `company/officers/*`, `buckets/<b>/officers/*`, `BACKLOG.md`.
  - `research.md`: library row format; `Prior-art check:` across `atlas_bridge.ledger_paths()` + every bucket; arbitrage sub-lane first; the INADMISSIBLE flag for LLM-signal mechanisms.
  - `bridge.md`: the card checklist (§8.5 row 3) as a literal template block with every required line.
  - `architect.md`: the acceptance-row template including the validation-report row and the reuse table.
  - `engineer.md`: 2-attempt cap, blocker format (from atlas `engineer.md`), the `run.py --date` contract (exit 0/2/1, `runs/<date>-<name>.json` + `manifest.json`), the validation report layout `validation/R-####/{metrics.json,report.md,manifest.json}` and PASS law, `code-review` LGTM line format `REVIEW: APPROVED — <item> (code-review subagent, job <id8>)`.
  - `execute.md`: supervisor non-negotiables; `shadow` CLI calls; the XR template.
  - `resume.md`: staleness rule, double-dispatch psql guard, cap-stalled retry, writes nothing.
  - `report.md`: the seven memo sections; how to find the CEO summary file; the monthly scoreboard inputs (the two psql queries producing `jobs.csv` and `usage.csv`); the `latest` on-demand mode; `TASK_COMPLETE:`.
  - `README.md`: layering rule (company handbook + `buckets/<b>/officers/<role>.md`), the rotation default, the table role → skill → archetype path.

- [ ] **Step 4: Run the bridge test** — Expected: PASS (the real-quantlab test passes on the Mini).

---

### Task 8: The four buckets (one sub-task per bucket; parallelisable)

**Files (per bucket `b ∈ {etf, longterm, shortterm, crypto}`):**
- Create: `R/buckets/<b>/CHARTER.md`, `R/buckets/<b>/officers/{research,bridge,architect,engineer,execute,govern}.md`, `R/buckets/<b>/knowledge/LIBRARY.md`, `R/buckets/<b>/knowledge/FAMILIES.md`, `R/buckets/<b>/evaluation/{LEDGER.md,LESSONS.md,trials.jsonl}`, `R/buckets/<b>/BACKLOG.md`, the `.gitkeep` dirs
- Test: `shared/tests/test_new_bucket.py::test_live_buckets_match_template_tree`, `shared/tests/test_owner_owned.py::test_every_open_family_row_is_owner_opened`, `.venv/bin/python -m mmcore check`

**Interfaces:**
- Consumes: Task 6's `_TEMPLATE` formats; Task 4's `families` table format.
- Produces: the data the skills read.

Pinned content per bucket (everything else per §4.1 and §3.2; cite sources by path/URL with `checked: 2026-10-21`):

- `etf`: FAMILIES rows — `arbitrage/premium-discount` **saturated** ids `A-0007 A-0013 A-0015 A-0016` (note: dead on free daily data; the discount closes from the NAV side); `arbitrage/levered-rebalance` **saturated** ids `A-0007 A-0013`; `arbitrage/creation-redemption` open (note: AP-only; likely BLOCKED-ON-DATA — must be shown, not assumed); `trend-overlay` open; `allocation-rule` open; `cash-yield`; `cost-model`. LIBRARY seeds: the three money lines, the 28/28 REJECT fact, the trend-overlay grades, the A-0007/13/15/16 kills, SPY↔SGOV policy T-0002 "no alpha claim". Substrate map: `trader/`, `quant/`, `k401`.
- `longterm`: FAMILIES — `arbitrage/cef-discount` open; `arbitrage/merger-spac` open (note: likely BLOCKED-ON-DATA on free data); `arbitrage/index-inclusion` open; `value-quality` open; `retirement-sleeve` open; `cash-yield`; `cost-model`. LIBRARY seeds: the money lines; value advisor status (zero theses in 7 weeks — Tradier quote token missing, grade: unmeasured); k401 weekly review exists; 15-years-of-monthly-obs line.
- `shortterm`: FAMILIES — `arbitrage/pairs-residual` open (note: inherits the F-04 contamination line: corr(conditioner, traded leg's own return) < 0.5643 or it is a re-mine; ids A-0017 A-0018 A-0021 A-0023 A-0024 listed in the note, status stays open because the lane is not exhausted, only fenced); `arbitrage/index-rebalance-flow` open; `arbitrage/pead` open (note: twice BLOCKED-ON-DATA on Finnhub token — inherit as BLOCKED until the owner provisions); `swing-mechanics` open; `cash-yield`; `cost-model`. LIBRARY seeds: Taiwan/Brazil negative-EV, Profit Mirage decay, the F-04 kills with the 0.5643 line, swing 77/77 provisioning_gap, momentum E-0026 74 % survivorship FAIL. LESSONS.md first line: `- [seed] arbitrage/pairs-residual | contamination | any pairs/residual conditioner must show corr(conditioner, traded leg's own return) < 0.5643 on the card or it is a re-mine (A-0017/18/21/23/24)`.
- `crypto`: FAMILIES — `arbitrage/cross-exchange-spot` open (note: zero priors; public order books only; must net fees + withdrawal friction); `arbitrage/funding-basis` open (note: zero priors; OKX public funding); `trend-spot` open; `cash-yield`; `cost-model`. LIBRARY seeds: Alpha Arena 42–59 % losses (grade C, secondary source, unverified dates); crypto grade-C exclusion; perps.py BUILT not live; kraken candle feed stale since 2026-08-23; never-enable-Crypto-Wallets rule (trader DESIGN D10); D2 advisory-forever note. CHARTER `## Ceilings`: "advisory forever unless the owner opens a venue (D2); every spread must be computed net of taker fees on both venues and withdrawal cost; shadow units only".
- Every CHARTER `## Cycle-1 question` = the §4.1 column verbatim; every `## Arbitrage lane and sub-lanes` lists the FAMILIES sub-lanes with status; every officer specialisation ≤ 60 lines with the four headings.

- [ ] **Step 1: Stamp the bucket from the template**

Run: `cd R && PYTHONPATH=shared .venv/bin/python -m mmcore new-bucket <b> --name "<Name>"`
Expected: last line `MMCORE NEW-BUCKET OK buckets/<b>`.

- [ ] **Step 2: Replace the placeholder content** with the pinned content above (read atlas `alpha-lab/evaluation/LESSONS.md`, `FAMILIES.md`, `quant/evaluation/LEDGER.md`, `knowledge/<sector>/CLAUDE.md`, `docs/research/llm-landscape-2026-09/crosscut-finance-trading-ai.md` §5/§8 to write real, sourced claims — no invented URLs; when a claim's source is an atlas file, cite the path).

- [ ] **Step 3: Verify**

Run: `cd R && PYTHONPATH=shared .venv/bin/python -m pytest shared/tests/test_new_bucket.py shared/tests/test_owner_owned.py -q && PYTHONPATH=shared MM_SKIP_GIT=1 .venv/bin/python -m mmcore check`
Expected: PASS and `MMCORE CHECK OK` (once all four buckets exist).

---

### Task 9: Dry-run acceptance, first commit, GitHub

**Files:**
- Modify: `R/.context/CHANGELOG.md` (append the dry-run note), `R/buckets/etf/state/history/etf-C0001.json` (the demo cycle, closed), `R/buckets/etf/evaluation/LEDGER.md` (two demo entries), `R/buckets/etf/evaluation/trials.jsonl` (one demo row)

**Interfaces:**
- Consumes: everything above.

- [ ] **Step 1: Full test run**

Run: `cd R && PYTHONPATH=shared .venv/bin/python -m pytest shared/tests -q`
Expected: all PASS; paste the count.

- [ ] **Step 2: Walk the governor's procedure by hand on `etf`**

Run, in order (set `MM_SKIP_GIT=1 MM_SKIP_TRIPWIRE=0`): `mmcore preflight --bucket etf` → `OK`; `mmcore families next --bucket etf` → prints `creation-redemption`; `mmcore cycle open --bucket etf --question "dry run" --family arbitrage --sublane creation-redemption --job deadbeef` → `OK etf-C0001`; `mmcore budget --bucket etf --jobs-today 0 --jobs-week 0 --active-cycles 1` → `ALLOW`; `mmcore budget --bucket etf --jobs-today 4 --jobs-week 0 --active-cycles 1` → `DENY max_stage_jobs_per_day` exit 2; `mmcore trials append --bucket etf --family arbitrage --sublane creation-redemption --params-hash dry --verdict registered --note "dry run" --cycle etf-C0001`; `mmcore ledger append --bucket etf --kind AUDIT --cycle etf-C0001 --job deadbeef --body-file <(echo "dry run of the governor procedure")` → `B-0001`; `mmcore families saturate --bucket etf --family arbitrage --sublane creation-redemption --ids B-0001 --reason x` → exit 2 (needs two ids) and the row unchanged; `mmcore cycle advance --bucket etf --to research --job deadbeef`; `mmcore cycle close --bucket etf --outcome not_actionable --job deadbeef` → exit 2 (illegal from research); `mmcore cycle advance --bucket etf --to bridge --job deadbeef`; `mmcore cycle close --bucket etf --outcome not_actionable --job deadbeef` → `OK history/etf-C0001.json`; `mmcore ledger append --bucket etf --kind LESSON …` → `B-0002`; `mmcore ledger audit --all` → no findings; `mmcore report weekly --saturday 2026-10-24` → markdown with seven sections and four rows; `mmcore check` → `OK`.
Expected: each verdict as listed. Paste the transcript into the task report and summarise it in `.context/CHANGELOG.md`.

- [ ] **Step 3: Commit and create the GitHub repo**

Run: `cd R && git add -A && git commit -q -m "feat: MoneyMachine Company bootstrap — constitution, mmcore, adapters, four buckets" -m "Spec: ai-server docs/superpowers/specs/2026-10-21-moneymachine-company-design.md" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" && gh repo create alfredbot-ai-butler/moneymachine --private --source=. --remote=origin --push && git remote -v && git log --oneline -1`
Expected: the remote `origin` points at `https://github.com/alfredbot-ai-butler/moneymachine.git`; push succeeds.

---

### Task 10: The nine skills (four parallel sub-tasks)

**Files:**
- Create: `W/skills/mm-ceo/SKILL.md`, `W/skills/mm-resume/SKILL.md`, `W/skills/mm-report/SKILL.md` (10a); `W/skills/mm-govern/SKILL.md` (10b); `W/skills/mm-research/SKILL.md`, `W/skills/mm-bridge/SKILL.md` (10c); `W/skills/mm-architect/SKILL.md`, `W/skills/mm-engineer/SKILL.md`, `W/skills/mm-execute/SKILL.md` (10d)
- Test: `W/tests/test_mm_skills.py` (Task 11), `W/scripts/lint_docs.py`

**Interfaces:**
- Consumes: §7 table, §6.4, §8.1, §8.6, the handbooks of Task 7 (read them from `~/Documents/repos/moneymachine/company/officers/`), the CLI of Task 6.
- Produces: the nine job kinds the schedules and dispatches name.

Frontmatter, exactly (one block per skill; `description` is one line, ≤ 400 chars, ends with "Dispatch for the <row> schedule/job_kind" for scheduled skills or "Dispatch-driven, not scheduled" for the others):

```yaml
# mm-ceo
name: mm-ceo
description: "MoneyMachine CEO (Sat 17:00 UTC) — fetch origin, read every bucket's committed state/grades/ledgers, liveness (psql over mm-* jobs + schedule_adherence.json) and spend, decide which buckets run this week, dispatch <= max_governors_per_ceo_run mm-govern jobs; read-only + dispatch, writes nothing; final text = the directive the reporter records. Dispatch for the mm-ceo-weekly schedule/job_kind."
model: claude-opus-5
effort: high
escalation:
  on_failure:
    model: claude-opus-5
    effort: xhigh
permission_mode: acceptEdits
required_tools: [Read, Glob, Grep, Bash]
max_turns: 40
isolation: workspace
role: manager
division: moneymachine
privilege_class: read-only
subagents: [gap-auditor]
context_files: [".context/org/ORG.md"]
tags: [moneymachine, management, scheduled-capable, needs-dispatch-mcp]
```
```yaml
# mm-govern
name: mm-govern
description: "MoneyMachine bucket governor — frozen evaluator for ONE bucket: grade the last cycle from artifacts (independent DSR recompute), rewrite BACKLOG, open the next cycle, dispatch exactly one stage within caps, file [system] items / DECISION-REQUESTs; mode=apply-system applies an owner-approved item to handbooks/BACKLOG only. Dispatch-driven (by mm-ceo), not scheduled."
model: claude-opus-5
effort: high
escalation:
  on_failure:
    model: claude-opus-5
    effort: xhigh
permission_mode: bypassPermissions
required_tools: [Read, Write, Edit, Bash, Glob, Grep]
max_turns: 60
isolation: workspace
role: governor
division: moneymachine
privilege_class: guarded-writer
tags: [moneymachine, evaluation, needs-dispatch-mcp]
```
```yaml
# mm-research / mm-bridge (identical except name/description)
model: claude-opus-5
effort: high
escalation: {on_failure: {model: claude-opus-5, effort: xhigh}}   # write in block form
permission_mode: bypassPermissions
required_tools: [Read, Write, Edit, Bash, Glob, Grep, WebSearch, WebFetch]
max_turns: 80
isolation: workspace
role: worker
division: moneymachine
privilege_class: guarded-writer
tags: [moneymachine, research, needs-dispatch-mcp]
```
```yaml
# mm-architect: as research but required_tools [Read, Write, Edit, Bash, Glob, Grep], max_turns 50
# mm-engineer:
model: claude-opus-4-8
effort: high
escalation: {on_failure: {model: claude-opus-5, effort: xhigh}}   # block form
permission_mode: bypassPermissions
required_tools: [Read, Write, Edit, Bash, Glob, Grep]
max_turns: 100
isolation: workspace
subagents: [code-review]
post_review:
  trigger: always
role: worker
division: moneymachine
privilege_class: guarded-writer
tags: [moneymachine, engineering, needs-dispatch-mcp]
# mm-execute:
model: claude-sonnet-4-6
effort: medium
escalation: {on_failure: {model: claude-opus-4-8, effort: high}}  # block form
permission_mode: bypassPermissions
required_tools: [Read, Write, Bash, Glob, Grep]
max_turns: 40
isolation: workspace
role: worker
division: moneymachine
privilege_class: guarded-writer
tags: [moneymachine, execution]
# mm-resume:
model: claude-sonnet-4-6
effort: low
escalation: {on_failure: {model: claude-sonnet-4-6, effort: medium}}  # block form
permission_mode: acceptEdits
required_tools: [Read, Glob, Grep, Bash]
max_turns: 25
isolation: workspace
role: worker
division: moneymachine
privilege_class: read-only
tags: [moneymachine, evaluation, scheduled-capable, needs-dispatch-mcp]
# mm-report:
model: claude-opus-5
effort: medium
escalation: {on_failure: {model: claude-opus-5, effort: high}}  # block form
permission_mode: bypassPermissions
required_tools: [Read, Write, Edit, Bash, Glob, Grep]
max_turns: 40
isolation: workspace
role: worker
division: moneymachine
privilege_class: guarded-writer
tags: [moneymachine, reporting, scheduled-capable]
```

Body sections for every skill (in this order): `# <name> — <one line>`; `## Inputs` (the §8.1 grammar lines this skill accepts, the required keys, the hard-stop rule, "the prefix is optional — Telegram strips flags"); `## Procedure` numbered: 0 sync (§6.4 step 0 — writers `git pull --ff-only origin main`; read-only skills `git fetch origin` + `git show origin/main:<path>`), 1 interpreter + timer (`python3.12 -m venv .venv && .venv/bin/pip install -q pytest pyyaml`; `date +%s > /tmp/mm-stage-start-<job-id8>`), 2 preflight (`PYTHONPATH=shared .venv/bin/python -m mmcore preflight --bucket <b>` or `--read-only`), 3 read the handbook `company/officers/<role>.md` then `buckets/<b>/officers/<role>.md`, 4–N the stage's own duties (from the handbook, summarised), then the chain mechanics (§6.4 steps 2–5 verbatim with the timeout table — omitted for `mm-execute`/`mm-report`, which dispatch nothing); `## Write surface` (exact paths; the CEO and resumer: "none — read-only + dispatch"); `## Forbidden` (always includes the verbatim dispatch sentence, "never edit sealed cards, past ledger entries, config/*.yaml, tripwires, LOOP.md, PROTOCOL.md, any SKILL.md", and for the CEO "the project write-back directive does not apply: read-only + dispatch; mm-report is the writer"); `## Close-out` (§8.6; "when task-linked, end with `TASK_COMPLETE: <outcome>`" — mandatory wording for `mm-report` and `mm-govern`); `## Gotchas (living section — append when you learn something)` seeded with ≥3 entries each: payload never in the prompt; `python3` is 3.9; max_turns exhaustion = completed + workspace deleted; the dev clone can lag origin; psql `-c` does not interpolate `-v` (pipe SQL via stdin).

Skill-specific body pins: `mm-ceo` — the psql queries (last 7 days of `mm-%` jobs with status + `resolved_skill`; `job_completed` usage via `volumes/audit_log/<id>*.jsonl` grep), the rotation default, "dispatch ≤ `max_governors_per_ceo_run` governors, description `mm-govern: bucket=<b> mode=weekly — <focus>`, payload `{"project_slug":"moneymachine","session_timeout_seconds":3600}`", the `DECISION:`/`ASK-OWNER:` final-text lines. `mm-resume` — `git show origin/main:buckets/<b>/state/cycle.json` for each bucket; stale rule (> 6 h, non-terminal); double-dispatch guard `psql assistant -tAc "SELECT count(*) FROM jobs WHERE kind='mm-<stage>' AND description LIKE '%cycle=<id>%' AND status IN ('queued','running')"`; cap check via the two §6.4 queries + `mmcore budget`; re-dispatch the SAME stage with the §6.4 timeout. `mm-report` — modes `weekly` and `latest`; find the CEO job: `psql assistant -tAc "SELECT id, status FROM jobs WHERE kind='mm-ceo' ORDER BY created_at DESC LIMIT 1"` then `cat "$SERVER_ROOT/volumes/audit_log/<id>.summary.md"` (`SERVER_ROOT` = `~/Library/Application Support/ai-server`); `C-####` entries from `DECISION:` lines; the memo from `mmcore report weekly --saturday <date>` filled in; monthly on the first Saturday of a month; never dispatches. `mm-engineer` — the 70-minute timer, the validation report, "dispatch `mm-execute` only on validation PASS; on REJECT close the cycle `rejected` and write the LESSON"; the `REVIEW: APPROVED — …` line. `mm-execute` — run `projects/<name>/run.py --date <today>` via `.venv/bin/python`, exit codes, `mmcore shadow mark`, the XR template, "a handled HALT is not a job failure".

- [ ] **Step 1: Write the SKILL.md files** per the pins (read the three alpha skills and `atlas-cio` for voice; keep each body ≥ 40 lines).

- [ ] **Step 2: Lint**

Run: `cd $W && $V scripts/lint_docs.py 2>&1 | tail -5`
Expected: `All clean!` once Task 13's registry/charter rows exist (until then the registry and charter checks name the new skills — state it).

---

### Task 11: `tests/test_mm_skills.py`

**Files:**
- Create: `W/tests/test_mm_skills.py`

**Interfaces:**
- Consumes: the nine `W/skills/mm-*/SKILL.md`.

- [ ] **Step 1: Write the test** (parse frontmatter with `yaml.safe_load` of the `---` block; paths relative to `Path(__file__).resolve().parents[1]`):
```python
MM = sorted(p.parent.name for p in (ROOT / "skills").glob("mm-*/SKILL.md"))
DISPATCH_SENTENCE = "Dispatch only kinds matching `mm-*` with `payload.project_slug` = `moneymachine`. Any other kind — `server-patch`, `new-skill`, `atlas-*`, anything — is a DECISION-REQUEST ledger entry, never a dispatch."
PINNED_SUBCOMMANDS = {"preflight","budget","cycle","ledger","trials","families","shadow","report","new-bucket","check"}
STAGE_KINDS = "('mm-research','mm-bridge','mm-architect','mm-engineer','mm-execute')"
def test_nine_skills_exist(): assert MM == ["mm-architect","mm-bridge","mm-ceo","mm-engineer","mm-execute","mm-govern","mm-report","mm-research","mm-resume"]
def test_every_body_has_dispatch_sentence(): ...
def test_post_review_is_mapping_when_present(): ...        # isinstance(fm["post_review"], dict) and "trigger" in it
def test_dispatchers_have_needs_dispatch_mcp(): ...        # bodies containing "enqueue_job" ⇒ tag present; mm-execute/mm-report have no enqueue_job
def test_bash_holders_are_workspace_isolated(): ...
def test_ceo_and_resume_are_read_only_acceptEdits(): ...
def test_division_and_project_slug(): ...                   # division == "moneymachine"; every body contains '"project_slug":"moneymachine"' or "project_slug=moneymachine"
def test_mmcore_subcommands_are_pinned(): ...               # re.findall(r"-m mmcore (\S+)") ⊆ PINNED_SUBCOMMANDS
def test_budget_query_lists_stage_kinds_only(): ...         # every body containing "FROM jobs" and "mmcore budget" contains STAGE_KINDS and not "kind LIKE 'mm-%'" in the budget query lines
def test_report_and_govern_bodies_end_with_task_complete_rule(): ...  # "TASK_COMPLETE:" in mm-report and mm-govern bodies
def test_no_skill_named_redeploy(): ...
def test_models_are_in_gateway_alias_table(): ...           # import src.gateway.telegram_bot._MODEL_ALIASES values (guard import errors → skip)
```
Run: `cd $W && SERVER_ROOT="$PWD" $V -m pytest tests/test_mm_skills.py -q`
Expected: PASS once Task 10 is complete (RED before).

---

### Task 12: Division charter, ORG index, roster edits, Gotcha appends

**Files:**
- Create: `W/.context/org/divisions/moneymachine/CHARTER.md`
- Modify: `W/.context/org/ORG.md` (Division index: one row after the Atlas row), `W/.context/org/divisions/delivery/CHARTER.md` (the one phrase), `W/skills/system-manager/SKILL.md` (the `IN (...)` list gains `'mm-ceo'`), `W/skills/delivery-ops-reconciler/SKILL.md` (Gotchas append), `W/skills/new-project/SKILL.md` (Gotchas append)

**Interfaces:**
- Consumes: Task 10 frontmatter (Role/Privilege must match character-for-character).

- [ ] **Step 1: Write the charter.** First lines:
```
# Charter — MoneyMachine division

**Manager:** `mm-ceo`
**Charter (goal):** run the MoneyMachine Company — four domain buckets (etf, longterm, shortterm, crypto) with one shared officer hierarchy … reports only; INV-22: no order path. Project repo `~/Documents/repos/moneymachine` (GitHub-canonical `alfredbot-ai-butler/moneymachine`).
```
Then `## Roster` with the header `| Agent | Role | Privilege | Purpose |` and exactly nine rows: `mm-ceo | manager | read-only`, `mm-govern | governor | guarded-writer`, `mm-research | worker | guarded-writer`, `mm-bridge | worker | guarded-writer`, `mm-architect | worker | guarded-writer`, `mm-engineer | worker | guarded-writer`, `mm-execute | worker | guarded-writer`, `mm-resume | worker | read-only`, `mm-report | worker | guarded-writer` — Purpose cells from §4.2 with the cadence in parentheses. No other table in the file may have a backticked first cell. Then `## Standards` (Rule 1, deterministic spine, one writer per artifact, caps owner-owned, LOOP.md §7 front door, three-layer switch), `## Cadence` (the three rows), `## Feedback / reports` (final text → `volumes/audit_log/<id>.summary.md`, read by `system-manager`; `reports/weekly/*.md` in the repo).

- [ ] **Step 2: ORG.md row** after line `| Atlas | \`atlas-manager\` | … | weekly |`: `| MoneyMachine | \`mm-ceo\` | [moneymachine](divisions/moneymachine/CHARTER.md) | weekly |`.

- [ ] **Step 3: Delivery charter phrase** `(atlas is the only one today)` → `(atlas and moneymachine today)`.

- [ ] **Step 4: system-manager roster** — add `'mm-ceo'` inside the `resolved_skill IN (...)` list; nothing else in that file changes.

- [ ] **Step 5: Gotcha appends** (one bullet each, in the existing `## Gotchas` section, atlas-style `- **title**: …`): reconciler — "A manifest with `delivery.deployable: false` and no `port` whose PROJECTS_REGISTRY row says not hosted (e.g. `moneymachine`) is a runner-scoping manifest, not hosted-not-registered drift — never route it to `new-project` register-only"; new-project — "Register-only mode: STOP if `delivery.deployable` is false or the registry row says not hosted (`moneymachine`) — registering would publish the directory".

- [ ] **Step 6: Lint**

Run: `cd $W && $V scripts/lint_docs.py 2>&1 | grep -E "org_charters|role_privileges|skills_registry" `
Expected: `[PASS] org_charters`, `[PASS] role_privileges` (skills_registry PASS after Task 13).

---

### Task 13: Registries, schedules, docs index

**Files:**
- Modify: `W/.context/SKILLS_REGISTRY.md` (9 rows appended after the last Installed row, before `## Deferred`), `W/.context/PROJECTS_REGISTRY.md` (row after the `ideas` row, above the AUTOGENERATED markers; a paragraph after the `ideas` paragraph; a row in the Delivery-topology table), `W/scripts/seed-schedules.sh` (block before `echo "Schedules seeded."`), `W/.context/INDEX.md` (section at EOF), `W/docs/README.md` (two rows at the end of the `## What's in here` table)

- [ ] **Step 1: SKILLS_REGISTRY rows** — format `| \`mm-ceo\` | Opus 5 / high (→ xhigh; workspace; read-only + dispatch, INV-20) | MoneyMachine CEO: weekly allocation across buckets → dispatches ≤2 governors (Sat 17:00 UTC, payload project_slug moneymachine) | — |` and likewise for the other eight (cells minimal; frontmatter is the source of truth).

- [ ] **Step 2: PROJECTS_REGISTRY** — row: `| \`moneymachine\` | static (not hosted — do not register) | (none — runner-scoping manifest only) | — | — | \`github.com/alfredbot-ai-butler/moneymachine\` (canonical, private; Mini dev clone \`~/Documents/repos/moneymachine\`; prod \`projects/moneymachine\` pull-only, read for manifest.yml only) | — |`. Paragraph: "`moneymachine` is the MoneyMachine Company … It carries a `manifest.yml` ONLY so the runner can scope jobs via `payload.project_slug` (dev-repo topology, `deployable: false`, no port). It is not hosted and must never be registered: no Caddy snippet, no `projects` DB row. Reconciliation must treat it like the content projects, never as hosted-not-registered drift. Nine `mm-*` skills; three schedule rows; spec `docs/superpowers/specs/2026-10-21-moneymachine-company-design.md`." Delivery-topology row: `| \`moneymachine\` | dev-repo (GitHub \`alfredbot-ai-butler/moneymachine\` canonical; Mini dev clone; runtime clone pull-only, manifest-only) | no (deployable: false) | **ACTIVE from creation 2026-10-21** — block live; never deployed, never registered |`.

- [ ] **Step 3: seed-schedules block**
```bash
# ── MoneyMachine Company (spec 2026-10-21; three rows, all workspace-scoped) ──
# CEO Sat 17:00 UTC (free band 15:15–20:09 after advisors-panel 15:00); reporter
# 2.5 h later so a failed CEO is written into the memo; resumer daily 10:30 (clear
# of alpha-governor 09:30, atlas-build 10:00 Tue/Fri, the 11:00 loop block).
upsert 'mm-ceo-weekly'    '0 17 * * 6'  'mm-ceo'    'mm-ceo: weekly MoneyMachine allocation -> fetch origin, read bucket state/grades/liveness/spend, dispatch <=2 mm-govern; read-only + dispatch (skills/mm-ceo)' '{"project_slug":"moneymachine","session_timeout_seconds":3600}'
upsert 'mm-report-weekly' '30 19 * * 6' 'mm-report' 'mm-report: mode=weekly -> record CEO decisions as C-#### entries, write reports/weekly/<Saturday>.md (CEO FAILED is a headline, not a skip), monthly scoreboard on the first Saturday; never dispatches (skills/mm-report)' '{"project_slug":"moneymachine","session_timeout_seconds":1800}'
upsert 'mm-resume-daily'  '30 10 * * *' 'mm-resume' 'mm-resume: daily heartbeat -> git show origin/main state, re-dispatch stale (>6h) or cap-stalled stages within caps, double-dispatch guarded; read-only + dispatch (skills/mm-resume)' '{"project_slug":"moneymachine","session_timeout_seconds":1200}'
```

- [ ] **Step 4: INDEX.md section** `## Additions 2026-10-21 (MoneyMachine Company — bucketed self-running agent company; BUILT, armed phase 0)` with rows: understand the company (spec §0–§4, repo `~/Documents/repos/moneymachine`, `company/{COMPANY,LOOP,PROTOCOL,MM_AUTHORITY}.md`); work on the skills (`skills/mm-*/SKILL.md`, `tests/test_mm_skills.py`, `.context/org/divisions/moneymachine/CHARTER.md`); operate it (`docs/OWNER.md` in the repo, the three schedule rows, kill switch); build it task-by-task (the plan).

- [ ] **Step 5: docs/README.md rows** for the spec and the plan.

- [ ] **Step 6: Lint + contract tests**

Run: `cd $W && $V scripts/lint_docs.py 2>&1 | tail -3 && SERVER_ROOT="$PWD" $V -m pytest tests/test_doc_lint.py tests/test_skill_contracts.py tests/test_mm_skills.py -q`
Expected: `All clean!`; all PASS.

---

### Task 14: Gates, review, landing (orchestrator)

- [ ] **Step 0: Preconditions — Task 9 is done and origin/main is merged in**

Run: `gh repo view alfredbot-ai-butler/moneymachine --json name -q .name && git -C ~/Documents/repos/moneymachine rev-parse --verify origin/main && cd $W && git fetch origin && git merge --no-edit origin/main; git diff --name-only --diff-filter=U`
Expected: `moneymachine`; a sha; no unmerged paths (if `.context/INDEX.md` conflicts because both branches appended a 2026-10-21 section at EOF, keep BOTH sections — the earlier one first — and commit the merge). STOP if the GitHub repo or `origin/main` of the project repo does not resolve: landing the schedule rows before the project repo exists would run the first jobs unscoped.

- [ ] **Step 1: Protected-path check**

Run: `cd $W && git add -A && git diff --cached --name-only | grep -E '^(\.context/PROTOCOL\.md|MISSION\.md|src/runner/guards\.py|scripts/lint_docs\.py|skills/(server-patch|server-deploy|new-skill)/SKILL\.md|\.env)' ; echo "exit=$?"`
Expected: no lines; `exit=1`.

- [ ] **Step 2: In-flight-branch overlap check**

Run: `cd $W && git diff --cached --name-only | grep -E '^(src/|\.context/modules/|\.context/SYSTEM\.md|skills/README\.md|skills/TEMPLATE\.md|tests/test_skill_contracts\.py|docs/TROUBLESHOOTING\.md|models\.yml)' ; echo "exit=$?"`
Expected: no lines; `exit=1`.

- [ ] **Step 3: Full gates**

Run: `cd $W && $V scripts/lint_docs.py 2>&1 | tail -2 && SERVER_ROOT="$PWD" $V -m pytest tests/test_doc_lint.py tests/test_skill_contracts.py tests/test_mm_skills.py -q && $V -m pytest -q 2>&1 | tail -3`
Expected: `All clean!`; the three files PASS; full suite PASS (baseline 1489 + the new tests).

- [ ] **Step 4: Secrets grep**

Run: `cd $W && git diff --cached | grep -iE 'api[_-]?key|token|secret|password' | grep -vE 'FINNHUB_TOKEN|quote token|no credential|never holds|API-Sign|api_secret|apiKey|ALPACA_|CB-ACCESS|OK-ACCESS|Authorization' ; echo "exit=$?"`
Expected: `exit=1` (only the tripwire vocabulary and documented mentions).

- [ ] **Step 5: Code-review subagent LGTM** on `git diff origin/main` (both repos' diffs summarised; the ai-server diff in full). Record the verdict in the commit body.

- [ ] **Step 6: Commit on the worktree branch**

```bash
cd $W && git commit -q -m "feat(moneymachine): MoneyMachine Company — division, nine mm-* skills, schedules, registries, spec + plan" \
  -m "Spec: docs/superpowers/specs/2026-10-21-moneymachine-company-design.md" \
  -m "Reviewed-By: code-review subagent (LGTM, job/session <id>)" \
  -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

- [ ] **Step 7: Sync and push to `origin main` from the worktree**

Run: `cd $W && git fetch origin && git merge origin/main && $V scripts/lint_docs.py | tail -1 && git push origin moneymachine/bootstrap:main && git log --oneline -1 origin/main`
Expected: lint `All clean!`; push accepted; `origin/main` at the new sha. On rejection: `git merge origin/main` again, re-run Step 3, retry ONCE; still failing → stop and report `git log --oneline origin/main..HEAD` and the reverse.

- [ ] **Step 8: Owner notification** — the final message (§14.2 contents) including the provisioning step and the note that the main checkout's local `main` holds an unpushed stray commit (71bf9a9, a 2-line pickem-chart EVAL.md edit) that this landing did not touch.

---

### Task 15: Provisioning (after the autopilot deploy is green)

- [ ] **Step 1: Wait for the deploy**

Run (poll, read-only): `psql assistant -c "select kind, status, created_at from jobs where kind in ('deploy-director','server-deploy','deploy_director','server_deploy') order by created_at desc limit 4"` and `psql assistant -c "select name, cron_expression, paused, next_run_at from schedules where name like 'mm-%' order by name"`
Expected: a completed deploy after the push; three `mm-*` rows, unpaused, `next_run_at` at their next slots.

- [ ] **Step 2: Create the prod runtime clone**

Run: `SRV="$HOME/Library/Application Support/ai-server" && git clone -q https://github.com/alfredbot-ai-butler/moneymachine "$SRV/projects/moneymachine" && ls "$SRV/projects/moneymachine/manifest.yml" && cd "$SRV" && pipenv run python -c 'from pathlib import Path; from src.registry.manifest import load; print(load(Path("projects/moneymachine/manifest.yml")).delivery)'`
Expected: the manifest path; `Delivery(topology='dev-repo', … deployable=False …)`.

- [ ] **Step 3: Prod lint stays green with the clone present**

Run: `cd "$SRV" && pipenv run python scripts/lint_docs.py | tail -1`
Expected: `All clean!` (the deployed registry row covers the new directory).

- [ ] **Step 4: Record in memory and report** — the first fires (`mm-resume-daily` next 10:30 UTC; `mm-ceo-weekly` Sat 17:00 UTC; `mm-report-weekly` Sat 19:30 UTC), what to watch in the first audit logs (`project_cwd_resolved` → dev clone; `workspace_synced`), and D0–D8.


## Amendment 2026-10-27 — the project became a hosted service

Task 1 Step 4's expected loader output (`moneymachine static dev-repo pull-only False`) is historical: on 2026-10-27 the owner asked for a read-only page, so `manifest.yml` is now `type: service`, port 8794, `healthcheck: /healthz`, `start_command: bash web/run.sh`, `deployable: true` with three gates (mmcore pytest; `web/.venv` + web pytest; `/healthz` 200). The loop's scoping (`payload.project_slug` → the Mini dev clone) is unchanged. Registration in prod (`scripts/register-project.sh moneymachine`) is an owner-run step; the page is fail-closed (403) until the Cloudflare Access application for `moneymachine.chrispiserchia.com` exists.
