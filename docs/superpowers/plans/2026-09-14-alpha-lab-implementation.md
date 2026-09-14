# Alpha-Lab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Owner submits an alpha idea ("alpha: …" via Telegram or a hand-edit to an inbox file); the system autonomously researches, backtests, and adversarially validates it as a chain of dispatched jobs until a GO / NO-GO / BLOCKED-ON-DATA verdict memo lands.

**Architecture:** A new thin atlas vertical `alpha-lab/` (constitution inheriting momentum's PROTOCOL, append-only ledger, per-idea `state.json` as chain-resumption state, small stdlib Python support package) plus three ai-server skills: a read-only+dispatch intake, a workspace-isolated stage worker that advances one idea one stage per job and dispatches the next, and a daily workspace-isolated governor that resumes stalled chains and audits.

**Tech Stack:** Python stdlib + pyyaml (atlas side, owner dependency ceiling), pytest; ai-server SKILL.md skills + `src/runner/router.py` regex rule + `scripts/seed-schedules.sh` row; dispatch MCP (`enqueue_job`).

**Spec:** `docs/superpowers/specs/2026-09-14-alpha-lab-design.md` (read it first; Task 11 appends two dated amendments to it — intake posture and governor posture/cadence — discovered during planning and explained in those tasks).

## Global Constraints

- **Two repos.** Atlas work happens in the dev clone `~/Documents/repos/atlas` (canonical = GitHub `Piserchia/atlas`, branch `master`; `git pull --rebase origin master` BEFORE starting and BEFORE pushing). ai-server work happens in `~/Documents/repos/ai-server` (push `origin main`; `git fetch origin && git merge origin/main` before starting and before pushing).
- **stdlib + pyyaml only** in `alpha-lab/` (owner dependency ceiling; momentum E-0033 precedent). No pandas/numpy/requests, ever.
- **Free data only**; paid-data needs become the BLOCKED-ON-DATA verdict, never a budget request.
- **No order path** (MISSION §M INV-22). Nothing in this plan touches brokerage order code, and the vertical's tripwire test enforces that permanently.
- **Protected paths are NOT touched**: `scripts/lint_docs.py`, `MISSION.md`, `.context/PROTOCOL.md`, `src/runner/guards.py`, auth config, the executor skills. The design was specifically shaped so no task needs them.
- **CHANGELOG discipline**: every ai-server commit touching `src/` needs a `.context/modules/runner/CHANGELOG.md` entry (pre-commit hook enforces); every atlas commit appends to atlas root `CHANGELOG.md`.
- **Job kinds are dashed**: `alpha-intake`, `alpha-research`, `alpha-governor` (runner maps kind→skill 1:1, underscores→dashes).
- **IDs**: ideas are `A-####`; ledger entries are `E-####`; every ledger entry's first body line is `Idea: A-####`.
- Secrets grep before every commit: `git diff | grep -iE 'api[_-]?key|token|secret|password'` must be empty (or hits are clearly not secrets).
- ai-server gates before its push: `pipenv run pytest -q` green + `python scripts/lint_docs.py` all-pass.
- Atlas gates before its push: `cd alpha-lab && .venv/bin/python -m pytest -q` green.

---

### Task 1: Atlas — alpha-lab scaffold + verdicts-only tripwire

**Files:**
- Create: `~/Documents/repos/atlas/alpha-lab/CLAUDE.md`
- Create: `~/Documents/repos/atlas/alpha-lab/config/budget.yaml`
- Create: `~/Documents/repos/atlas/alpha-lab/evaluation/LEDGER.md`
- Create: `~/Documents/repos/atlas/alpha-lab/evaluation/trials.jsonl` (empty file)
- Create: `~/Documents/repos/atlas/alpha-lab/evaluation/INBOX.md`
- Create: `~/Documents/repos/atlas/alpha-lab/conftest.py` (empty — makes pytest put the repo-root of the vertical on sys.path so `import alphalab` works without an editable install; this deliberately dodges the ~/Documents UF_HIDDEN `.pth` venv gotcha)
- Create: `~/Documents/repos/atlas/alpha-lab/pyproject.toml`
- Create: `~/Documents/repos/atlas/alpha-lab/alphalab/__init__.py` (empty)
- Create: `~/Documents/repos/atlas/alpha-lab/ideas/.gitkeep`
- Test: `~/Documents/repos/atlas/alpha-lab/tests/test_verdicts_only.py`

**Interfaces:**
- Consumes: nothing (first task).
- Produces: the directory layout every later task builds in; `config/budget.yaml` keys `max_cycles_per_idea` (int), `max_alpha_jobs_per_day` (int), `max_active_ideas` (int); LEDGER schema `## [E-####] <TYPE> <ISO-ts>` with first body line `Idea: A-####`; INBOX line format `- [ ] <idea text> (owner, YYYY-MM-DD)` / checked `- [x] … -> A-####`.

- [ ] **Step 1: Rebase the atlas dev clone**

```bash
cd ~/Documents/repos/atlas && git pull --rebase origin master
```
If the tree is dirty or mid-rebase, STOP and report (another loop may be mid-write; never clean up someone else's state).

- [ ] **Step 2: Create directories and the venv**

```bash
cd ~/Documents/repos/atlas
mkdir -p alpha-lab/config alpha-lab/evaluation alpha-lab/alphalab alpha-lab/tests alpha-lab/ideas
touch alpha-lab/evaluation/trials.jsonl alpha-lab/alphalab/__init__.py alpha-lab/conftest.py alpha-lab/ideas/.gitkeep
cd alpha-lab && python3.12 -m venv .venv && .venv/bin/pip install -q pytest pyyaml
```

- [ ] **Step 3: Write the failing tripwire test**

`alpha-lab/tests/test_verdicts_only.py`:

```python
"""Mechanical enforcement of alpha-lab/CLAUDE.md rule 1: VERDICTS ONLY.

No order path exists anywhere in this vertical. If this test is ever
edited or deleted, that edit is itself the violation."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Strings that would indicate order-path or live-broker surface. The test
# file itself is excluded from the scan (it must name them to forbid them).
FORBIDDEN_MARKERS = (
    "tradingcore.tradier",
    "://api.alpaca.markets",
    "broker-api.alpaca.markets",
    "trader.executor",
    "swing.executor",
    "submit_order",
    "place_order",
)


def _scannable_files():
    for path in ROOT.rglob("*.py"):
        if ".venv" in path.parts or path.name == "test_verdicts_only.py":
            continue
        yield path


def test_rule_one_present_in_claude_md():
    text = (ROOT / "CLAUDE.md").read_text()
    assert "verdicts only" in text.lower()
    assert "requires the human to edit this file first" in text


def test_no_order_surface_anywhere():
    for path in _scannable_files():
        text = path.read_text()
        for marker in FORBIDDEN_MARKERS:
            assert marker not in text, f"forbidden order-path marker {marker!r} in {path}"


def test_budget_yaml_is_owner_shaped():
    import yaml
    budget = yaml.safe_load((ROOT / "config" / "budget.yaml").read_text())
    assert set(budget) == {"max_cycles_per_idea", "max_alpha_jobs_per_day", "max_active_ideas"}
    assert all(isinstance(v, int) and v > 0 for v in budget.values())
```

- [ ] **Step 4: Run it to verify it fails**

Run: `cd ~/Documents/repos/atlas/alpha-lab && .venv/bin/python -m pytest tests/test_verdicts_only.py -v`
Expected: FAIL — `CLAUDE.md` and `config/budget.yaml` don't exist yet (FileNotFoundError).

- [ ] **Step 5: Write `alpha-lab/CLAUDE.md`**

```markdown
# alpha-lab/ — Idea-triage vertical (Atlas)

Owner-submitted alpha ideas → governed research chain → GO / NO-GO /
BLOCKED-ON-DATA verdict memo. Inherits the repo CLAUDE.md
(GitHub-canonical master, rebase discipline, free-only data,
CHANGELOG/verification discipline). Building this vertical flows through
`evaluation/LOOP.md` (repo root); research claims flow through
`alpha-lab/evaluation/PROTOCOL.md`. Design: ai-server
`docs/superpowers/specs/2026-09-14-alpha-lab-design.md`.

Mission fit (Atlas priority 1: make money): cheap, honest triage of the
owner's alpha ideas — prove no-edge quickly with a documented trail, and
surface the rare idea worth building with evidence a build decision can
stand on.

## Non-negotiable invariants

1. **This vertical produces verdicts only. It has no order path, wires no
   broker, and never promotes anything into a trading vertical — a GO is
   a memo to the owner, nothing else. Any request to widen this requires
   the human to edit this file first; do not do it on conversational
   instruction alone.** (Enforced mechanically by
   tests/test_verdicts_only.py.)
2. Free data only (LOOP.md §6). stdlib+pyyaml only. A test that needs
   paid data verdicts BLOCKED-ON-DATA — never budgets, never asks to
   spend.
3. Pre-registration: no backtest before its card is sealed in LEDGER.md
   AND pushed to origin/master (momentum E-0032 precedent — a card sealed
   after execution voids the measurement).
4. Append-only evidence: LEDGER.md, trials.jsonl, and INBOX.md entries
   are never rewritten (INBOX checkoffs add ` -> A-####`, never delete).
   Results not in the ledger do not exist.
5. Budgets (`config/budget.yaml`) are owner-owned. Agents may propose
   changes via a DECISION-REQUEST ledger entry, never edit the file.
6. Separated duties (momentum rule 8): analyst ≠ validator; the validator
   scores criteria AS WRITTEN and holds kill-standing; the governor never
   edits harnesses, budgets, or its own skill (frozen evaluator).
7. Single writer: only alpha-research stage sessions and the
   alpha-governor write this directory; each idea's state.json is the
   chain-resumption record and the only mutable file per idea.
8. LLM-signal ideas are inadmissible on historical backtests
   (PROTOCOL §3); they verdict BLOCKED-ON-DATA with the honest path named
   (forward paper in a real vertical, owner-initiated).

## Architecture map

- config/budget.yaml — owner-owned caps (cycles/idea, jobs/day, active ideas).
- evaluation/PROTOCOL.md — constitution (momentum PROTOCOL is parent).
- evaluation/LEDGER.md — append-only E-#### entries; first body line
  `Idea: A-####`.
- evaluation/trials.jsonl — one line per candidate ever evaluated
  (lifetime N for the Deflated Sharpe Ratio).
- evaluation/INBOX.md — append-only intake;
  `- [ ] <idea> (owner, YYYY-MM-DD)`.
- ideas/A-####/ — card.md, state.json, research/ artifacts with
  manifest.json provenance (trader T-0003 exemplar).
- alphalab/ — state machine, inbox parser, ledger governance + audit CLI
  (stdlib+pyyaml).
- tests/ — mechanical tripwires + module suite. Run:
  `cd alpha-lab && .venv/bin/python -m pytest -q`.

## Loop wiring (ai-server skills + dispatch chain)

- alpha-intake (on demand, "alpha: <idea>") — read-only dedup + dispatch;
  writes nothing here.
- alpha-research (dispatch-driven chain, one stage per job) — files
  ideas, triages, seals cards, runs backtest cycles, validates, verdicts.
- alpha-governor (daily 09:30 UTC) — resumes stalled chains, drains
  INBOX, budget audit, verdict spot-checks.
```

- [ ] **Step 6: Write `alpha-lab/config/budget.yaml`**

```yaml
# Owner-owned caps. Agents may PROPOSE changes via a DECISION-REQUEST
# ledger entry; they never edit this file (CLAUDE.md rule 5).
#
# max_alpha_jobs_per_day bounds intake + stage jobs combined so the chain
# can never starve the other Atlas loops or the owner's own quota. 6/day
# lets one idea traverse its whole chain in about a day; a cap-stalled
# chain resumes at the next daily governor run.
max_cycles_per_idea: 6
max_alpha_jobs_per_day: 6
max_active_ideas: 3
```

- [ ] **Step 7: Write `alpha-lab/evaluation/LEDGER.md`**

```markdown
# Alpha-lab ledger (append-only)

Schema: `## [E-####] <TYPE> <ISO-8601-timestamp>`
TYPE ∈ {IDEA, HYPOTHESIS, RESULT, VERDICT, DECISION, DECISION-REQUEST,
PROTOCOL-VIOLATION, AUDIT}

Rules (parsed mechanically by `alphalab/governance.py`):
- E-#### ids are strictly increasing, never reused, never edited after
  append — the ordering is the append-only proof.
- Every entry's FIRST body line is `Idea: A-####` (machine association).
- HYPOTHESIS entries carry `Criteria observables:`, `Success criterion:`,
  `Kill criterion:`, `Prior-art check:` blocks (PROTOCOL §2).
- DECISION entries are terminal verdicts and cite their evidence E-ids.

---
```

- [ ] **Step 8: Write `alpha-lab/evaluation/INBOX.md`**

```markdown
# Alpha-lab idea inbox (append-only)

One idea per line, exactly:

    - [ ] <idea text on one line> (owner, YYYY-MM-DD)

The owner may append lines by hand; the Telegram intake path also lands
here (checked, with the assigned id) via the FILE-mode stage worker.
Workers check entries off as `- [x] <text> (owner, <date>) -> A-####`
when the idea is filed — entries are never deleted or reworded. The daily
governor drains unchecked entries oldest-first when capacity allows.

---
```

- [ ] **Step 9: Write `alpha-lab/pyproject.toml`**

```toml
[project]
name = "alphalab"
version = "0.1.0"
description = "Alpha-lab idea-triage vertical support package (stdlib + pyyaml only)"
requires-python = ">=3.11"
dependencies = ["pyyaml"]

[project.optional-dependencies]
dev = ["pytest"]

[tool.setuptools]
packages = ["alphalab"]
```

- [ ] **Step 10: Run the test to verify it passes**

Run: `cd ~/Documents/repos/atlas/alpha-lab && .venv/bin/python -m pytest tests/test_verdicts_only.py -v`
Expected: PASS (3 tests).

- [ ] **Step 11: Commit**

```bash
cd ~/Documents/repos/atlas
git add alpha-lab
git commit -m "feat(alpha-lab): vertical scaffold — CLAUDE.md invariants, owner budget, ledger/inbox formats, verdicts-only tripwire"
```

---

### Task 2: Atlas — PROTOCOL.md (the constitution) + its test

**Files:**
- Create: `~/Documents/repos/atlas/alpha-lab/evaluation/PROTOCOL.md`
- Test: `~/Documents/repos/atlas/alpha-lab/tests/test_protocol.py`

**Interfaces:**
- Consumes: Task 1 layout.
- Produces: the binding research contract every SKILL.md body references; verdict names `GO` / `NO-GO` / `BLOCKED-ON-DATA`; trials.jsonl line schema `{"ts", "idea", "name", "family", "params_hash", "verdict", "note"}`.

- [ ] **Step 1: Write the failing test**

`alpha-lab/tests/test_protocol.py`:

```python
"""PROTOCOL.md must declare its parent and carry the load-bearing clauses.

A doc test, deliberately: the skills quote these exact phrases as binding,
so their presence is a contract, not prose style."""

from pathlib import Path

PROTOCOL = Path(__file__).resolve().parents[1] / "evaluation" / "PROTOCOL.md"

REQUIRED_PHRASES = (
    "momentum/evaluation/PROTOCOL.md",   # parent declaration
    "Criteria observables:",             # §2a discipline
    "Success criterion:",
    "Kill criterion:",
    "Prior-art check:",
    "trials.jsonl",
    "INADMISSIBLE",                      # LLM-signal backtests
    "GO",
    "NO-GO",
    "BLOCKED-ON-DATA",
    "budget death",
    "95th percentile",                   # placebo decision rule
    "Deflated Sharpe",
)


def test_protocol_exists_and_binds():
    text = PROTOCOL.read_text()
    for phrase in REQUIRED_PHRASES:
        assert phrase in text, f"PROTOCOL.md missing load-bearing phrase {phrase!r}"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd ~/Documents/repos/atlas/alpha-lab && .venv/bin/python -m pytest tests/test_protocol.py -v`
Expected: FAIL — FileNotFoundError.

- [ ] **Step 3: Write `alpha-lab/evaluation/PROTOCOL.md`**

```markdown
# Alpha-lab research protocol (constitution)

Alpha-lab-scoped instance of the momentum lab's research governance
(`momentum/evaluation/PROTOCOL.md` is the parent document; where this
file is silent, the parent's rule applies with "momo" read as
"alpha-lab"). Binding on every stage session, human or dispatched.

## 1. Idea lifecycle

`submitted → triaged → carded → backtesting (≤ budget) → validated →
verdict`, recorded in `ideas/A-####/state.json` (schema enforced by
`alphalab/state.py`). Terminal verdicts: **GO**, **NO-GO**,
**BLOCKED-ON-DATA**. Triage may kill same-day (submitted → verdict).
Budget exhaustion is an automatic NO-GO recorded as "budget death".
"We proved it has no edge, cheaply, with a documented trail" is a
success of the process (parent §10).

## 2. Pre-registration

No backtest without a hypothesis CARD in `ideas/A-####/card.md` and a
HYPOTHESIS ledger entry, sealed AND pushed to origin/master before the
backtest stage runs. Every card carries:

- `Criteria observables:` — every success/kill clause names an
  observable computable from run artifacts by someone holding only the
  artifacts and the card (parent §2a; criteria are scored AS WRITTEN;
  the misfire flow is the parent's, verbatim).
- `Success criterion:` / `Kill criterion:` blocks.
- `Prior-art check:` — cite the nearest entries across ALL verticals'
  ledgers and trials registries (momentum, trader, swing, value,
  alpha-lab) and say why this is not a re-mine of a killed or crowded
  idea. An idea already killed elsewhere is a same-day NO-GO citing the
  prior trial.
- Max 2 parameters changed per confirmatory cycle; grids are EXPLORATORY
  and every grid cell counts as a trial.

## 3. Evidence standards

- Backtests: deterministic harness under `ideas/A-####/research/cycle-N/`,
  stdlib+pyyaml only, costs modeled (≥3 bps/side + spread; never
  cost-free), pessimistic fills, walk-forward or purged CV with embargo,
  ≥30 trades per OOS slice for trade-level ideas; stop-inclusive AND
  stop-less variants both reported where stops apply. Data provenance in
  `manifest.json` (source_url, fetch timestamp, sha256, row counts,
  dividend-adjustment note) per the trader T-0003 exemplar.
- Placebo baseline mandatory: random-entry placebo (M ≥ 200); the
  candidate must exceed the placebo distribution's 95th percentile to
  claim the pattern matters (momentum EVALUATION Layer 3).
- Survivorship probe mandatory for any universe-selection idea; yfinance
  fails the survivorship test and may serve only with that caveat stated
  in the card.
- LLM-signal ideas: historical backtests are INADMISSIBLE as evidence
  (parametric look-ahead — the model has memorized the tape). Verdict
  BLOCKED-ON-DATA naming the honest path (forward paper in a target
  vertical, owner-initiated).
- A GO that does not state lifetime N (from trials.jsonl) and the
  Deflated Sharpe Ratio against it is invalid on its face.

## 4. Trial accounting

`evaluation/trials.jsonl` is append-only; one line per candidate variant
ever evaluated — including rejects and every exploratory grid cell:
`{"ts": ..., "idea": "A-####", "name": ..., "family": ...,
"params_hash": ..., "verdict": ..., "note": ...}`. Lines land BEFORE the
cycle's VERDICT entry; "I didn't log the rejects" invalidates the cycle.

## 5. Verdict rules (deterministic)

- Success criterion met, validator confirms the scoring → GO.
- Kill criterion met, validator confirms the scoring → NO-GO.
- cycles_used reaches max_cycles without a confirmed pass → NO-GO
  ("budget death", no validation stage needed — the rule is arithmetic).
- Required data unavailable free (or LLM-signal class) → BLOCKED-ON-DATA.

Verdicts are computed from artifacts as scored by the kill-standing
validator; they are never re-judged by a model after the fact. The
DECISION entry cites its evidence entries by E-id. A GO additionally
names a recommended target vertical (trader / swing / value / momentum)
and a build sketch — and stops there: building is the owner's decision
(atlas evaluation/LOOP.md §6).

## 6. Learning channels (exhaustive)

1. Episodic, append-only: LEDGER.md, trials.jsonl, research/ artifacts.
2. Procedural, gated: skill texts via LOOP.md §7 front door; GOTCHAS
   appends (mechanical only).

No other channel exists. No agent edits a harness after its card seals,
the budgets, gate thresholds, or its own grading skill (the
frozen-evaluator property is the load-bearing control).

## 7. What stays human

Paid data (verdict BLOCKED-ON-DATA instead), building anything from a
GO, `config/budget.yaml` edits, and every ceiling in atlas
`evaluation/LOOP.md` §6.
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd ~/Documents/repos/atlas/alpha-lab && .venv/bin/python -m pytest tests/test_protocol.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/Documents/repos/atlas
git add alpha-lab/evaluation/PROTOCOL.md alpha-lab/tests/test_protocol.py
git commit -m "feat(alpha-lab): research PROTOCOL (momentum parent) + load-bearing-phrase test"
```

---

### Task 3: Atlas — `alphalab/state.py` (idea lifecycle state machine)

**Files:**
- Create: `~/Documents/repos/atlas/alpha-lab/alphalab/state.py`
- Test: `~/Documents/repos/atlas/alpha-lab/tests/test_state_machine.py`

**Interfaces:**
- Consumes: Task 1 layout.
- Produces (used by Tasks 5, 9, 10 and the skill bodies):
  - `STAGES: tuple[str, ...]` = `("submitted", "triaged", "carded", "backtesting", "validated", "verdict")`
  - `VERDICTS: tuple[str, ...]` = `("GO", "NO-GO", "BLOCKED-ON-DATA")`
  - `class StateError(ValueError)`
  - `new_state(idea_id: str, max_cycles: int, now_iso: str, job_id: str) -> dict`
  - `validate_state(d: dict) -> None` (raises `StateError`)
  - `check_transition(current: str, new: str) -> None` (raises `StateError`)
  - `is_terminal(d: dict) -> bool`
  - `load_state(path) -> dict`, `save_state(path, d: dict) -> None`

- [ ] **Step 1: Write the failing tests**

`alpha-lab/tests/test_state_machine.py`:

```python
import json

import pytest

from alphalab import state


def _base(**over):
    d = state.new_state("A-0001", 6, "2026-09-14T12:00:00+00:00", "deadbeef")
    d.update(over)
    return d


def test_new_state_is_valid_and_submitted():
    d = state.new_state("A-0001", 6, "2026-09-14T12:00:00+00:00", "deadbeef")
    state.validate_state(d)
    assert d["stage"] == "submitted"
    assert d["cycles_used"] == 0
    assert d["verdict"] is None


def test_missing_key_rejected():
    d = _base()
    del d["cycles_used"]
    with pytest.raises(state.StateError):
        state.validate_state(d)


def test_unknown_stage_rejected():
    with pytest.raises(state.StateError):
        state.validate_state(_base(stage="pondering"))


def test_illegal_transition_rejected():
    with pytest.raises(state.StateError):
        state.check_transition("submitted", "backtesting")


def test_triage_may_kill_same_day():
    state.check_transition("submitted", "verdict")  # no raise


def test_backtesting_may_repeat():
    state.check_transition("backtesting", "backtesting")  # no raise


def test_terminal_is_terminal():
    with pytest.raises(state.StateError):
        state.check_transition("verdict", "triaged")


def test_terminal_requires_verdict_outcome():
    with pytest.raises(state.StateError):
        state.validate_state(_base(stage="verdict", verdict=None))
    with pytest.raises(state.StateError):
        state.validate_state(_base(stage="verdict", verdict={"outcome": "MAYBE"}))
    state.validate_state(_base(stage="verdict",
                               verdict={"outcome": "NO-GO", "reason": "prior art"}))


def test_nonterminal_must_have_null_verdict():
    with pytest.raises(state.StateError):
        state.validate_state(_base(verdict={"outcome": "GO"}))


def test_cycles_over_budget_rejected():
    with pytest.raises(state.StateError):
        state.validate_state(_base(cycles_used=7))


def test_roundtrip(tmp_path):
    p = tmp_path / "state.json"
    d = _base(stage="triaged")
    state.save_state(p, d)
    assert state.load_state(p) == d
    assert json.loads(p.read_text())["idea_id"] == "A-0001"
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd ~/Documents/repos/atlas/alpha-lab && .venv/bin/python -m pytest tests/test_state_machine.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'alphalab.state'`.

- [ ] **Step 3: Write `alpha-lab/alphalab/state.py`**

```python
"""Idea lifecycle state machine for alpha-lab.

`ideas/A-####/state.json` is the chain-resumption record: any stage
worker (or the governor) picks an idea up cold from it. Terminal ideas
are never advanced again. Schema and transitions here are the single
source of truth the skills and the governor audit against.
"""

from __future__ import annotations

import json
from pathlib import Path

STAGES = ("submitted", "triaged", "carded", "backtesting", "validated", "verdict")
VERDICTS = ("GO", "NO-GO", "BLOCKED-ON-DATA")

# stage -> stages a worker may legally move to next. "verdict" is reachable
# early for triage kills, BLOCKED-ON-DATA at any point, and budget death.
TRANSITIONS = {
    "submitted": ("triaged", "verdict"),
    "triaged": ("carded", "verdict"),
    "carded": ("backtesting", "verdict"),
    "backtesting": ("backtesting", "validated", "verdict"),
    "validated": ("verdict",),
    "verdict": (),
}

REQUIRED_KEYS = (
    "idea_id", "stage", "cycles_used", "max_cycles",
    "last_advanced_at", "last_job_id", "verdict",
)


class StateError(ValueError):
    pass


def new_state(idea_id: str, max_cycles: int, now_iso: str, job_id: str) -> dict:
    return {
        "idea_id": idea_id,
        "stage": "submitted",
        "cycles_used": 0,
        "max_cycles": max_cycles,
        "last_advanced_at": now_iso,
        "last_job_id": job_id,
        "verdict": None,
    }


def validate_state(d: dict) -> None:
    missing = [k for k in REQUIRED_KEYS if k not in d]
    if missing:
        raise StateError(f"state missing keys: {missing}")
    if d["stage"] not in STAGES:
        raise StateError(f"unknown stage {d['stage']!r}")
    if not isinstance(d["cycles_used"], int) or not isinstance(d["max_cycles"], int):
        raise StateError("cycles_used/max_cycles must be ints")
    if d["cycles_used"] > d["max_cycles"]:
        raise StateError(
            f"cycles_used {d['cycles_used']} exceeds max_cycles {d['max_cycles']}")
    if d["stage"] == "verdict":
        outcome = (d["verdict"] or {}).get("outcome")
        if outcome not in VERDICTS:
            raise StateError(f"terminal state needs verdict.outcome in {VERDICTS}")
    elif d["verdict"] is not None:
        raise StateError("non-terminal state must have verdict null")


def check_transition(current: str, new: str) -> None:
    if new not in TRANSITIONS.get(current, ()):
        raise StateError(f"illegal transition {current!r} -> {new!r}")


def is_terminal(d: dict) -> bool:
    return d["stage"] == "verdict"


def load_state(path) -> dict:
    d = json.loads(Path(path).read_text())
    validate_state(d)
    return d


def save_state(path, d: dict) -> None:
    validate_state(d)
    Path(path).write_text(json.dumps(d, indent=2, sort_keys=True) + "\n")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd ~/Documents/repos/atlas/alpha-lab && .venv/bin/python -m pytest tests/test_state_machine.py -v`
Expected: PASS (11 tests).

- [ ] **Step 5: Commit**

```bash
cd ~/Documents/repos/atlas
git add alpha-lab/alphalab/state.py alpha-lab/tests/test_state_machine.py
git commit -m "feat(alpha-lab): idea lifecycle state machine (state.json schema + transitions)"
```

---

### Task 4: Atlas — `alphalab/inbox.py` (INBOX.md parser)

**Files:**
- Create: `~/Documents/repos/atlas/alpha-lab/alphalab/inbox.py`
- Test: `~/Documents/repos/atlas/alpha-lab/tests/test_inbox_format.py`

**Interfaces:**
- Consumes: INBOX line format from Task 1.
- Produces (used by Task 5's CLI and the governor skill body):
  - `class InboxError(ValueError)`
  - `parse_inbox(text: str) -> list[dict]` — each dict `{"done": bool, "text": str, "date": str, "idea_id": str | None}`; non-entry lines (headers, prose, blank, `---`) are skipped; a line starting `- [` that doesn't match the format raises `InboxError`.
  - `unprocessed(entries: list[dict]) -> list[dict]` — unchecked entries, file order preserved.

- [ ] **Step 1: Write the failing tests**

`alpha-lab/tests/test_inbox_format.py`:

```python
import pytest

from alphalab import inbox

SAMPLE = """# Alpha-lab idea inbox (append-only)

Prose explaining the format is skipped by the parser.

---
- [ ] overnight gap fades in small caps (owner, 2026-09-14)
- [x] PEAD drift lasts longer in small caps (owner, 2026-09-13) -> A-0001
- [ ] VIX term structure inversion predicts SPY reversal (owner, 2026-09-14)
"""


def test_parse_entries_and_skips_prose():
    entries = inbox.parse_inbox(SAMPLE)
    assert len(entries) == 3
    assert entries[0] == {"done": False, "date": "2026-09-14", "idea_id": None,
                          "text": "overnight gap fades in small caps"}
    assert entries[1]["done"] is True
    assert entries[1]["idea_id"] == "A-0001"


def test_unprocessed_filters_and_preserves_order():
    todo = inbox.unprocessed(inbox.parse_inbox(SAMPLE))
    assert [e["text"] for e in todo] == [
        "overnight gap fades in small caps",
        "VIX term structure inversion predicts SPY reversal",
    ]


@pytest.mark.parametrize("bad", [
    "- [ ] missing attribution",
    "- [x] checked but no id (owner, 2026-09-13)",   # checked needs -> A-####
    "- [ ] bad date (owner, 14-09-2026)",
    "- [y] bad checkbox (owner, 2026-09-14)",
])
def test_malformed_entry_raises(bad):
    with pytest.raises(inbox.InboxError):
        inbox.parse_inbox(bad)


def test_empty_inbox_is_fine():
    assert inbox.parse_inbox("# header only\n") == []
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd ~/Documents/repos/atlas/alpha-lab && .venv/bin/python -m pytest tests/test_inbox_format.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'alphalab.inbox'`.

- [ ] **Step 3: Write `alpha-lab/alphalab/inbox.py`**

```python
"""INBOX.md parsing.

Entry lines only; everything else (headers, prose, ---) is ignored.
A line that LOOKS like an entry (starts "- [") but doesn't match the
format exactly is an error — silent drops here would silently swallow
an owner's idea. Checked entries must carry their assigned id.
"""

from __future__ import annotations

import re

ENTRY_RE = re.compile(
    r"^- \[(?P<done>[ x])\] "
    r"(?P<text>.+?) "
    r"\(owner, (?P<date>\d{4}-\d{2}-\d{2})\)"
    r"(?: -> (?P<idea_id>A-\d{4}))?$"
)


class InboxError(ValueError):
    pass


def parse_inbox(text: str) -> list[dict]:
    entries = []
    for lineno, line in enumerate(text.splitlines(), 1):
        if not line.startswith("- ["):
            continue
        m = ENTRY_RE.match(line)
        if not m:
            raise InboxError(f"INBOX line {lineno} malformed: {line!r}")
        done = m.group("done") == "x"
        idea_id = m.group("idea_id")
        if done and not idea_id:
            raise InboxError(
                f"INBOX line {lineno} checked without an assigned id: {line!r}")
        entries.append({"done": done, "text": m.group("text"),
                        "date": m.group("date"), "idea_id": idea_id})
    return entries


def unprocessed(entries: list[dict]) -> list[dict]:
    return [e for e in entries if not e["done"]]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd ~/Documents/repos/atlas/alpha-lab && .venv/bin/python -m pytest tests/test_inbox_format.py -v`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
cd ~/Documents/repos/atlas
git add alpha-lab/alphalab/inbox.py alpha-lab/tests/test_inbox_format.py
git commit -m "feat(alpha-lab): INBOX parser (loud on malformed entries)"
```

---

### Task 5: Atlas — `alphalab/governance.py` + `alphalab/cli.py` (ledger parse, budget audit)

**Files:**
- Create: `~/Documents/repos/atlas/alpha-lab/alphalab/governance.py`
- Create: `~/Documents/repos/atlas/alpha-lab/alphalab/cli.py`
- Test: `~/Documents/repos/atlas/alpha-lab/tests/test_budget_accounting.py`

**Interfaces:**
- Consumes: LEDGER schema (Task 1), `alphalab.state` (Task 3).
- Produces (used by the alpha-governor skill body via `.venv/bin/python -m alphalab.cli audit`):
  - `governance.Entry` — namedtuple `(eid: int, etype: str, ts: str, body: str)`
  - `governance.TYPES: frozenset[str]`
  - `governance.parse_ledger(text: str) -> tuple[list[Entry], list[str]]` — entries plus structural violations (out-of-order/duplicate ids, unknown types, missing `Idea:` line).
  - `governance.idea_of(entry: Entry) -> str | None`
  - `governance.cycles_from_ledger(entries: list[Entry], idea_id: str) -> int` — count of RESULT entries for the idea.
  - `governance.audit(ledger_text: str, states: list[dict]) -> list[str]` — all violations: structural + per-idea `cycles_used` vs ledger RESULT count + card-before-result ordering.
  - `cli.main(argv: list[str] | None = None) -> int` — `audit` subcommand; prints violations one per line, returns 1 if any, else prints `audit clean` and returns 0.

- [ ] **Step 1: Write the failing tests**

`alpha-lab/tests/test_budget_accounting.py`:

```python
from alphalab import cli, governance, state

LEDGER = """# Alpha-lab ledger (append-only)

Schema: `## [E-####] <TYPE> <ISO-8601-timestamp>`

---

## [E-0001] IDEA 2026-09-14T12:00:00+00:00
Idea: A-0001
Small-cap PEAD drift.

## [E-0002] HYPOTHESIS 2026-09-14T13:00:00+00:00
Idea: A-0001
Criteria observables: ...

## [E-0003] RESULT 2026-09-14T15:00:00+00:00
Idea: A-0001
Cycle 1 numbers, placebo p95 not exceeded.
"""


def _state(**over):
    d = state.new_state("A-0001", 6, "2026-09-14T12:00:00+00:00", "j1")
    d.update(over)
    return d


def test_parse_ledger_clean():
    entries, violations = governance.parse_ledger(LEDGER)
    assert violations == []
    assert [e.eid for e in entries] == [1, 2, 3]
    assert entries[1].etype == "HYPOTHESIS"
    assert governance.idea_of(entries[0]) == "A-0001"


def test_out_of_order_and_duplicate_ids_flagged():
    bad = LEDGER + "\n## [E-0003] AUDIT 2026-09-15T09:00:00+00:00\nIdea: A-0001\ndup\n"
    _, violations = governance.parse_ledger(bad)
    assert any("E-0003" in v for v in violations)


def test_unknown_type_flagged():
    bad = LEDGER + "\n## [E-0004] VIBES 2026-09-15T09:00:00+00:00\nIdea: A-0001\nx\n"
    _, violations = governance.parse_ledger(bad)
    assert any("VIBES" in v for v in violations)


def test_missing_idea_line_flagged():
    bad = LEDGER + "\n## [E-0004] AUDIT 2026-09-15T09:00:00+00:00\nno idea line\n"
    _, violations = governance.parse_ledger(bad)
    assert any("Idea:" in v for v in violations)


def test_cycle_count_and_budget_match():
    entries, _ = governance.parse_ledger(LEDGER)
    assert governance.cycles_from_ledger(entries, "A-0001") == 1
    ok = governance.audit(LEDGER, [_state(stage="backtesting", cycles_used=1)])
    assert ok == []
    bad = governance.audit(LEDGER, [_state(stage="backtesting", cycles_used=2)])
    assert any("cycles_used" in v for v in bad)


def test_result_before_card_flagged():
    no_card = LEDGER.replace("HYPOTHESIS", "AUDIT")
    bad = governance.audit(no_card, [_state(stage="backtesting", cycles_used=1)])
    assert any("before" in v.lower() or "card" in v.lower() for v in bad)


def test_cli_audit_exit_codes(tmp_path, capsys):
    root = tmp_path
    (root / "evaluation").mkdir()
    (root / "evaluation" / "LEDGER.md").write_text(LEDGER)
    idea = root / "ideas" / "A-0001"
    idea.mkdir(parents=True)
    state.save_state(idea / "state.json", _state(stage="backtesting", cycles_used=1))
    assert cli.main(["audit", "--root", str(root)]) == 0
    assert "audit clean" in capsys.readouterr().out
    state.save_state(idea / "state.json", _state(stage="backtesting", cycles_used=0))
    assert cli.main(["audit", "--root", str(root)]) == 1
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd ~/Documents/repos/atlas/alpha-lab && .venv/bin/python -m pytest tests/test_budget_accounting.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'alphalab.governance'`.

- [ ] **Step 3: Write `alpha-lab/alphalab/governance.py`**

```python
"""Ledger parsing + budget audit (momo/governance.py discipline, minimal).

The ledger is append-only; strictly-increasing unique E-ids are the
mechanical proof. Every entry's first body line associates it to an idea
(`Idea: A-####`). The audit cross-checks each idea's state.json
cycles_used against the ledger's RESULT count and enforces
card-before-result ordering (momentum E-0032)."""

from __future__ import annotations

import re
from collections import namedtuple

ENTRY_RE = re.compile(r"^## \[E-(\d{4})\] ([A-Z-]+) (\S+)$", re.MULTILINE)
IDEA_RE = re.compile(r"^Idea: (A-\d{4})$", re.MULTILINE)

TYPES = frozenset({
    "IDEA", "HYPOTHESIS", "RESULT", "VERDICT", "DECISION",
    "DECISION-REQUEST", "PROTOCOL-VIOLATION", "AUDIT",
})

Entry = namedtuple("Entry", "eid etype ts body")


def parse_ledger(text: str) -> tuple[list[Entry], list[str]]:
    violations: list[str] = []
    matches = list(ENTRY_RE.finditer(text))
    entries: list[Entry] = []
    seen: set[int] = set()
    last = 0
    for i, m in enumerate(matches):
        eid, etype, ts = int(m.group(1)), m.group(2), m.group(3)
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[m.end():end].strip()
        entries.append(Entry(eid, etype, ts, body))
        if eid in seen or eid <= last:
            violations.append(
                f"E-{eid:04d}: id out of order or duplicate (append-only proof broken)")
        seen.add(eid)
        last = max(last, eid)
        if etype not in TYPES:
            violations.append(f"E-{eid:04d}: unknown type {etype}")
        if not IDEA_RE.search(body.split("\n\n")[0] if body else ""):
            violations.append(f"E-{eid:04d}: first body line is not 'Idea: A-####'")
    return entries, violations


def idea_of(entry: Entry) -> str | None:
    m = IDEA_RE.search(entry.body)
    return m.group(1) if m else None


def cycles_from_ledger(entries: list[Entry], idea_id: str) -> int:
    return sum(1 for e in entries
               if e.etype == "RESULT" and idea_of(e) == idea_id)


def audit(ledger_text: str, states: list[dict]) -> list[str]:
    entries, violations = parse_ledger(ledger_text)
    for st in states:
        idea = st["idea_id"]
        ledger_cycles = cycles_from_ledger(entries, idea)
        if ledger_cycles != st["cycles_used"]:
            violations.append(
                f"{idea}: state.json cycles_used={st['cycles_used']} but "
                f"ledger has {ledger_cycles} RESULT entries")
        result_ids = [e.eid for e in entries
                      if e.etype == "RESULT" and idea_of(e) == idea]
        card_ids = [e.eid for e in entries
                    if e.etype == "HYPOTHESIS" and idea_of(e) == idea]
        if result_ids and (not card_ids or min(card_ids) > min(result_ids)):
            violations.append(
                f"{idea}: RESULT E-{min(result_ids):04d} has no earlier "
                f"HYPOTHESIS card (sealed-before-run violated, E-0032 class)")
    return violations
```

- [ ] **Step 4: Write `alpha-lab/alphalab/cli.py`**

```python
"""`python -m alphalab.cli audit [--root DIR]` — the governor's audit gate.

Prints violations one per line; exit 1 if any. Read-only."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from alphalab import governance, state


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="alphalab")
    sub = parser.add_subparsers(dest="cmd", required=True)
    audit_p = sub.add_parser("audit", help="ledger + budget accounting audit")
    audit_p.add_argument("--root", default=str(Path(__file__).resolve().parents[1]),
                         help="alpha-lab vertical root (default: package parent)")
    args = parser.parse_args(argv)

    root = Path(args.root)
    ledger_text = (root / "evaluation" / "LEDGER.md").read_text()
    states = []
    for state_path in sorted(root.glob("ideas/*/state.json")):
        states.append(state.load_state(state_path))

    violations = governance.audit(ledger_text, states)
    for v in violations:
        print(v)
    if violations:
        return 1
    print("audit clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd ~/Documents/repos/atlas/alpha-lab && .venv/bin/python -m pytest tests/test_budget_accounting.py -v`
Expected: PASS (7 tests).

- [ ] **Step 6: Run the whole vertical suite**

Run: `cd ~/Documents/repos/atlas/alpha-lab && .venv/bin/python -m pytest -q`
Expected: all green (Tasks 1–5 suites).

- [ ] **Step 7: Commit**

```bash
cd ~/Documents/repos/atlas
git add alpha-lab/alphalab/governance.py alpha-lab/alphalab/cli.py alpha-lab/tests/test_budget_accounting.py
git commit -m "feat(alpha-lab): ledger governance + audit CLI (budget accounting, card-before-result)"
```

---

### Task 6: Atlas — wiring (manifest gate, LOOP.md ceilings, root CLAUDE.md, CHANGELOG) + push

**Files:**
- Modify: `~/Documents/repos/atlas/manifest.yml` (deploy gates list)
- Modify: `~/Documents/repos/atlas/evaluation/LOOP.md` (§6 "What stays human")
- Modify: `~/Documents/repos/atlas/CLAUDE.md` (the section that maps/binds verticals)
- Modify: `~/Documents/repos/atlas/CHANGELOG.md` (append)

**Interfaces:**
- Consumes: Tasks 1–5 (the suite the gate runs).
- Produces: deploy gate for `alpha-lab/` paths; the human-ceiling lines the skills cite.

- [ ] **Step 1: Add the deploy gate to `manifest.yml`**

In the `delivery.deploy.gates` list, after the `firm/` gate entry, add:

```yaml
      - kind: test
        cmd: "cd alpha-lab && .venv/bin/python -m pytest -q"
        when_paths: ["alpha-lab/"]
```

Note for the future deploy: the RUNTIME clone needs a one-time venv bootstrap before the first atlas-redeploy that touches `alpha-lab/` (Task 12 covers it).

- [ ] **Step 2: Add the human ceilings to `evaluation/LOOP.md` §6**

Append to the bullet list in `## 6. What stays human (unchanged ceilings)`, before the "Owner decision 2026-08-04" paragraph:

```markdown
- Alpha-lab GO verdicts (2026-09-14): a GO is a decision memo to the
  owner only — the loop creates no build task, backlog item, or order
  path from it; building anything from a GO starts with the owner.
- Alpha-lab budgets (`alpha-lab/config/budget.yaml`) are owner-owned;
  agents propose via DECISION-REQUEST ledger entry, never edit.
```

- [ ] **Step 3: Bind the vertical in the atlas root `CLAUDE.md`**

Read the root `CLAUDE.md` and find where the other verticals are mapped/bound (the lines naming `trader/`, `swing/`, `value/` and their PROTOCOLs). Add one line in the same style:

```markdown
- alpha-lab/ — owner-idea triage vertical (verdicts only, no order path);
  research claims flow through alpha-lab/evaluation/PROTOCOL.md
  (momentum PROTOCOL is parent); loop wiring in alpha-lab/CLAUDE.md.
```

- [ ] **Step 4: Append to atlas `CHANGELOG.md`**

Follow the file's existing entry format (date + summary):

```markdown
## 2026-09-14 — alpha-lab vertical scaffold

New idea-triage vertical `alpha-lab/`: owner-submitted alpha ideas run a
governed research chain (triage → sealed card → backtest cycles →
adversarial validation) to a GO/NO-GO/BLOCKED-ON-DATA verdict memo.
Verdicts only — no order path (tests/test_verdicts_only.py tripwire).
PROTOCOL inherits momentum's as parent. Support package `alphalab/`
(state machine, INBOX parser, ledger audit CLI), owner budget caps,
manifest deploy gate for alpha-lab/ paths, LOOP.md §6 ceilings. Loop
skills land ai-server-side (alpha-intake/-research/-governor). Spec:
ai-server docs/superpowers/specs/2026-09-14-alpha-lab-design.md.
```

- [ ] **Step 5: Full suite + push**

```bash
cd ~/Documents/repos/atlas/alpha-lab && .venv/bin/python -m pytest -q
cd ~/Documents/repos/atlas
git diff | grep -iE 'api[_-]?key|token|secret|password'   # expect no output
git add manifest.yml evaluation/LOOP.md CLAUDE.md CHANGELOG.md
git commit -m "feat(alpha-lab): wire vertical — deploy gate, LOOP.md §6 ceilings, root binding, changelog"
git pull --rebase origin master && git push origin master
```
Expected: suite green, push accepted. If the push is rejected: rebase, re-run the suite, retry ONCE; still failing → stop and report divergence.

---

### Task 7: ai-server — router rule for `alpha:` prefix

**Files:**
- Modify: `~/Documents/repos/ai-server/src/runner/router.py` (the `_RULES` list)
- Modify: `~/Documents/repos/ai-server/tests/test_pure_functions.py` (TestRouter parametrize table)
- Modify: `~/Documents/repos/ai-server/.context/modules/runner/CHANGELOG.md` (append — pre-commit hook requires it for src/ changes)

**Interfaces:**
- Consumes: existing `router.route(description) -> str | None`.
- Produces: descriptions starting `alpha:` / `alpha idea:` route to skill `alpha-intake` (Tasks 8's skill).

- [ ] **Step 1: Sync the dev repo**

```bash
cd ~/Documents/repos/ai-server && git fetch origin && git merge origin/main
```

- [ ] **Step 2: Write the failing tests**

In `tests/test_pure_functions.py`, inside the `TestRouter` parametrize list, after the "Meta" block, add:

```python
        # Alpha-lab intake (anchored prefix — unanchored "alpha" words must
        # NOT match; "research alpha decay" stays a research-report)
        ("alpha: overnight gap fades in small caps", "alpha-intake"),
        ("alpha idea: VIX term structure inversion predicts SPY reversal", "alpha-intake"),
        ("research alpha decay in momentum strategies", "research-report"),
```

- [ ] **Step 3: Run them to verify the new cases fail**

Run: `cd ~/Documents/repos/ai-server && pipenv run pytest tests/test_pure_functions.py::TestRouter -v`
Expected: the two `alpha-intake` cases FAIL (route returns None); the `research alpha decay` case passes already.

- [ ] **Step 4: Add the rule to `src/runner/router.py`**

In `_RULES`, immediately after the plan-decomposer block (after the `\bmulti[- ]step\b` line) and before the coding-intent block, add:

```python
    # ── Alpha-lab idea intake (anchored: only an explicit "alpha:" prefix
    #    routes; route() lowercases+strips first, so ^ is the message start.
    #    Unprefixed alpha ideas reach alpha-intake via the LLM fallback on
    #    the skill's description.) ──
    (r"^alpha( idea)?:", "alpha-intake"),
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd ~/Documents/repos/ai-server && pipenv run pytest tests/test_pure_functions.py::TestRouter -v`
Expected: PASS, all cases.

- [ ] **Step 6: Append the runner CHANGELOG entry**

Follow the file's existing entry format, at the top of the entries:

```markdown
## 2026-09-14 — router: alpha-lab intake rule

Added anchored rule `^alpha( idea)?:` → `alpha-intake` (before the
coding-intent rules; anchored so "research alpha decay…" keeps routing to
research-report). Part of the alpha-lab vertical
(docs/superpowers/plans/2026-09-14-alpha-lab-implementation.md).
```

- [ ] **Step 7: Commit**

```bash
cd ~/Documents/repos/ai-server
git add src/runner/router.py tests/test_pure_functions.py .context/modules/runner/CHANGELOG.md
git commit -m "feat(router): route 'alpha:' prefix to alpha-intake (alpha-lab vertical)"
```

---

### Task 8: ai-server — `alpha-intake` skill (read-only dedup + dispatch)

**Files:**
- Create: `~/Documents/repos/ai-server/skills/alpha-intake/SKILL.md`
- Create: `~/Documents/repos/ai-server/skills/alpha-intake/GOTCHAS.md`
- Modify: `~/Documents/repos/ai-server/.context/SKILLS_REGISTRY.md` (add row)

**Interfaces:**
- Consumes: router rule (Task 7); dispatch MCP `enqueue_job` (tag `needs-dispatch-mcp`).
- Produces: dispatches kind `alpha-research` with payload `{"project_slug": "atlas", "idea_text": "<idea>", "session_timeout_seconds": 3600}` (the FILE-mode contract Task 9 implements).

**Design note (spec §4 amendment, recorded in Task 11):** intake is read-only + dispatch, NOT a workspace writer. Two verified reasons: (a) a router-created job carries no `project_slug` payload, so `session._resolve_project` would scope a workspace clone to the *ai-server* repo, not atlas; (b) an unisolated writer would need an `UNISOLATED_WRITER_ALLOWLIST` entry in `scripts/lint_docs.py` — a protected path. The FILE-mode alpha-research job (which gets `project_slug` via its dispatch payload) is the vertical's single writer.

- [ ] **Step 1: Write `skills/alpha-intake/SKILL.md`**

```markdown
---
name: alpha-intake
description: Intake for owner-submitted alpha ideas (atlas alpha-lab vertical) — read-only dedup sweep against every vertical's ledger + trials registry in the atlas dev clone, then dispatch the first alpha-research stage job carrying the idea text; replies with confirmation + dedup result. Trigger "alpha: <idea>" / "alpha idea: <idea>" (router rule), --kind=alpha_intake, or any owner message proposing a market-alpha / trading-edge hypothesis to investigate for a possible build.
model: claude-opus-5
effort: medium
permission_mode: acceptEdits
required_tools: [Read, Glob, Grep]
max_turns: 25
role: worker
division: atlas
privilege_class: read-only
context_files: ["skills/alpha-intake/GOTCHAS.md"]
tags: [atlas, alpha-lab, intake, needs-dispatch-mcp]
---

# alpha-intake — dedup the idea, dispatch the chain, confirm

You received an owner alpha idea in the job description (after the
"alpha:" / "alpha idea:" prefix, if present). You are READ-ONLY +
dispatch: you write no file, run no shell. Your read surface is the
atlas dev clone at `~/Documents/repos/atlas`.

Procedure:

1. Extract the idea text (strip the prefix). If nothing remains, reply
   asking for the idea in one line; stop.
2. Cheap dedup sweep (Grep/Read only) over the atlas dev clone: search
   2–4 distinctive keywords from the idea (effect names, tickers,
   "PEAD", "term structure", …) across
   `alpha-lab/evaluation/LEDGER.md`, `alpha-lab/evaluation/INBOX.md`,
   `alpha-lab/ideas/*/card.md`, and the other verticals' registries
   (`momentum|trader|swing|value/evaluation/LEDGER.md` and
   `*/evaluation/trials.jsonl`).
3. Clear prior match (same causal claim): do NOT dispatch. Reply citing
   the prior idea/ledger id and its verdict, and note that a materially
   different mechanism is welcome as a new submission.
4. Otherwise dispatch exactly ONE job via the dispatch MCP `enqueue_job`:
   kind `alpha-research`, description
   `alpha-research: file + triage owner idea — <first ~10 words>`,
   payload `{"project_slug": "atlas", "idea_text": "<full idea text>",
   "session_timeout_seconds": 3600}`.
5. Reply (your final message is the Telegram confirmation): idea
   received (one-line restatement), dedup result ("no prior match" or
   the nearest miss), the dispatched job id, and that the A-#### id +
   triage outcome arrive with the first stage summary.

## Gotchas

- You have NO write tools and the read-only guard profile denies writes
  anyway — never try to edit INBOX.md or create the idea directory. The
  FILE-mode alpha-research worker is the vertical's single writer and
  does the filing (at capacity it queues the idea in INBOX itself).
- Dedup here is a courtesy filter for instant feedback; the
  authoritative `Prior-art check:` happens at the carding stage. When
  unsure, dispatch — a wasted triage stage is cheaper than a silently
  swallowed idea.
- permission_mode must stay acceptEdits: plan mode silently blocks MCP
  tool calls, so a plan-mode intake would confirm ideas whose research
  job never fired (deploy-director incident class, 2026-07-30).
- The description may arrive without the "alpha:" prefix when the LLM
  router matched it semantically — treat the whole description as the
  idea then.
```

- [ ] **Step 2: Write `skills/alpha-intake/GOTCHAS.md`**

```markdown
# alpha-intake gotchas

- (2026-09-14, design) Read-only by construction: a router-created job
  has no project_slug payload, so a workspace-isolated intake would
  clone the AI-SERVER repo, not atlas — that is why filing belongs to
  the dispatched FILE-mode alpha-research job, which carries the slug
  in its payload.
- (2026-09-14, design) Plain-text Telegram messages go through
  triage_plain_text; a very short "alpha: X" can be triaged to chat
  instead of a task job. `/task alpha: <idea>` is the deterministic
  path; mention it to the owner if an idea seems to have vanished.
```

- [ ] **Step 3: Add the SKILLS_REGISTRY.md row**

In the Installed table, after the `pickem-analysis` row:

```markdown
| `alpha-intake` | Opus 5 / medium (acceptEdits; read-only + dispatch, INV-20) | Owner alpha-idea intake for the atlas alpha-lab vertical: read-only dedup sweep over every vertical's ledger/trials in the atlas dev clone, then dispatches the first `alpha-research` stage job with the idea text in its payload. Write-free by design — the FILE-mode stage worker is the vertical's single writer. Trigger `alpha: <idea>` (router rule) | — |
```

- [ ] **Step 4: Verify frontmatter + lint**

Run: `cd ~/Documents/repos/ai-server && python scripts/lint_docs.py && pipenv run pytest tests/test_skill_contracts.py tests/test_registry_failclosed.py -q`
Expected: lint all-pass (frontmatter parses, registry row present, role/privilege rules satisfied: read-only + needs-dispatch-mcp + acceptEdits); tests green.

- [ ] **Step 5: Commit**

```bash
cd ~/Documents/repos/ai-server
git add skills/alpha-intake .context/SKILLS_REGISTRY.md
git commit -m "feat(skills): alpha-intake — read-only dedup + dispatch intake for alpha-lab"
```

---

### Task 9: ai-server — `alpha-research` skill (the stage worker / chain driver)

**Files:**
- Create: `~/Documents/repos/ai-server/skills/alpha-research/SKILL.md`
- Create: `~/Documents/repos/ai-server/skills/alpha-research/GOTCHAS.md`
- Modify: `~/Documents/repos/ai-server/.context/SKILLS_REGISTRY.md` (add row)

**Interfaces:**
- Consumes: alpha-lab vertical (Tasks 1–6: `alphalab.state` schema, PROTOCOL, budget.yaml, LEDGER/INBOX formats); dispatch payload contract from Task 8 (`idea_text`) and from itself (`idea_id`).
- Produces: the chain — each non-terminal stage dispatches kind `alpha-research` with payload `{"project_slug": "atlas", "idea_id": "A-####", "session_timeout_seconds": 3600}`; terminal stages produce the DECISION ledger entry + verdict memo.

- [ ] **Step 1: Write `skills/alpha-research/SKILL.md`**

```markdown
---
name: alpha-research
description: Alpha-lab stage worker — advances ONE owner idea exactly one lifecycle stage per job under atlas alpha-lab/evaluation/PROTOCOL.md (file+triage -> seal card -> one backtest cycle -> adversarial validation -> verdict GO/NO-GO/BLOCKED-ON-DATA), then dispatches the next stage job after the push. Dispatch-driven chain, not scheduled. Payload requires project_slug=atlas plus idea_id (advance existing) or idea_text (file new). Kind alpha-research.
model: claude-opus-5
effort: high
permission_mode: bypassPermissions
required_tools: [Read, Write, Edit, Bash, Glob, Grep]
max_turns: 80
isolation: workspace
subagents: [code-review]
post_review:
  trigger: always
role: worker
division: atlas
privilege_class: guarded-writer
context_files: ["skills/alpha-research/GOTCHAS.md"]
tags: [atlas, alpha-lab, research, needs-dispatch-mcp]
---

# alpha-research — one stage, one commit, one dispatch

You advance ONE alpha-lab idea exactly ONE stage, then stop. Binding
docs, read this run: `alpha-lab/CLAUDE.md`,
`alpha-lab/evaluation/PROTOCOL.md`, `evaluation/LOOP.md` §6. Timer
discipline: first command `date +%s > /tmp/alpha-stage-start`; check
elapsed before each phase; at 45 min write an honest note into your
summary, commit what is sealed, and close out — the chain resumes from
state.json (an honest INCOMPLETE beats a timeout).

Venv (fresh clone): `cd alpha-lab && python3.12 -m venv .venv &&
.venv/bin/pip install -q pytest pyyaml`.

Mode from payload:

- **`idea_text` present (FILE mode):** count non-terminal ideas
  (`ideas/*/state.json` with stage != "verdict"). At/over budget.yaml
  `max_active_ideas` → append the idea to `evaluation/INBOX.md` as an
  unchecked `- [ ] <text> (owner, <today>)` line, commit, push, report
  "queued at capacity"; STOP (no dispatch). Otherwise: assign the next
  A-#### (max existing ideas/ id + 1, A-0001 if none), create
  `ideas/A-####/state.json` via `alphalab.state.new_state` (max_cycles
  from budget.yaml), record the idea in INBOX — checked, with
  ` -> A-####` (append the line if it came via Telegram; check off the
  existing line if the governor dispatched it from a hand-edit), append
  an IDEA ledger entry (first body line `Idea: A-####`, then the idea
  text verbatim), then run the TRIAGE stage in this same session.
- **`idea_id` present (ADVANCE mode):** load `ideas/<id>/state.json`;
  if terminal, report "already decided — <outcome>" and STOP. Execute
  exactly the current stage.

## Stages

**triage** (submitted → triaged | verdict): authoritative prior-art
sweep (all five verticals' ledgers + trials registries); mechanism
plausibility; free-data availability — name the exact series/universe
needed and which existing free source covers it (Alpaca IEX daily,
yfinance WITH its survivorship caveat stated, FRED, Finnhub earnings).
A fetch error is a retry, not absence (error ≠ absence). Write
`ideas/A-####/research/triage.md` with the findings. Outcomes: advance
to `triaged`; or terminal NO-GO (prior art / implausible mechanism) or
BLOCKED-ON-DATA (paid-only data; LLM-signal class) — then run the
VERDICT close-out below in this same session.

**card** (triaged → carded): write `ideas/A-####/card.md` + a
HYPOTHESIS ledger entry with every PROTOCOL §2 field (`Criteria
observables:`, `Success criterion:`, `Kill criterion:`, `Prior-art
check:`). The card commit MUST be pushed to origin/master before the
backtest stage is dispatched — dispatch only after the push succeeds
(momentum E-0032: a card sealed after execution voids the measurement).

**backtest cycle** (carded → backtesting; backtesting → backtesting |
validated | verdict): ONE confirmatory cycle against the sealed card.
Build the harness under `ideas/A-####/research/cycle-<n>/` where n =
cycles_used + 1 (stdlib + pyyaml only; costs ≥3bps/side, pessimistic
fills, walk-forward/purged CV, placebo M≥200, `manifest.json`
provenance — PROTOCOL §3). Append trials.jsonl lines for EVERY variant
evaluated, then RESULT and VERDICT ledger entries; increment
cycles_used. Success or kill criterion met AS WRITTEN → advance to
`validated`. Neither met, budget remaining → stay `backtesting` (the
NEXT cycle needs an amended card first: new HYPOTHESIS entry, ≤2 params
changed — that is the next job's first act). Budget exhausted → terminal
NO-GO "budget death" (deterministic; skip validation) → VERDICT
close-out now.

**validation** (validated → verdict): spawn the adversarial validator as
a Task subagent with a clean context — give it ONLY the card and the
cycle artifacts, not your narrative. It scores each criterion AS
WRITTEN and holds kill-standing; its scoring is final. Record its
findings as a VERDICT ledger entry, then run the VERDICT close-out.

**VERDICT close-out** (terminal, from any path above): set state.json
stage="verdict" with verdict.outcome ∈ GO / NO-GO / BLOCKED-ON-DATA and
a one-line reason; append the DECISION ledger entry citing evidence
E-ids. A GO must state lifetime N (trials.jsonl), the Deflated Sharpe
Ratio against it, the placebo percentile, a recommended target vertical
(trader / swing / value / momentum), and a ≤5-line build sketch. NO
further dispatch — the chain ends here.

## Chain mechanics (after every NON-terminal stage)

1. Gates: `cd alpha-lab && .venv/bin/python -m pytest -q` green;
   code-review subagent LGTM on any code diff; secrets grep. ONE
   commit, footers `Alpha-Idea: A-####` + `Job: <job-id8>`.
2. `git pull --rebase origin master`, then push (on reject: rebase,
   retry ONCE; still failing → report divergence, do NOT dispatch).
3. Budget check: `psql assistant -tAc "SELECT count(*) FROM jobs WHERE
   kind IN ('alpha-intake','alpha-research') AND created_at > now() -
   interval '24 hours'"`. At/over budget.yaml `max_alpha_jobs_per_day`
   → skip the dispatch and say "cap-stalled" in your summary (the daily
   governor resumes it).
4. Dispatch AFTER the push: `enqueue_job`, kind `alpha-research`,
   description `alpha-research: <next stage> A-#### — <short idea
   tag>`, payload `{"project_slug": "atlas", "idea_id": "A-####",
   "session_timeout_seconds": 3600}`.

## Write surface

`alpha-lab/**` only. You NEVER edit: any other vertical, `tradingcore/`
(read-only import), `config/budget.yaml`, the tests (tripwire OR module
suite), sealed cards, past ledger entries, this skill. Proposals go in
a DECISION-REQUEST ledger entry + your summary.

## Close-out

Final message = Telegram summary: idea id, stage executed, outcome,
cycles used vs budget, next dispatched job id — or, on a terminal
stage, the verdict memo: outcome, the single strongest reason, N / DSR
/ placebo percentile for a GO, and what (if anything) waits on the
owner.

## Gotchas

- The card push precedes the backtest DISPATCH, not merely the backtest
  run — never run even a "quick look" backtest in the card session.
- trials.jsonl lines land before the cycle's VERDICT entry; "I didn't
  log the rejects" invalidates the cycle (PROTOCOL §4).
- Never bump session_timeout_seconds toward the 5400 cap as a stage
  stopgap — split the work across chain jobs instead (the
  atlas-momo-research timeout incident class).
- A dispatch that fails AFTER a successful push is safe to leave: the
  daily governor detects the stalled chain from state.json and
  re-dispatches (LOOP.md §5 design rule — repo artifacts travel in one
  commit; the enqueue is the only out-of-band write, after the push).
- A candidate needing numpy/pandas is a blocker note for the owner,
  never a pip install (momentum E-0033 precedent).
```

- [ ] **Step 2: Write `skills/alpha-research/GOTCHAS.md`**

```markdown
# alpha-research gotchas

- (2026-09-14, design) The schedule-free chain: this skill is dispatched
  by alpha-intake (FILE mode, payload idea_text), by itself (ADVANCE
  mode, payload idea_id), and by alpha-governor (both modes). If a
  payload arrives with NEITHER key, report the malformed dispatch and
  stop — do not guess an idea.
- (2026-09-14, design) Workspace clones drop gitignored files but the
  atlas manifest's `delivery.env_files: [".env"]` re-provisions the
  owner keys — Alpaca/FRED/Finnhub creds are available for data
  fetches; brokerage ORDER use of them is forbidden (verdicts only).
```

- [ ] **Step 3: Add the SKILLS_REGISTRY.md row**

```markdown
| `alpha-research` | Opus 5 / high (workspace isolation; code-review subagent + post-review; dispatch-chained, not scheduled) | Alpha-lab stage worker: advances ONE idea exactly one lifecycle stage per job (file+triage → seal card → one backtest cycle w/ placebo + trials.jsonl → adversarial validation → verdict GO/NO-GO/BLOCKED-ON-DATA) under atlas `alpha-lab/evaluation/PROTOCOL.md`, then dispatches the next stage after the push (card sealed+pushed before any backtest — E-0032 discipline; daily job cap from owner-owned budget.yaml). Payload: `project_slug: atlas` + `idea_id` or `idea_text` | — |
```

- [ ] **Step 4: Verify frontmatter + lint**

Run: `cd ~/Documents/repos/ai-server && python scripts/lint_docs.py && pipenv run pytest tests/test_skill_contracts.py -q`
Expected: all green (workspace isolation satisfies the unisolated-writers rule automatically).

- [ ] **Step 5: Commit**

```bash
cd ~/Documents/repos/ai-server
git add skills/alpha-research .context/SKILLS_REGISTRY.md
git commit -m "feat(skills): alpha-research — one-stage-per-job chain worker for alpha-lab"
```

---

### Task 10: ai-server — `alpha-governor` skill + schedule row

**Files:**
- Create: `~/Documents/repos/ai-server/skills/alpha-governor/SKILL.md`
- Create: `~/Documents/repos/ai-server/skills/alpha-governor/GOTCHAS.md`
- Modify: `~/Documents/repos/ai-server/.context/SKILLS_REGISTRY.md` (add row)
- Modify: `~/Documents/repos/ai-server/scripts/seed-schedules.sh` (add row)

**Interfaces:**
- Consumes: `alphalab.cli audit` (Task 5), state.json schema (Task 3), INBOX format (Task 4), dispatch payload contracts (Tasks 8–9), budget.yaml caps (Task 1).
- Produces: schedule `alpha-governor` daily `30 9 * * *` with payload `{"project_slug":"atlas"}`.

- [ ] **Step 1: Write `skills/alpha-governor/SKILL.md`**

```markdown
---
name: alpha-governor
description: Daily alpha-lab governor — resume stalled research chains (stale non-terminal state.json -> re-dispatch, double-dispatch guarded), drain INBOX.md hand-edits into the chain within capacity, budget audit via alphalab.cli (discrepancy = PROTOCOL-VIOLATION ledger entry), spot-check new verdicts' evidence chains, append AUDIT entries. Frozen evaluator: judges and dispatches, never edits harnesses/budgets/cards/skills. Dispatch for the alpha-governor schedule/job_kind, or on demand ("run the alpha-lab governor").
model: claude-opus-5
effort: medium
escalation:
  on_failure:
    model: claude-opus-5
    effort: high
permission_mode: bypassPermissions
required_tools: [Read, Write, Edit, Bash, Glob, Grep]
max_turns: 50
isolation: workspace
role: worker
division: atlas
privilege_class: guarded-writer
context_files: ["skills/alpha-governor/GOTCHAS.md"]
tags: [atlas, alpha-lab, evaluation, scheduled-capable, needs-dispatch-mcp]
---

# alpha-governor — resume, drain, audit, then stop

You are alpha-lab's frozen evaluator, running daily in a workspace clone
of atlas (the schedule payload carries project_slug). You judge and
dispatch; you never run research yourself and never edit harnesses,
cards, budgets, `alphalab/`, tests, or any skill (including this one).
Binding docs: `alpha-lab/CLAUDE.md`, `alpha-lab/evaluation/PROTOCOL.md`.
Venv (fresh clone): `cd alpha-lab && python3.12 -m venv .venv &&
.venv/bin/pip install -q pytest pyyaml`.

Duties, in order:

1. **Chain liveness** (lead with findings): for each
   `ideas/*/state.json` that is non-terminal with `last_advanced_at`
   older than 26 hours: first guard against double-dispatch —
   `psql assistant -tAc "SELECT count(*) FROM jobs WHERE
   kind='alpha-research' AND payload->>'idea_id'='A-####' AND status IN
   ('queued','running','deferred')"` — if 0, re-dispatch via
   `enqueue_job` (kind `alpha-research`, payload `{"project_slug":
   "atlas", "idea_id": "A-####", "session_timeout_seconds": 3600}`).
   A cap-stall is normal operation; a crashed or vanished stage job is
   a FINDING to lead with (the governor-dark incident class).
2. **INBOX drain**: for unchecked `- [ ]` entries (oldest first): while
   the non-terminal idea count is under budget.yaml `max_active_ideas`
   AND today's alpha job count (same psql count as the stage worker's
   budget check) is under `max_alpha_jobs_per_day`, dispatch a
   FILE-mode job (kind `alpha-research`, payload `{"project_slug":
   "atlas", "idea_text": "<entry text>", "session_timeout_seconds":
   3600}`). Do NOT check entries off yourself — the FILE-mode worker
   does (single-writer discipline).
3. **Budget audit**: `cd alpha-lab && .venv/bin/python -m alphalab.cli
   audit`. Non-zero exit → append a PROTOCOL-VIOLATION ledger entry
   quoting the violation lines verbatim. A discrepancy is a finding to
   report, never something to "fix" by editing state or ledger.
4. **Verdict spot-check** (only when a DECISION entry is newer than the
   newest AUDIT entry): for the newest DECISION's idea, verify — the
   HYPOTHESIS card E-id precedes the first RESULT E-id; trials.jsonl
   has lines for the idea; the RESULT cites a placebo run; a GO states
   N + DSR. Append an AUDIT entry (pass, or findings verbatim).
5. **Close-out**: if you appended ledger entries, ONE commit (footer
   `Alpha-Governor` + `Job: <job-id8>`), `git pull --rebase origin
   master`, push. Final message = Telegram summary: chains resumed,
   ideas filed from INBOX, audit result, spot-check result, anything
   waiting on the owner.

## Gotchas

- Quiet days are the normal case: no stalls, empty INBOX, clean audit →
  one-line summary, no commit, done. Dispatch nothing "just in case".
- The 26h staleness threshold assumes this schedule stays daily; if the
  cadence changes in seed-schedules.sh, revisit the threshold here.
- Your own dispatches count toward max_alpha_jobs_per_day — re-check
  the day's count before each dispatch in duties 1–2 and stop at the
  cap; tomorrow's run picks up the rest.
- permission_mode bypassPermissions + workspace guard hooks is the
  posture; the dispatch MCP works in it (unlike plan mode, which
  silently blocks MCP).
```

- [ ] **Step 2: Write `skills/alpha-governor/GOTCHAS.md`**

```markdown
# alpha-governor gotchas

- (2026-09-14, design) Workspace-isolated ON PURPOSE, unlike the weekly
  vertical governors (atlas-trader-evaluate et al. run in the shared
  dev clone): this governor writes only ledger AUDIT appends and
  dispatches, and the clone posture avoids adding it to
  UNISOLATED_WRITER_ALLOWLIST in scripts/lint_docs.py (protected path).
  Do not "normalize" it to the shared-clone posture.
- (2026-09-14, design) jobs.payload is queried with `->>` — if the
  column were ever migrated from JSON, revisit the liveness queries.
```

- [ ] **Step 3: Add the SKILLS_REGISTRY.md row**

```markdown
| `alpha-governor` | Opus 5 / medium (→ high on failure; workspace isolation; frozen evaluator) | Daily alpha-lab governor (09:30 UTC, payload `project_slug: atlas`): resume stalled idea chains (26h staleness, double-dispatch guarded via jobs query), drain INBOX hand-edits within capacity caps, budget audit via `alphalab.cli audit` (discrepancy = PROTOCOL-VIOLATION entry), verdict evidence spot-check, AUDIT ledger appends. Judges + dispatches; never edits harnesses/budgets/cards/skills | — |
```

- [ ] **Step 4: Add the schedule row to `scripts/seed-schedules.sh`**

After the pickem block, before the closing `echo "Schedules seeded."`:

```bash
# ── Alpha-lab (atlas alpha-lab/, owner-idea triage vertical, 2026-09-14) ───
# The research chain is dispatch-driven (intake -> stage job -> next stage);
# only the governor is cron'd. DAILY so cap-stalled or crashed chains resume
# within a day (continuous-until-verdict pacing, spec 2026-09-14 as
# amended). 09:30 UTC is clear every day: managers 06:00, pickem-sync 09:00
# (Sun/Mon/Tue/Fri), builds 10:00 (Tue/Fri), 11:00 loop block, daily-brief
# 12:00. Workspace-isolated with project_slug (unlike the weekly vertical
# governors): it writes only ledger AUDIT appends + dispatches, and the
# clone posture avoids an UNISOLATED_WRITER_ALLOWLIST entry in
# lint_docs.py (protected path).
upsert 'alpha-governor' '30 9 * * *' 'alpha-governor' 'alpha-governor: daily alpha-lab governor -> resume stalled idea chains, drain INBOX, budget audit via alphalab.cli, verdict spot-check (skills/alpha-governor)' '{"project_slug":"atlas"}'
```

- [ ] **Step 5: Verify lint + seeder syntax**

Run: `cd ~/Documents/repos/ai-server && python scripts/lint_docs.py && bash -n scripts/seed-schedules.sh`
Expected: lint all-pass; `bash -n` silent (syntax OK). Do NOT execute the seeder here — it runs against the prod DB at deploy time.

- [ ] **Step 6: Commit**

```bash
cd ~/Documents/repos/ai-server
git add skills/alpha-governor .context/SKILLS_REGISTRY.md scripts/seed-schedules.sh
git commit -m "feat(skills): alpha-governor — daily chain-resume/drain/audit governor + schedule row"
```

---

### Task 11: ai-server — spec amendments, org-charter check, INDEX, full gates, push

**Files:**
- Modify: `~/Documents/repos/ai-server/docs/superpowers/specs/2026-09-14-alpha-lab-design.md` (append amendments)
- Modify: `~/Documents/repos/ai-server/.context/INDEX.md` (update the 2026-09-14 section)
- Possibly modify: `~/Documents/repos/ai-server/.context/org/divisions/atlas/CHARTER.md` (roster rows, only if it lists per-skill rows)

**Interfaces:**
- Consumes: everything above.
- Produces: honest documentation trail; ai-server main pushed.

- [ ] **Step 1: Append the amendments section to the spec**

At the end of `docs/superpowers/specs/2026-09-14-alpha-lab-design.md`:

```markdown
## Amendments (2026-09-14, discovered at implementation planning)

1. **Intake is read-only + dispatch (§4 revised).** A router-created job
   carries no `project_slug` payload, so a workspace-isolated intake
   would clone the ai-server repo, not atlas
   (`session._resolve_project`); an unisolated writer would need an
   `UNISOLATED_WRITER_ALLOWLIST` entry in `scripts/lint_docs.py` — a
   protected path. Intake therefore dedups read-only against the atlas
   dev clone and dispatches a FILE-mode `alpha-research` job carrying
   the idea text; the stage worker is the vertical's single writer.
2. **Governor is workspace-isolated and DAILY (§6 revised).** Shared
   dev-clone posture would also require the protected-path allowlist
   edit; workspace isolation avoids it and adds guard hooks. Daily
   (09:30 UTC) instead of weekly because chain resumption is the
   governor's job: with a weekly governor, any cap-stall or crashed
   stage would freeze a chain for up to a week, contradicting the
   approved continuous-until-verdict pacing.
3. **`max_alpha_jobs_per_day` default is 6, not 2 (§7 revised).** At 2,
   a 5–7-job idea chain mathematically stalls to the governor every
   day; 6 lets one idea traverse its whole chain within a day while
   still bounding quota. Owner-tunable in `alpha-lab/config/budget.yaml`
   as before.
```

- [ ] **Step 2: Update `.context/INDEX.md`**

In the `## Additions 2026-09-14` section, replace the row's "implementation not started" wording:

```markdown
| Understand the alpha-lab vertical (owner submits an alpha idea → autonomous triage/backtest chain → GO / NO-GO / BLOCKED-ON-DATA verdict memo; verdicts only, no build, no order path) — spec approved 2026-09-14 (see its Amendments section), implemented same day | `docs/superpowers/specs/2026-09-14-alpha-lab-design.md`; plan `docs/superpowers/plans/2026-09-14-alpha-lab-implementation.md`; atlas `alpha-lab/CLAUDE.md` |
| Work on the alpha-lab loop skills | `skills/alpha-{intake,research,governor}/SKILL.md`; atlas `alpha-lab/evaluation/PROTOCOL.md` (binding) |
```

- [ ] **Step 3: Org charter roster check**

Read `.context/org/divisions/atlas/CHARTER.md`. If it maintains a per-skill roster table (it lists rows for `atlas-trader-*` etc.), append rows for `alpha-intake` (Role worker / Privilege read-only), `alpha-research` (worker / guarded-writer), `alpha-governor` (worker / guarded-writer), copying the exact column format of the trader rows. If it has no such table, skip — the lint's charter cross-check only fires on rows that exist.

- [ ] **Step 4: Full gates**

```bash
cd ~/Documents/repos/ai-server
python scripts/lint_docs.py
pipenv run pytest -q
git diff | grep -iE 'api[_-]?key|token|secret|password'   # expect no output
```
Expected: lint all-pass, full suite green.

- [ ] **Step 5: Commit and push**

```bash
cd ~/Documents/repos/ai-server
git add docs/superpowers/specs/2026-09-14-alpha-lab-design.md .context/INDEX.md .context/org
git commit -m "docs(alpha-lab): spec amendments (intake posture, daily governor, jobs/day cap), INDEX + charter roster"
git fetch origin && git merge origin/main
git push origin main
```
On reject: fetch, merge, re-run gates, retry ONCE; still failing → stop and report divergence.

---

### Task 12: Deploy + end-to-end acceptance + eval case

**Files:**
- Create (last step): `~/Documents/repos/ai-server/evals/cases/alpha-intake.yml`

**Interfaces:**
- Consumes: everything deployed.
- Produces: proof the loop works with zero human touch after submission; the dedup eval case seeded from a real dead idea.

- [ ] **Step 1: Deploy the server**

Dispatch the gated deploy: from Telegram (owner) or an existing session with dispatch rights, `/task deploy server`. The `server-deploy` skill ff-pulls, runs the pytest gate, seeds schedules (the new `alpha-governor` row lands, first fire at the NEXT 09:30 UTC slot — not immediately), and restarts. Verify afterwards: `psql assistant -c "SELECT name, cron_expression, paused FROM schedules WHERE name='alpha-governor';"` shows the row unpaused.

- [ ] **Step 2: Bootstrap the alpha-lab venv in the atlas runtime clone**

One-time, so the manifest's `alpha-lab/` test gate can run on future atlas deploys. Locate the runtime clone the `atlas-redeploy` skill targets (its SKILL.md names the path), then:

```bash
cd <atlas-runtime-clone>/alpha-lab || (cd <atlas-runtime-clone> && git pull --ff-only && cd alpha-lab)
python3.12 -m venv .venv && .venv/bin/pip install -q pytest pyyaml
.venv/bin/python -m pytest -q
```
Expected: suite green in the runtime clone.

- [ ] **Step 3: Acceptance run 1 — weak idea reaches NO-GO untouched**

Submit via Telegram: `/task alpha: buying every stock whose name starts with the letter Q outperforms SPY`.
Expected chain, with NO human input after submission:
1. `alpha-intake` job replies with confirmation + dispatched job id.
2. FILE-mode `alpha-research` job assigns `A-0001`, and its triage stage kills it — no plausible causal mechanism — terminal NO-GO in the same session (or, if it generously cards it, the chain runs on and the kill criterion ends it within budget).
3. Telegram memo states NO-GO + reason; atlas master shows the commits (`ideas/A-0001/`, IDEA + DECISION ledger entries, checked INBOX line).

Verify: `cd ~/Documents/repos/atlas && git pull --rebase origin master && cat alpha-lab/ideas/A-0001/state.json` shows `"stage": "verdict"` with `"outcome": "NO-GO"`, and `alpha-lab/.venv/bin/python -m alphalab.cli audit` (run from `alpha-lab/`) prints `audit clean`.

- [ ] **Step 4: Acceptance run 2 — data-infeasible idea reaches BLOCKED-ON-DATA at triage**

Submit: `/task alpha: microsecond-level order-book imbalance on NYSE predicts the next tick`.
Expected: triage identifies that tick/order-book depth data is paid-only (free sources are daily/IEX-minute at best) → terminal BLOCKED-ON-DATA, memo names the missing data and does NOT propose buying it.

- [ ] **Step 5: Acceptance run 3 — governor quiet day**

After both verdicts, wait for (or dispatch on demand: `/task alpha-governor: run the alpha-lab governor`) a governor run. Expected summary: no stalls, INBOX empty of unchecked entries, `audit clean`, verdict spot-check AUDIT entry appended for the newest DECISION.

- [ ] **Step 6: Write the dedup eval case from the real dead idea**

`evals/cases/alpha-intake.yml` (use the EXACT text submitted in Step 3):

```yaml
skill: alpha-intake
cases:
  - name: dedup-known-dead-idea
    input: "alpha: buying every stock whose name starts with the letter Q outperforms SPY"
    rubric:
      - "Identifies the prior alpha-lab idea (A-#### / ledger entry) as matching"
      - "Does NOT dispatch a new alpha-research job"
      - "Invites resubmission only with a materially different mechanism"
    baseline_score: 4
```

- [ ] **Step 7: Final commit + push**

```bash
cd ~/Documents/repos/ai-server
git add evals/cases/alpha-intake.yml
git commit -m "test(evals): alpha-intake dedup case seeded from acceptance run"
git fetch origin && git merge origin/main && git push origin main
```

- [ ] **Step 8: Report**

Summarize to the owner: both acceptance verdicts with their memos, the governor's first audit, the deployed schedule row, and the two things that stay owner-side forever (building anything from a GO; editing budget.yaml).
