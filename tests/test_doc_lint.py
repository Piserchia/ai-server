"""Documentation lint tests — validates registries stay in sync with actual files."""

import sys
from pathlib import Path

# Add repo root to path so we can import the lint script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.lint_docs import (  # noqa: E402
    check_skills_registry,
    check_projects_registry,
    check_runner_context,
    check_phase_plan_status,
    check_module_skills_dirs,
    check_module_graph_imports,
    check_context_files_exist,
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
