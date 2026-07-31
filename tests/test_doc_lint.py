"""Documentation lint tests — validates registries stay in sync with actual files."""

import sys
from pathlib import Path

# Add repo root to path so we can import the lint script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import scripts.lint_docs as lint_docs  # noqa: E402
from scripts.lint_docs import (  # noqa: E402
    check_skills_registry,
    check_projects_registry,
    check_runner_context,
    check_phase_plan_status,
    check_module_skills_dirs,
    check_module_graph_imports,
    check_context_files_exist,
    check_skill_sections,
    check_delivery_contracts,
    check_org_charters,
    check_role_privileges,
    check_logger_style,
)


def test_skills_registry_complete():
    warnings = check_skills_registry()
    assert warnings == [], f"Skills not in SKILLS_REGISTRY.md: {warnings}"


def test_projects_registry_complete():
    warnings = check_projects_registry()
    assert warnings == [], f"Projects not in PROJECTS_REGISTRY.md: {warnings}"


def test_runner_context_complete():
    warnings = check_runner_context()
    assert warnings == [], f"Runner files not in CONTEXT.md: {warnings}"


def test_phase_plan_status_current():
    warnings = check_phase_plan_status()
    assert warnings == [], f"Phase plan status mismatches: {warnings}"


def test_module_skills_dirs_seeded():
    warnings = check_module_skills_dirs()
    assert warnings == [], f"Module skills/ dirs missing/incomplete: {warnings}"


def test_module_graph_imports():
    warnings = check_module_graph_imports()
    assert warnings == [], f"Module graph import mismatches: {warnings}"


def test_context_files_exist():
    warnings = check_context_files_exist()
    assert warnings == [], f"Broken context_files declarations: {warnings}"


def test_skill_sections():
    warnings = check_skill_sections()
    assert warnings == [], f"Skill section issues: {warnings}"


def test_delivery_contracts_valid():
    warnings = check_delivery_contracts()
    assert warnings == [], f"Invalid project delivery contracts: {warnings}"


def test_org_charters_claim_every_skill():
    warnings = check_org_charters()
    assert warnings == [], f"Org charter / skill-roster mismatches: {warnings}"


def test_role_privileges_read_only():
    warnings = check_role_privileges()
    assert warnings == [], f"Oversight-role privilege violations: {warnings}"


# ── check_role_privileges rule logic (fixture repos, not the live tree) ─────
#
# The repo-level test above proves the real skills pass; these prove the rules
# themselves fire (and stay silent) correctly, by pointing REPO_ROOT at a
# synthetic tree. No .context/org/ dir is created, so the charter cross-check
# is skipped — these exercise only the frontmatter rules.


def _write_skill(root: Path, name: str, fm_lines: list[str]) -> None:
    d = root / "skills" / name
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(
        "---\n" + "\n".join(fm_lines) + "\n---\n\n# X\n\nbody\n"
    )


def test_oversight_accepts_acceptedits_with_readonly(monkeypatch, tmp_path):
    # The post-2026-07-31 manager shape: acceptEdits + read-only + dispatch tag.
    _write_skill(tmp_path, "mgr", [
        "name: mgr", "role: manager", "permission_mode: acceptEdits",
        "privilege_class: read-only", "tags: [needs-dispatch-mcp]",
    ])
    monkeypatch.setattr(lint_docs, "REPO_ROOT", tmp_path)
    assert lint_docs.check_role_privileges() == []


def test_oversight_accepts_plan_without_dispatch_tag(monkeypatch, tmp_path):
    # Pure reporters (gap-auditor / connectors) stay plan — still valid.
    _write_skill(tmp_path, "conn", [
        "name: conn", "role: connector", "permission_mode: plan",
        "privilege_class: read-only", "tags: [management]",
    ])
    monkeypatch.setattr(lint_docs, "REPO_ROOT", tmp_path)
    assert lint_docs.check_role_privileges() == []


def test_oversight_rejects_bypass_permissions(monkeypatch, tmp_path):
    _write_skill(tmp_path, "mgr", [
        "name: mgr", "role: manager", "permission_mode: bypassPermissions",
        "privilege_class: read-only",
    ])
    monkeypatch.setattr(lint_docs, "REPO_ROOT", tmp_path)
    warnings = lint_docs.check_role_privileges()
    assert len(warnings) == 1 and "acceptEdits" in warnings[0]


def test_oversight_requires_read_only_privilege(monkeypatch, tmp_path):
    _write_skill(tmp_path, "mgr", [
        "name: mgr", "role: manager", "permission_mode: acceptEdits",
        "privilege_class: guarded-writer",
    ])
    monkeypatch.setattr(lint_docs, "REPO_ROOT", tmp_path)
    warnings = lint_docs.check_role_privileges()
    assert len(warnings) == 1 and "privilege_class" in warnings[0]


def test_dispatch_readonly_on_plan_fails(monkeypatch, tmp_path):
    # The 2026-07-30 failure shape: read-only dispatcher stuck on plan mode —
    # its enqueue_job would silently never fire. Role-independent.
    _write_skill(tmp_path, "worker-dispatch", [
        "name: worker-dispatch", "permission_mode: plan",
        "privilege_class: read-only", "tags: [retrospective, needs-dispatch-mcp]",
    ])
    monkeypatch.setattr(lint_docs, "REPO_ROOT", tmp_path)
    warnings = lint_docs.check_role_privileges()
    assert len(warnings) == 1 and "dispatch MCP" in warnings[0]


def test_dispatch_rule_ignores_non_readonly_skills(monkeypatch, tmp_path):
    # god / self-diagnose shape: dispatch tag without the read-only privilege
    # class — outside this rule's scope, whatever the mode.
    _write_skill(tmp_path, "fixer", [
        "name: fixer", "permission_mode: bypassPermissions",
        "tags: [needs-dispatch-mcp]",
    ])
    monkeypatch.setattr(lint_docs, "REPO_ROOT", tmp_path)
    assert lint_docs.check_role_privileges() == []


def test_logger_style_no_structlog_kwargs_on_stdlib():
    warnings = check_logger_style()
    assert warnings == [], f"Stdlib-logger kwarg violations: {warnings}"
