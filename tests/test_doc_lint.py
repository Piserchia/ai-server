"""Documentation lint tests — validates registries stay in sync with actual files."""

import sys
from pathlib import Path

import pytest

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
    check_model_pins,
    check_code_server_set,
)
from src.config import settings  # noqa: E402


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


# ── protected bundle (plan T8, 2026-10-21): provider / model pin rules ──────
#
# Three rules the cross-vendor writer slice enforces at runtime
# (runner/session.py:lane_refusal, registry/models.py:resolve) and in its own
# tests (T1/T4); the protected lint is the belt that catches a frontmatter
# edit before a job ever runs. Repo-level tests prove the live tree passes;
# fixture tests prove each rule fires and stays silent correctly.


def test_model_pins_clean():
    warnings = check_model_pins()
    assert warnings == [], f"Model pin violations: {warnings}"


def test_code_server_set_matches_session():
    # The protected lint holds the code-server set of record; session.py's
    # copy must be byte-equal so an INV-4-lane edit cannot widen or shrink it.
    warnings = check_code_server_set()
    assert warnings == [], f"code-server set drift: {warnings}"


def test_code_server_set_is_the_plan_set():
    assert lint_docs.CODE_SERVER_SKILLS == frozenset({
        "server-patch", "server-deploy", "new-skill", "deploy-director",
        "atlas-redeploy", "project-redeploy",
    })


def test_bare_anthropic_pin_on_any_tier_is_fine(monkeypatch, tmp_path):
    _write_skill(tmp_path, "writer", [
        "name: writer", "model: claude-sonnet-4-6", "isolation: none",
    ])
    _write_skill(tmp_path, "unpinned", ["name: unpinned", "isolation: none"])
    monkeypatch.setattr(lint_docs, "REPO_ROOT", tmp_path)
    assert lint_docs.check_model_pins() == []


def test_non_anthropic_pin_requires_workspace_isolation(monkeypatch, tmp_path):
    # Rule 1: a non-Anthropic provider only ever runs on the workspace tier
    # (INV-21(a)); `none` is host-equivalent and `host` is god's alone.
    _write_skill(tmp_path, "codex-writer", [
        "name: codex-writer", "model: codex/gpt-6-luna", "isolation: none",
    ])
    _write_skill(tmp_path, "codex-unset", [
        "name: codex-unset", "model: codex/gpt-6-luna",
    ])
    monkeypatch.setattr(lint_docs, "REPO_ROOT", tmp_path)
    warnings = lint_docs.check_model_pins()
    assert len(warnings) == 2
    assert all("isolation: workspace" in w for w in warnings)
    assert {w.split("`")[1] for w in warnings} == {"codex-writer", "codex-unset"}


def test_non_anthropic_pin_on_workspace_passes(monkeypatch, tmp_path):
    _write_skill(tmp_path, "codex-writer", [
        "name: codex-writer", "model: codex/gpt-6-luna", "isolation: workspace",
    ])
    monkeypatch.setattr(lint_docs, "REPO_ROOT", tmp_path)
    assert lint_docs.check_model_pins() == []


@pytest.mark.parametrize("pin", [
    "codex/no-such-model",     # unknown model for a known provider
    "nope/gpt-6-luna",         # unknown provider
    "claude-haiku-4-5",        # retired Anthropic id (T0) — bare, unknown
    "a/b/c",                   # malformed
])
def test_pin_must_exist_in_models_yml(monkeypatch, tmp_path, pin):
    # Rule 2: provider AND model must be registry entries (C12 fail-closed;
    # the job would be `provider_refused` — catch it at lint time).
    _write_skill(tmp_path, "s", ["name: s", f"model: {pin}", "isolation: workspace"])
    monkeypatch.setattr(lint_docs, "REPO_ROOT", tmp_path)
    warnings = lint_docs.check_model_pins()
    assert len(warnings) == 1 and "models.yml" in warnings[0], warnings


def test_escalation_target_must_exist_in_models_yml(monkeypatch, tmp_path):
    _write_skill(tmp_path, "s", [
        "name: s", "model: claude-sonnet-4-6",
        "escalation:", "  on_failure:", "    model: codex/not-real",
    ])
    monkeypatch.setattr(lint_docs, "REPO_ROOT", tmp_path)
    warnings = lint_docs.check_model_pins()
    assert len(warnings) == 1 and "escalation" in warnings[0] and "models.yml" in warnings[0]


def test_escalation_target_must_be_anthropic(monkeypatch, tmp_path):
    # Rule 4 (T8 review): main.py enqueues the retry with payload.model=<target>
    # and created_by="escalation:<id>"; lane_refusal's owner-origin rule then
    # refuses the override on an Anthropic-pinned skill, so a non-Anthropic
    # target is a retry that can never run. Catch it at lint time.
    _write_skill(tmp_path, "s", [
        "name: s", "model: claude-sonnet-4-6",
        "escalation:", "  on_failure:", "    model: codex/gpt-6-luna",
    ])
    _write_skill(tmp_path, "unpinned", [
        "name: unpinned",
        "escalation:", "  on_failure:", "    model: codex/gpt-6-luna",
    ])
    monkeypatch.setattr(lint_docs, "REPO_ROOT", tmp_path)
    warnings = lint_docs.check_model_pins()
    assert len(warnings) == 2, warnings
    assert all("escalation" in w and "Anthropic by design" in w for w in warnings)
    assert {w.split("`")[1] for w in warnings} == {"s", "unpinned"}


def test_anthropic_escalation_target_is_fine(monkeypatch, tmp_path):
    _write_skill(tmp_path, "s", [
        "name: s", "model: claude-sonnet-4-6",
        "escalation:", "  on_failure:", "    model: claude-opus-5",
    ])
    monkeypatch.setattr(lint_docs, "REPO_ROOT", tmp_path)
    assert lint_docs.check_model_pins() == []


def test_code_server_skill_pinned_to_anthropic_by_setting(monkeypatch, tmp_path):
    # Rule 3 (plan D-A): a code-server skill may pin a non-Anthropic provider
    # only when ROUTER_CODE_SERVER_PROVIDERS lists it — the same setting the
    # session reads, so the pin cannot be relaxed from models.yml alone.
    _write_skill(tmp_path, "server-patch", [
        "name: server-patch", "model: codex/gpt-6-luna", "isolation: workspace",
    ])
    monkeypatch.setattr(lint_docs, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(settings, "router_code_server_providers", "anthropic")
    warnings = lint_docs.check_model_pins()
    assert len(warnings) == 1, warnings
    assert "code-server" in warnings[0] and "ROUTER_CODE_SERVER_PROVIDERS" in warnings[0]
    # The flip is one setting (plan §7 item 6).
    monkeypatch.setattr(settings, "router_code_server_providers", "anthropic, Codex")
    assert lint_docs.check_model_pins() == []


def test_code_server_skill_with_anthropic_pin_is_fine(monkeypatch, tmp_path):
    _write_skill(tmp_path, "server-deploy", [
        "name: server-deploy", "model: claude-opus-5",
    ])
    monkeypatch.setattr(lint_docs, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(settings, "router_code_server_providers", "anthropic")
    assert lint_docs.check_model_pins() == []


def test_code_server_rule_does_not_apply_to_other_skills(monkeypatch, tmp_path):
    _write_skill(tmp_path, "app-patch", [
        "name: app-patch", "model: codex/gpt-6-luna", "isolation: workspace",
    ])
    monkeypatch.setattr(lint_docs, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(settings, "router_code_server_providers", "anthropic")
    assert lint_docs.check_model_pins() == []


def test_code_server_set_check_reports_drift(monkeypatch, tmp_path):
    src = tmp_path / "src" / "runner"
    src.mkdir(parents=True)
    (src / "session.py").write_text(
        "CODE_SERVER_SKILLS: frozenset[str] = frozenset({\n"
        "    'server-patch', 'server-deploy',\n"
        "})\n"
    )
    monkeypatch.setattr(lint_docs, "REPO_ROOT", tmp_path)
    warnings = lint_docs.check_code_server_set()
    assert len(warnings) == 1 and "CODE_SERVER_SKILLS" in warnings[0]


def test_code_server_set_check_reports_a_missing_literal(monkeypatch, tmp_path):
    src = tmp_path / "src" / "runner"
    src.mkdir(parents=True)
    (src / "session.py").write_text("x = 1\n")
    monkeypatch.setattr(lint_docs, "REPO_ROOT", tmp_path)
    warnings = lint_docs.check_code_server_set()
    assert len(warnings) == 1 and "CODE_SERVER_SKILLS" in warnings[0]


def test_run_all_wires_the_t8_checks():
    results = lint_docs.run_all()
    assert "model_pins" in results and "code_server_set" in results
