"""
Module graph parser for .context/SYSTEM.md.

Parses the markdown module graph table into forward (depends-on) and reverse
(depended-on-by) dependency maps. Used by:
- src/runner/session.py — inject dependency context into server directives
- scripts/lint_docs.py — validate declared deps match actual imports
"""

from __future__ import annotations

import ast
import re
from pathlib import Path


def module_path_to_shorthand(path: str) -> str:
    """Convert a file path like 'src/runner/session.py' to shorthand 'runner.session'.

    Root-level modules: 'src/config.py' → 'config'.
    Nested modules: 'src/runner/session.py' → 'runner.session'.
    Non-src paths returned as-is.
    """
    if path.startswith("src/"):
        path = path[4:]
    if path.endswith(".py"):
        path = path[:-3]
    return path.replace("/", ".")


def parse_module_graph(system_md_text: str) -> dict[str, list[str]]:
    """Parse the module graph table from SYSTEM.md text.

    Returns dict mapping module shorthand → list of dependency shorthands.
    Only includes Python modules under src/. Filters out special values
    like '—', 'Everything', external packages, skill references.

    Pure function.
    """
    graph: dict[str, list[str]] = {}

    for line in system_md_text.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue

        cells = [c.strip() for c in line.split("|")]
        # Filter: need at least 5 cells (empty + module + purpose + deps + depby + empty)
        if len(cells) < 5:
            continue

        module_cell = cells[1]
        deps_cell = cells[3]

        # Extract module path from backticks
        m = re.search(r"`([^`]+)`", module_cell)
        if not m:
            continue
        raw_path = m.group(1)

        # Only Python modules under src/
        if not raw_path.startswith("src/") or not raw_path.endswith(".py"):
            continue

        shorthand = module_path_to_shorthand(raw_path)

        # Parse dependencies
        deps: list[str] = []
        if deps_cell and deps_cell != "—":
            for dep in deps_cell.split(","):
                dep = dep.strip()
                if not dep or dep == "—":
                    continue
                # Skip non-module references
                if dep in ("Everything", "Everything that touches state",
                           "(entry point)"):
                    continue
                # Skip external packages (no dots and not a known shorthand pattern)
                if dep.startswith("claude_agent_sdk"):
                    continue
                deps.append(dep)

        graph[shorthand] = deps

    return graph


def reverse_graph(graph: dict[str, list[str]]) -> dict[str, list[str]]:
    """Build reverse dependency map: module → list of modules that depend on it.

    Pure function.
    """
    rev: dict[str, list[str]] = {mod: [] for mod in graph}
    for mod, deps in graph.items():
        for dep in deps:
            if dep in rev:
                rev[dep].append(mod)
            else:
                rev.setdefault(dep, []).append(mod)
    return rev


def extract_imports(source: str) -> set[str]:
    """Extract src.* import targets from Python source code.

    Returns a set of module shorthands (e.g., {'config', 'db', 'runner.session'}).
    Handles both 'from src.X import Y' and 'from src.X.Y import Z' forms.

    Pure function.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()

    imports: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or not node.module:
            continue
        if node.module == "src":
            # "from src import audit_log" → "audit_log"
            for alias in node.names:
                imports.add(alias.name)
        elif node.module.startswith("src."):
            # "from src.runner.session import run_session" → "runner.session"
            # "from src.config import settings" → "config"
            mod = node.module[4:]  # strip "src."
            imports.add(mod)

    return imports


def detect_modules_in_text(text: str, known_modules: set[str]) -> set[str]:
    """Find references to known modules in free-form text.

    Matches module shorthands, file paths (src/runner/session.py),
    and bare filenames (session.py, models.py).

    Pure function.
    """
    found: set[str] = set()
    text_lower = text.lower()

    for mod in known_modules:
        # Check shorthand (e.g., "runner.session")
        if mod in text_lower:
            found.add(mod)
            continue
        # Check file path (e.g., "src/runner/session.py")
        parts = mod.split(".")
        if len(parts) == 1:
            file_path = f"src/{mod}.py"
        else:
            file_path = f"src/{'/'.join(parts)}.py"
        if file_path in text_lower:
            found.add(mod)
            continue
        # Check bare filename (e.g., "session.py")
        bare = parts[-1] + ".py"
        if bare in text_lower:
            found.add(mod)

    return found
