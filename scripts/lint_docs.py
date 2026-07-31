#!/usr/bin/env python3
"""
Documentation linter. Validates that registries, module graphs, and context
files stay in sync with the actual repo structure.

Usage:
    python scripts/lint-docs.py          # prints report, exit 0 if clean
    pipenv run pytest tests/test_doc_lint.py  # same checks as pytest tests

Checks (13):
1. Every skill directory has a row in SKILLS_REGISTRY.md
2. Every project directory has a row in PROJECTS_REGISTRY.md
3. Every src/runner/*.py file is mentioned in runner CONTEXT.md
4. Phase plan status matches SYSTEM.md workstreams
5. Every .context/modules/<x>/ has skills/ with GOTCHAS, PATTERNS, DEBUG stubs
6. Declared module graph deps match actual imports (AST-parsed)
7. Every skill's context_files reference real files
8. Non-internal skills have required body sections (Gotchas, min body length)
9. Skill `isolation` frontmatter values are valid tiers
10. Every project manifest's delivery contract parses + validates
11. Every skill is claimed by exactly one division CHARTER.md (org chart)
12. Oversight roles (manager/ceo/connector/auditor) are read-only + plan mode,
    and charter Role/Privilege columns match skill frontmatter
13. No structlog-style kwargs on stdlib loggers (TypeError at log time)
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


def check_isolation_values() -> list[str]:
    """Every skill's `isolation` frontmatter (if present) must be a valid tier,
    and `host` is reserved for `god` alone (INV-18).

    Valid tiers live in runner/workspaces.py (none | workspace | host).
    `container` was retired 2026-07-27 (docker lane removed — the runtime maps
    it to workspace, but frontmatter should be migrated). An invalid value
    silently degrades to 'none' at runtime — catch it at lint time instead."""
    warnings = []
    skills_dir = REPO_ROOT / "skills"
    if not skills_dir.exists():
        return []

    valid = {"none", "workspace", "host"}
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
        iso = fm.get("isolation")
        if iso is None:
            continue
        if str(iso) == "container":
            warnings.append(
                f"Skill `{child.name}` uses retired isolation `container` "
                f"(docker lane removed 2026-07-27) — change to `workspace`"
            )
        elif str(iso) not in valid:
            warnings.append(
                f"Skill `{child.name}` has invalid isolation `{iso}` "
                f"(valid: {', '.join(sorted(valid))})"
            )
        elif str(iso) == "host" and child.name != "god":
            warnings.append(
                f"Skill `{child.name}` declares isolation `host` but only "
                f"`god` may run host-tier (INV-18)"
            )
    return warnings


def check_org_charters() -> list[str]:
    """Every skill must be claimed by exactly one division CHARTER.md
    (`.context/org/`). This makes the management-hierarchy org chart
    (ORG.md + divisions/*/CHARTER.md) a source of truth that can't drift from
    the actual skill roster — the decentralized "each department owns its
    agents" model. A skill in no charter is an unmanaged orphan; a skill in two
    is an ownership conflict. Planned-but-not-yet-created managers (referenced
    in a charter but with no skill dir) are allowed — they just aren't checked."""
    warnings: list[str] = []
    org_dir = REPO_ROOT / ".context" / "org" / "divisions"
    skills_dir = REPO_ROOT / "skills"
    if not org_dir.exists() or not skills_dir.exists():
        return warnings   # org layer not present yet

    row_re = re.compile(r"^\|\s*`([a-z0-9_-]+)`\s*\|")
    mgr_re = re.compile(r"\*\*Manager:\*\*\s*`([a-z0-9_-]+)`")

    claimed: dict[str, list[str]] = {}
    for charter in sorted(org_dir.glob("*/CHARTER.md")):
        div = charter.parent.name
        text = _read(charter)
        names: set[str] = set()
        for line in text.splitlines():
            m = row_re.match(line)
            if m:
                names.add(m.group(1))
        mm = mgr_re.search(text)
        if mm:
            names.add(mm.group(1))
        for n in names:
            claimed.setdefault(n, []).append(div)

    existing = {c.name for c in sorted(skills_dir.iterdir())
                if c.is_dir() and (c / "SKILL.md").exists()}
    for s in sorted(existing):
        divs = claimed.get(s, [])
        if not divs:
            warnings.append(f"Skill `{s}` is not claimed by any division CHARTER.md "
                            f"(add it to a `.context/org/divisions/<div>/CHARTER.md` roster)")
        elif len(divs) > 1:
            warnings.append(f"Skill `{s}` is claimed by multiple divisions {divs} "
                            f"(a skill belongs to exactly one)")
    return warnings


def check_role_privileges() -> list[str]:
    """The management-hierarchy safety invariant, made structural: any skill
    declaring an oversight role (manager | ceo | connector | auditor) must be
    read-only — `permission_mode: plan` AND `privilege_class: read-only`.
    Managers direct, gated workers execute (MISSION: "batched, proposed,
    reviewed"); an oversight agent that can write is a design violation, so a
    frontmatter edit that widens one must fail lint instead of shipping silent.

    Also cross-checks each charter roster row's Role/Privilege columns against
    the skill's declared frontmatter — ORG.md calls the charters the source of
    truth, so they must not advertise a different contract than the skill runs
    with. Comparison fires only when the frontmatter declares the field
    (workers commonly omit role/privilege_class and are charter-only)."""
    import yaml

    warnings: list[str] = []
    skills_dir = REPO_ROOT / "skills"
    org_dir = REPO_ROOT / ".context" / "org" / "divisions"
    if not skills_dir.exists():
        return warnings

    oversight = {"manager", "ceo", "connector", "auditor"}
    fm_by_skill: dict[str, dict] = {}
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
            fm = yaml.safe_load(parts[1]) or {}
        except Exception:
            continue
        fm_by_skill[child.name] = fm
        role = str(fm.get("role", "") or "")
        if role in oversight:
            if str(fm.get("permission_mode", "") or "") != "plan":
                warnings.append(
                    f"Skill `{child.name}` declares role `{role}` but "
                    f"permission_mode is not `plan` (oversight roles are read-only)"
                )
            if str(fm.get("privilege_class", "") or "") != "read-only":
                warnings.append(
                    f"Skill `{child.name}` declares role `{role}` but "
                    f"privilege_class is not `read-only` (oversight roles "
                    f"propose; gated workers execute)"
                )

    if org_dir.exists():
        row_re = re.compile(
            r"^\|\s*`([a-z0-9_-]+)`\s*\|\s*([a-z-]+)\s*\|\s*([a-z-]+)\s*\|")
        for charter in sorted(org_dir.glob("*/CHARTER.md")):
            for line in _read(charter).splitlines():
                m = row_re.match(line)
                if not m:
                    continue
                name, row_role, row_priv = m.groups()
                fm = fm_by_skill.get(name)
                if fm is None:
                    continue  # planned-but-not-created: allowed (see check_org_charters)
                fm_role = str(fm.get("role", "") or "")
                fm_priv = str(fm.get("privilege_class", "") or "")
                if fm_role and fm_role != row_role:
                    warnings.append(
                        f"Charter `{charter.parent.name}` lists `{name}` as role "
                        f"`{row_role}` but its frontmatter declares `{fm_role}`"
                    )
                if fm_priv and fm_priv != row_priv:
                    warnings.append(
                        f"Charter `{charter.parent.name}` lists `{name}` privilege "
                        f"`{row_priv}` but its frontmatter declares `{fm_priv}`"
                    )
    return warnings


def check_logger_style() -> list[str]:
    """Structlog-style kwargs on a stdlib logger raise TypeError AT LOG TIME
    (`Logger._log() got an unexpected keyword argument ...`) — the call site
    parses fine, passes import, and detonates only when the line executes.
    2026-07-30 incident: `events.py` logged `poll_interval=...` on a
    `logging.getLogger` logger at event-loop startup; latent since Phase 4
    (the crash was silent until `main.main` supervised subsystem exits), it
    left the prod runner unable to start. AST-scan src/: a module whose
    `logger` comes from `logging.getLogger` must not pass keyword args
    (beyond stdlib's exc_info/stack_info/stacklevel/extra) to logger calls.
    Modules using structlog are exempt — structlog accepts arbitrary kwargs."""
    import ast

    warnings: list[str] = []
    allowed = {"exc_info", "stack_info", "stacklevel", "extra"}
    levels = {"debug", "info", "warning", "error", "exception", "critical", "log"}
    src_dir = REPO_ROOT / "src"
    if not src_dir.exists():
        return warnings
    for py in sorted(src_dir.rglob("*.py")):
        text = py.read_text()
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        # Exempt modules that actually IMPORT structlog (its loggers accept
        # arbitrary kwargs). Import-based, not substring: a stdlib-logging file
        # that merely mentions structlog in a comment must still be checked.
        imports_structlog = any(
            (isinstance(n, ast.Import)
             and any(a.name.split(".")[0] == "structlog" for a in n.names))
            or (isinstance(n, ast.ImportFrom)
                and (n.module or "").split(".")[0] == "structlog")
            for n in ast.walk(tree)
        )
        if imports_structlog:
            continue
        stdlib_loggers: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
                f = node.value.func
                if (isinstance(f, ast.Attribute) and f.attr == "getLogger"
                        and isinstance(f.value, ast.Name) and f.value.id == "logging"):
                    for t in node.targets:
                        if isinstance(t, ast.Name):
                            stdlib_loggers.add(t.id)
        if not stdlib_loggers:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            f = node.func
            if (isinstance(f, ast.Attribute) and f.attr in levels
                    and isinstance(f.value, ast.Name) and f.value.id in stdlib_loggers):
                bad = [k.arg for k in node.keywords if k.arg and k.arg not in allowed]
                if bad:
                    rel = py.relative_to(REPO_ROOT)
                    warnings.append(
                        f"{rel}:{node.lineno} stdlib logger called with "
                        f"structlog-style kwargs {bad} — TypeError at log time "
                        f"(use %-style args, or structlog)"
                    )
    return warnings


def check_delivery_contracts() -> list[str]:
    """Every project manifest.yml must parse AND its delivery contract must be
    internally valid (topology/autonomy enums, dev-repo requires dev_repo +
    pull-only, deployable requires gates). Catches a broken delivery block at
    lint time instead of when the runner tries to scope/deploy the project.

    Filesystem existence of a dev_repo is intentionally NOT checked — that is
    machine-specific (a fresh checkout has no dev repos) and belongs to the
    runtime, not doc-lint."""
    from src.registry.manifest import ManifestError, load

    warnings: list[str] = []
    projects_dir = REPO_ROOT / "projects"
    if not projects_dir.exists():
        return warnings
    for child in sorted(projects_dir.iterdir()):
        manifest = child / "manifest.yml"
        if not manifest.exists():
            continue
        try:
            load(manifest)
        except (ManifestError, TypeError, ValueError) as exc:
            warnings.append(f"Project `{child.name}` manifest invalid: {exc}")
    return warnings


def check_skill_sections() -> list[str]:
    """Validate that non-internal skills have required body sections.

    Required for all non-internal skills: ## Gotchas
    Internal skills (name starts with _) are exempt.
    Also warns if body is < 20 lines (too thin to be useful).
    """
    warnings = []
    skills_dir = REPO_ROOT / "skills"
    if not skills_dir.exists():
        return []

    for child in sorted(skills_dir.iterdir()):
        skill_md = child / "SKILL.md"
        if not child.is_dir() or not skill_md.exists():
            continue
        slug = child.name
        if slug.startswith("_"):
            continue  # internal skills exempt

        text = skill_md.read_text()
        if not text.startswith("---"):
            continue
        parts = text.split("---", 2)
        if len(parts) < 3:
            continue
        body = parts[2]
        body_lines = [l for l in body.strip().splitlines() if l.strip()]

        if len(body_lines) < 10:
            warnings.append(
                f"Skill `{slug}` body is only {len(body_lines)} lines (< 10 minimum)"
            )

        # Check for ## Gotchas (case-insensitive)
        has_gotchas = any(
            l.strip().lower().startswith("## gotcha")
            for l in body.splitlines()
        )
        if not has_gotchas:
            warnings.append(
                f"Skill `{slug}` missing '## Gotchas' section"
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
        "skill_sections": check_skill_sections(),
        "isolation_values": check_isolation_values(),
        "delivery_contracts": check_delivery_contracts(),
        "org_charters": check_org_charters(),
        "role_privileges": check_role_privileges(),
        "logger_style": check_logger_style(),
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
