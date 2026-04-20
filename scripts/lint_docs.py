#!/usr/bin/env python3
"""
Documentation linter. Validates that registries, module graphs, and context
files stay in sync with the actual repo structure.

Usage:
    python scripts/lint-docs.py          # prints report, exit 0 if clean
    pipenv run pytest tests/test_doc_lint.py  # same checks as pytest tests

Checks:
1. Every skill directory has a row in SKILLS_REGISTRY.md
2. Every project directory has a row in PROJECTS_REGISTRY.md
3. Every src/runner/*.py file is mentioned in runner CONTEXT.md
4. Phase plan status matches SYSTEM.md workstreams
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Allow importing from src/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Resolve repo root
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent


def _read(path: Path) -> str:
    """Read file content, return empty string if missing."""
    try:
        return path.read_text()
    except FileNotFoundError:
        return ""


def check_skills_registry() -> list[str]:
    """Every skills/ directory with a SKILL.md should appear in SKILLS_REGISTRY.md."""
    registry = _read(REPO_ROOT / ".context" / "SKILLS_REGISTRY.md")
    skills_dir = REPO_ROOT / "skills"
    warnings = []

    if not skills_dir.exists():
        return ["skills/ directory not found"]

    for child in sorted(skills_dir.iterdir()):
        if child.is_dir() and (child / "SKILL.md").exists():
            slug = child.name
            # Check if the slug appears in backticks in the registry
            if f"`{slug}`" not in registry:
                warnings.append(f"Skill `{slug}` exists but not in SKILLS_REGISTRY.md")

    return warnings


def check_projects_registry() -> list[str]:
    """Every projects/ directory (except _ports.yml, README.md) should appear in PROJECTS_REGISTRY.md."""
    registry = _read(REPO_ROOT / ".context" / "PROJECTS_REGISTRY.md")
    projects_dir = REPO_ROOT / "projects"
    warnings = []

    if not projects_dir.exists():
        return ["projects/ directory not found"]

    skip = {"_ports.yml", "README.md", ".DS_Store"}
    for child in sorted(projects_dir.iterdir()):
        if child.name in skip or not child.is_dir():
            continue
        slug = child.name
        if f"`{slug}`" not in registry:
            warnings.append(f"Project `{slug}` exists but not in PROJECTS_REGISTRY.md")

    return warnings


def check_runner_context() -> list[str]:
    """Every .py file in src/runner/ should be mentioned in runner CONTEXT.md."""
    context = _read(REPO_ROOT / ".context" / "modules" / "runner" / "CONTEXT.md")
    runner_dir = REPO_ROOT / "src" / "runner"
    warnings = []

    if not runner_dir.exists():
        return ["src/runner/ directory not found"]

    for py_file in sorted(runner_dir.glob("*.py")):
        if py_file.name == "__init__.py":
            continue
        if py_file.name not in context:
            warnings.append(f"src/runner/{py_file.name} not mentioned in runner CONTEXT.md")

    return warnings


def check_phase_plan_status() -> list[str]:
    """Phase plans should not say 'Not started' if SYSTEM.md says the phase is complete."""
    system_md = _read(REPO_ROOT / ".context" / "SYSTEM.md")
    warnings = []

    for phase_num in range(3, 7):
        plan_path = REPO_ROOT / "docs" / f"PHASE_{phase_num}_PLAN.md"
        plan = _read(plan_path)
        if not plan:
            continue

        # Check if SYSTEM.md marks this phase as complete
        phase_complete = f"Phase {phase_num} ✓" in system_md or f"Phase {phase_num} ✓" in system_md

        # Check if plan still says "Not started"
        plan_says_not_started = re.search(
            r"(?i)\*\*not started\*\*|status.*not started", plan
        )

        if phase_complete and plan_says_not_started:
            warnings.append(
                f"PHASE_{phase_num}_PLAN.md says 'Not started' but SYSTEM.md marks Phase {phase_num} as complete"
            )

    return warnings


def check_module_skills_dirs() -> list[str]:
    """Every module under .context/modules/ should have a skills/ directory
    with GOTCHAS.md, PATTERNS.md, and DEBUG.md — even if only stubs. These
    are the institutional-knowledge targets that PROTOCOL.md directs sessions
    to append to; missing files discourage write-backs."""
    warnings = []
    modules_dir = REPO_ROOT / ".context" / "modules"
    if not modules_dir.exists():
        return [".context/modules/ not found"]

    required = ("GOTCHAS.md", "PATTERNS.md", "DEBUG.md")
    for module_dir in sorted(modules_dir.iterdir()):
        if not module_dir.is_dir():
            continue
        skills_dir = module_dir / "skills"
        if not skills_dir.exists():
            warnings.append(
                f"Module `{module_dir.name}` has no skills/ dir "
                f"(run scripts/seed-module-skills.sh)"
            )
            continue
        for fname in required:
            if not (skills_dir / fname).exists():
                warnings.append(
                    f"Module `{module_dir.name}` missing skills/{fname} "
                    f"(run scripts/seed-module-skills.sh)"
                )
    return warnings


def check_module_graph_imports() -> list[str]:
    """Validate that declared dependencies in SYSTEM.md match actual imports.

    Warns when a Python module under src/ imports from src.X but doesn't
    declare X in its 'Depends on' column in the module graph table.
    """
    from src.context.module_graph import (
        extract_imports,
        module_path_to_shorthand,
        parse_module_graph,
    )

    system_md = _read(REPO_ROOT / ".context" / "SYSTEM.md")
    graph = parse_module_graph(system_md)
    if not graph:
        return ["Could not parse module graph from SYSTEM.md"]

    warnings = []
    src_dir = REPO_ROOT / "src"

    for py_file in sorted(src_dir.rglob("*.py")):
        if py_file.name == "__init__.py":
            continue
        rel = str(py_file.relative_to(REPO_ROOT))
        shorthand = module_path_to_shorthand(rel)

        if shorthand not in graph:
            continue  # module not in graph table (e.g., src/context/module_graph.py itself)

        declared_deps = set(graph[shorthand])
        actual_imports = extract_imports(py_file.read_text())

        for imp in actual_imports:
            if imp in declared_deps:
                continue
            # Check if a parent is declared (e.g., declared 'runner'
            # covers 'runner.session')
            parts = imp.split(".")
            if any(".".join(parts[:i]) in declared_deps for i in range(1, len(parts))):
                continue
            # Check if imp is a package prefix of any declared dep
            # (handles `from src.runner import quota` extracting 'runner'
            # when the module declares 'runner.quota')
            if any(d.startswith(imp + ".") for d in declared_deps):
                continue
            # Skip self-references (module importing from its own package)
            if imp == shorthand or imp.startswith(shorthand + "."):
                continue
            # Skip: import target not in graph at all (likely an external
            # package or a module not tracked in SYSTEM.md)
            if imp not in graph:
                continue
            warnings.append(
                f"`{shorthand}` imports `{imp}` but doesn't declare it in SYSTEM.md"
            )

    return warnings


def check_context_files_exist() -> list[str]:
    """Validate that every skill's context_files reference real files."""
    warnings = []
    skills_dir = REPO_ROOT / "skills"
    if not skills_dir.exists():
        return []

    for child in sorted(skills_dir.iterdir()):
        skill_md = child / "SKILL.md"
        if not child.is_dir() or not skill_md.exists():
            continue
        text = skill_md.read_text()
        if not text.startswith("---"):
            continue
        parts = text.split("---", 2)
        if len(parts) < 3:
            continue
        try:
            import yaml
            fm = yaml.safe_load(parts[1]) or {}
        except Exception:
            continue
        for cf in fm.get("context_files", []):
            if not (REPO_ROOT / cf).exists():
                warnings.append(
                    f"Skill `{child.name}` declares context_file `{cf}` but it does not exist"
                )
    return warnings


def run_all() -> dict[str, list[str]]:
    """Run all checks, return {check_name: [warnings]}."""
    return {
        "skills_registry": check_skills_registry(),
        "projects_registry": check_projects_registry(),
        "runner_context": check_runner_context(),
        "phase_plan_status": check_phase_plan_status(),
        "module_skills_dirs": check_module_skills_dirs(),
        "module_graph_imports": check_module_graph_imports(),
        "context_files_exist": check_context_files_exist(),
    }


def main() -> int:
    results = run_all()
    total_warnings = sum(len(w) for w in results.values())

    for check_name, warnings in results.items():
        status = "PASS" if not warnings else "WARN"
        print(f"[{status}] {check_name}")
        for w in warnings:
            print(f"       {w}")

    print(f"\n{'All clean!' if total_warnings == 0 else f'{total_warnings} warning(s) found.'}")
    return 0 if total_warnings == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
