"""T9 of the cross-vendor writer slice — docs, registries, runbook stay in sync.

Pure file-content checks (no network, no DB, no SDK). `scripts/lint_docs.py`
is a protected path, so the slice-specific documentation contract lives here:

- every file under `src/runner/executors/` is named in the runner CONTEXT.md
  (the linter's `check_runner_context` only globs the top level);
- the SYSTEM.md module graph carries rows for the two new modules;
- INDEX.md and docs/README.md point at the slice plan;
- TROUBLESHOOTING.md has a symptom for each failure mode the plan names;
- the cut spec's deferred items 1/9/10 are annotated as reopened;
- the runner CONTEXT.md no longer carries pre-dispatch "not yet" notes;
- the db CONTEXT.md lists the audit kinds the slice added;
- each touched module's CHANGELOG records T9.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
PLAN = "docs/superpowers/plans/2026-10-21-cross-vendor-writer-slice.md"
CUT_SPEC = REPO_ROOT / "docs/superpowers/specs/2026-10-05-observability-and-trading-unblock-design.md"


def _read(rel: str) -> str:
    return (REPO_ROOT / rel).read_text()


# --- registries -----------------------------------------------------------


def test_runner_context_names_every_executor_module():
    context = _read(".context/modules/runner/CONTEXT.md")
    executors = sorted((REPO_ROOT / "src/runner/executors").glob("*.py"))
    assert executors, "src/runner/executors/ is empty"
    missing = [
        f"src/runner/executors/{p.name}" for p in executors
        if f"src/runner/executors/{p.name}" not in context
    ]
    assert missing == [], f"executor modules not in runner CONTEXT.md: {missing}"


@pytest.mark.parametrize(
    "module", ["src/runner/executors/codex_cli.py", "src/registry/models.py"],
)
def test_system_module_graph_has_a_row(module: str):
    system = _read(".context/SYSTEM.md")
    assert re.search(rf"^\| `{re.escape(module)}` \|", system, re.M), (
        f"{module} has no module-graph row in SYSTEM.md"
    )


def test_system_workstreams_reflect_the_slice():
    system = _read(".context/SYSTEM.md")
    assert "cross-vendor-writer-slice" in system, (
        "SYSTEM.md's live-workstreams list does not mention the slice plan"
    )
    assert "implementation R0\n  not started." not in system, (
        "SYSTEM.md still says the model-router implementation is not started"
    )


def test_index_and_readme_point_at_the_slice_plan():
    for rel in (".context/INDEX.md", "docs/README.md"):
        assert PLAN.split("docs/", 1)[1] in _read(rel) or PLAN in _read(rel), (
            f"{rel} has no row for {PLAN}"
        )


def test_index_and_readme_no_longer_call_cross_vendor_deferred_without_caveat():
    # Both docs said the cross-vendor machinery is "deferred, not planned";
    # after 2026-10-21 that sentence needs the reopening next to it.
    for rel in (".context/INDEX.md", "docs/README.md"):
        text = _read(rel)
        for m in re.finditer(r"deferred, not planned", text):
            window = text[m.start(): m.start() + 400]
            assert "2026-10-21" in window, (
                f"{rel}: 'deferred, not planned' at {m.start()} lacks the 2026-10-21 reopening note"
            )


# --- runbook / troubleshooting --------------------------------------------


@pytest.mark.parametrize(
    "needle",
    [
        "provider_refused",
        "review_blocked",
        "codex not found",
        "codex exec",       # the hang symptom (stdin)
        "auth_expired",
        "job_held",
    ],
)
def test_troubleshooting_has_a_symptom_heading_for(needle: str):
    headings = [
        line for line in _read("docs/TROUBLESHOOTING.md").splitlines()
        if line.startswith("## Symptom:")
    ]
    assert any(needle.lower() in h.lower() for h in headings), (
        f"no '## Symptom:' heading in docs/TROUBLESHOOTING.md mentions {needle!r}"
    )


def test_troubleshooting_names_the_device_auth_relogin_and_codex_bin():
    text = _read("docs/TROUBLESHOOTING.md")
    assert "codex login --device-auth" in text
    assert "CODEX_BIN" in text
    assert "stdin" in text


# --- the cut spec's deferred list -----------------------------------------


@pytest.mark.parametrize("item", [1, 9, 10])
def test_cut_spec_deferred_item_annotated_as_reopened(item: int):
    text = CUT_SPEC.read_text()
    section = text.split("## 14) Deferred", 1)[1].split("## 15)", 1)[0]
    m = re.search(rf"^{item}\. \*\*.*$", section, re.M)
    assert m, f"item {item} not found in the cut spec's §14"
    assert "reopened 2026-10-21" in m.group(0), (
        f"cut spec §14 item {item} is not annotated 'reopened 2026-10-21'"
    )


# --- module context docs ----------------------------------------------------


@pytest.mark.parametrize(
    "stale",
    [
        "declared in T1, not yet consumed",
        "Not called by `run_session` until T4",
    ],
)
def test_runner_context_has_no_stale_pre_dispatch_note(stale: str):
    assert stale not in _read(".context/modules/runner/CONTEXT.md")


def test_runner_context_documents_codex_run_as_user_setting():
    assert "CODEX_RUN_AS_USER" in _read(".context/modules/runner/CONTEXT.md")


@pytest.mark.parametrize(
    "kind",
    [
        "provider_selected",
        "provider_refused",
        "executor_started",
        "turn_completed",
        "executor_error",
        "merge_gate_verdict",
        "merge_gate_skipped",
        "merge_gate_refused",
        "workspace_published",
    ],
)
def test_db_context_lists_the_slice_audit_kinds(kind: str):
    docstring = _read("src/audit_log.py")
    assert f"- {kind}:" in docstring, f"{kind} is not in the audit_log.py docstring"
    assert f"`{kind}`" in _read(".context/modules/db/CONTEXT.md"), (
        f"db CONTEXT.md's audit-log section does not list `{kind}`"
    )


@pytest.mark.parametrize("module", ["runner", "gateway", "registry", "db"])
def test_changelog_records_t9(module: str):
    changelog = _read(f".context/modules/{module}/CHANGELOG.md")
    assert re.search(r"^## 2026-10-21 — T9", changelog, re.M), (
        f"{module} CHANGELOG.md has no 2026-10-21 T9 entry"
    )


def test_plan_t9_section_records_implementation():
    plan = _read(PLAN)
    t9 = plan.split("### T9", 1)[1].split("### T10", 1)[0]
    assert "Implemented 2026-10-21" in t9
