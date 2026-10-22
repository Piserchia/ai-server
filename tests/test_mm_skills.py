"""
Structural contract tests for the nine MoneyMachine skills (`skills/mm-*/SKILL.md`).

Fast, no LLM, no DB. Pins the things the design spec says every `mm-*` body
must carry (spec §7, §6.4, §8.6; plan Task 11):

- exactly nine skills, none named `*-redeploy`;
- the verbatim dispatch sentence (no `server-patch`/`new-skill`/`atlas-*`
  dispatch from inside the company);
- the budget psql counts list the five stage kinds exactly and never
  `kind LIKE 'mm-%'` (the round-1 blocker: a governor counting itself);
- `mm-report` and `mm-govern` end with the `TASK_COMPLETE:` rule so a
  Telegram-originated run resolves instead of auto-continuing;
- every `mmcore` subcommand a skill invokes exists in the pinned CLI;
- frontmatter shape: Bash holders are workspace-isolated, the CEO and the
  resumer are read-only + acceptEdits, every skill is in the `moneymachine`
  division, models are in the gateway alias table.

Run: cd <worktree> && SERVER_ROOT="$PWD" <venv>/bin/python -m pytest tests/test_mm_skills.py -q
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]

MM = sorted(p.parent.name for p in (ROOT / "skills").glob("mm-*/SKILL.md"))

DISPATCH_SENTENCE = (
    "Dispatch only kinds matching `mm-*` with `payload.project_slug` = `moneymachine`. "
    "Any other kind — `server-patch`, `new-skill`, `atlas-*`, anything — is a "
    "DECISION-REQUEST ledger entry, never a dispatch."
)

PINNED_SUBCOMMANDS = {
    "preflight", "budget", "cycle", "ledger", "trials", "families",
    "shadow", "report", "new-bucket", "check",
}

STAGE_KINDS = "('mm-research','mm-bridge','mm-architect','mm-engineer','mm-execute')"

EXPECTED_NINE = [
    "mm-architect", "mm-bridge", "mm-ceo", "mm-engineer", "mm-execute",
    "mm-govern", "mm-report", "mm-research", "mm-resume",
]

# The two skills that dispatch nothing (spec §7 "Dispatches" column).
NON_DISPATCHERS = {"mm-execute", "mm-report"}
# The two read-only + dispatch skills (spec §7, bold **read-only**).
READ_ONLY = {"mm-ceo", "mm-resume"}

_FRONTMATTER_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n(.*)\Z", re.DOTALL)


def _split(name: str) -> tuple[dict, str]:
    """Return (frontmatter mapping, body text) for skills/<name>/SKILL.md."""
    text = (ROOT / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
    m = _FRONTMATTER_RE.match(text)
    assert m, f"{name}: SKILL.md does not start with a `---` frontmatter block"
    fm = yaml.safe_load(m.group(1))
    assert isinstance(fm, dict), f"{name}: frontmatter is not a mapping"
    return fm, m.group(2)


def _frontmatter(name: str) -> dict:
    return _split(name)[0]


def _body(name: str) -> str:
    return _split(name)[1]


def _budget_query_lines(body: str) -> list[str]:
    """The §6.4 step-4 count queries: the `FROM jobs` lines that count over a
    time window. Excludes the double-dispatch guard (no interval) and the
    CEO's liveness listing (no count(*))."""
    return [
        ln for ln in body.splitlines()
        if "FROM jobs" in ln and "count(*)" in ln.lower() and "interval" in ln
    ]


def _models_of(fm: dict) -> list[str]:
    models = []
    if fm.get("model"):
        models.append(fm["model"])
    esc = (fm.get("escalation") or {}).get("on_failure") or {}
    if esc.get("model"):
        models.append(esc["model"])
    return models


# ─── existence / naming ────────────────────────────────────────────────────


def test_nine_skills_exist():
    assert MM == EXPECTED_NINE, (
        f"expected the nine mm-* skills {EXPECTED_NINE}; found {MM} "
        f"(missing: {sorted(set(EXPECTED_NINE) - set(MM))}, "
        f"extra: {sorted(set(MM) - set(EXPECTED_NINE))})"
    )


def test_no_skill_named_redeploy():
    offenders = [n for n in MM if "redeploy" in n]
    assert offenders == [], f"no mm-* skill may be named *-redeploy: {offenders}"
    for n in MM:
        assert "redeploy" not in str(_frontmatter(n).get("name", "")), (
            f"{n}: frontmatter name must not be a redeploy skill"
        )


# ─── body pins ─────────────────────────────────────────────────────────────


def test_every_body_has_dispatch_sentence():
    missing = [n for n in MM if DISPATCH_SENTENCE not in _body(n)]
    assert missing == [], (
        f"bodies missing the verbatim dispatch sentence (spec §7): {missing}"
    )


def test_dispatchers_have_needs_dispatch_mcp():
    for n in MM:
        fm, body = _split(n)
        tags = fm.get("tags") or []
        if "enqueue_job" in body:
            assert "needs-dispatch-mcp" in tags, (
                f"{n}: body calls enqueue_job but tags lack needs-dispatch-mcp: {tags}"
            )
    for n in NON_DISPATCHERS:
        if n not in MM:
            continue
        fm, body = _split(n)
        assert "enqueue_job" not in body, f"{n}: dispatches nothing — no enqueue_job in body"
        assert "needs-dispatch-mcp" not in (fm.get("tags") or []), (
            f"{n}: dispatches nothing — must not carry needs-dispatch-mcp"
        )


def test_division_and_project_slug():
    for n in MM:
        fm, body = _split(n)
        assert fm.get("division") == "moneymachine", (
            f"{n}: division must be 'moneymachine', got {fm.get('division')!r}"
        )
        assert (
            '"project_slug":"moneymachine"' in body
            or "project_slug=moneymachine" in body
        ), f"{n}: body must carry the moneymachine project_slug (payload or grammar form)"


def test_mmcore_subcommands_are_pinned():
    for n in MM:
        used = set(re.findall(r"-m mmcore (\S+)", _body(n)))
        # A trailing backtick or punctuation glued to the subcommand is noise.
        used = {u.strip("`'\",.;:)") for u in used}
        used.discard("")
        unknown = used - PINNED_SUBCOMMANDS
        assert unknown == set(), (
            f"{n}: invokes mmcore subcommands not in the pinned CLI (spec §9.1): "
            f"{sorted(unknown)}; allowed {sorted(PINNED_SUBCOMMANDS)}"
        )


def test_budget_query_lists_stage_kinds_only():
    checked = []
    for n in MM:
        body = _body(n)
        if "FROM jobs" not in body or "mmcore budget" not in body:
            continue
        checked.append(n)
        lines = _budget_query_lines(body)
        assert lines, (
            f"{n}: body runs `mmcore budget` but has no windowed count(*) FROM jobs "
            f"query lines (§6.4 step 4)"
        )
        for ln in lines:
            assert STAGE_KINDS in ln, (
                f"{n}: budget query must list the five stage kinds exactly "
                f"{STAGE_KINDS}; got: {ln.strip()}"
            )
            assert "kind LIKE 'mm-%'" not in ln, (
                f"{n}: budget query must never count governors/resumer/CEO/reporter "
                f"(kind LIKE 'mm-%'): {ln.strip()}"
            )
    # Every skill that dispatches a stage must do the cap check; if none of
    # the existing skills did, the loop above would vacuously pass.
    dispatching_present = [n for n in MM if n not in NON_DISPATCHERS]
    if dispatching_present:
        assert checked, (
            f"none of {dispatching_present} carries both `FROM jobs` and `mmcore budget`"
        )


def test_report_and_govern_bodies_end_with_task_complete_rule():
    for n in ("mm-report", "mm-govern"):
        assert n in MM, f"{n} is missing — see test_nine_skills_exist"
        body = _body(n)
        assert "TASK_COMPLETE:" in body, (
            f"{n}: body must carry the `TASK_COMPLETE:` close-out rule (spec §8.6) so a "
            f"Telegram-originated run resolves instead of auto-continuing"
        )
        assert "## Close-out" in body, f"{n}: body must have a `## Close-out` section"
        close_out = body.split("## Close-out", 1)[1]
        assert "TASK_COMPLETE:" in close_out, (
            f"{n}: the `TASK_COMPLETE:` rule must appear in `## Close-out`"
        )


# ─── frontmatter shape ─────────────────────────────────────────────────────


def test_post_review_is_mapping_when_present():
    for n in MM:
        fm = _frontmatter(n)
        if "post_review" not in fm:
            continue
        pr = fm["post_review"]
        assert isinstance(pr, dict), f"{n}: post_review must be a mapping, got {pr!r}"
        assert "trigger" in pr, f"{n}: post_review mapping must carry `trigger`"


def test_bash_holders_are_workspace_isolated():
    for n in MM:
        fm = _frontmatter(n)
        tools = fm.get("required_tools") or []
        assert isinstance(tools, list), f"{n}: required_tools must be a list"
        if "Bash" in tools:
            assert fm.get("isolation") == "workspace", (
                f"{n}: holds Bash but isolation is {fm.get('isolation')!r}, not 'workspace'"
            )


def test_ceo_and_resume_are_read_only_acceptEdits():
    for n in sorted(READ_ONLY):
        assert n in MM, f"{n} is missing — see test_nine_skills_exist"
        fm = _frontmatter(n)
        assert fm.get("privilege_class") == "read-only", (
            f"{n}: privilege_class must be 'read-only', got {fm.get('privilege_class')!r}"
        )
        assert fm.get("permission_mode") == "acceptEdits", (
            f"{n}: permission_mode must be 'acceptEdits', got {fm.get('permission_mode')!r}"
        )
        tools = set(fm.get("required_tools") or [])
        assert not (tools & {"Write", "Edit"}), (
            f"{n}: read-only + dispatch skill must not require Write/Edit: {sorted(tools)}"
        )


def test_models_are_in_gateway_alias_table():
    try:
        from src.gateway.telegram_bot import _MODEL_ALIASES
    except Exception as exc:  # pragma: no cover - env without the gateway deps
        pytest.skip(f"gateway alias table not importable: {exc!r}")
    valid = set(_MODEL_ALIASES.values())
    for n in MM:
        for model in _models_of(_frontmatter(n)):
            assert model in valid, (
                f"{n}: model {model!r} not in the gateway alias table {sorted(valid)}"
            )
