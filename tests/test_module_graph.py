"""Unit tests for src/context/module_graph.py pure functions."""

from __future__ import annotations

from src.context.module_graph import (
    detect_modules_in_text,
    extract_imports,
    module_path_to_shorthand,
    parse_module_graph,
    reverse_graph,
)

SAMPLE_SYSTEM_MD = """
## Module graph

| Module | Purpose | Depends on | Depended on by |
|---|---|---|---|
| `src/config.py` | Settings | — | Everything |
| `src/db.py` | Database | config | Everything that touches state |
| `src/models.py` | ORM | — | db, runner, gateway |
| `src/runner/session.py` | Sessions | config, db, models, registry.skills | runner.main |
| `src/runner/main.py` | Entry point | config, db, runner.session | (entry point) |
| `src/registry/skills.py` | Skill loader | config | runner.session |
| `scripts/lint_docs.py` | Lint checks | — | tests/test_doc_lint.py |
"""


class TestModulePathToShorthand:
    def test_root_level(self):
        assert module_path_to_shorthand("src/config.py") == "config"

    def test_nested(self):
        assert module_path_to_shorthand("src/runner/session.py") == "runner.session"

    def test_deep_nested(self):
        assert module_path_to_shorthand("src/context/module_graph.py") == "context.module_graph"

    def test_no_src_prefix(self):
        assert module_path_to_shorthand("scripts/lint_docs.py") == "scripts.lint_docs"

    def test_no_py_suffix(self):
        assert module_path_to_shorthand("src/config") == "config"


class TestParseModuleGraph:
    def test_parses_sample(self):
        graph = parse_module_graph(SAMPLE_SYSTEM_MD)
        assert "config" in graph
        assert graph["config"] == []  # depends on nothing (—)
        assert "db" in graph
        assert graph["db"] == ["config"]
        assert "runner.session" in graph
        assert set(graph["runner.session"]) == {"config", "db", "models", "registry.skills"}

    def test_skips_scripts(self):
        graph = parse_module_graph(SAMPLE_SYSTEM_MD)
        assert "scripts/lint_docs" not in graph
        assert "lint_docs" not in graph

    def test_skips_header_row(self):
        graph = parse_module_graph(SAMPLE_SYSTEM_MD)
        assert "Module" not in graph

    def test_empty_input(self):
        assert parse_module_graph("") == {}

    def test_no_table(self):
        assert parse_module_graph("# Just a heading\n\nSome text.") == {}

    def test_filters_special_values(self):
        graph = parse_module_graph(SAMPLE_SYSTEM_MD)
        # "Everything" should not appear in any deps list
        for deps in graph.values():
            assert "Everything" not in deps
            assert "(entry point)" not in deps


class TestReverseGraph:
    def test_simple(self):
        graph = {"a": ["b", "c"], "b": ["c"], "c": []}
        rev = reverse_graph(graph)
        assert "a" in rev
        assert rev["a"] == []  # nothing depends on a
        assert set(rev["b"]) == {"a"}
        assert set(rev["c"]) == {"a", "b"}

    def test_empty_graph(self):
        assert reverse_graph({}) == {}

    def test_no_deps(self):
        graph = {"a": [], "b": []}
        rev = reverse_graph(graph)
        assert rev["a"] == []
        assert rev["b"] == []


class TestExtractImports:
    def test_from_src_import(self):
        source = "from src import audit_log\nfrom src.config import settings\n"
        imports = extract_imports(source)
        assert "audit_log" in imports
        assert "config" in imports

    def test_nested_import(self):
        source = "from src.runner.session import run_session\n"
        imports = extract_imports(source)
        assert "runner.session" in imports

    def test_ignores_non_src(self):
        source = "from pathlib import Path\nimport json\n"
        assert extract_imports(source) == set()

    def test_ignores_third_party(self):
        source = "from sqlalchemy import select\nfrom claude_agent_sdk import ClaudeSDKClient\n"
        assert extract_imports(source) == set()

    def test_multiple_imports(self):
        source = (
            "from src.config import settings\n"
            "from src.db import async_session\n"
            "from src.runner.quota import is_paused\n"
        )
        imports = extract_imports(source)
        assert imports == {"config", "db", "runner.quota"}

    def test_empty_source(self):
        assert extract_imports("") == set()

    def test_syntax_error(self):
        assert extract_imports("def broken(:\n") == set()

    def test_from_src_dot_import(self):
        source = "from src.runner import quota, router\n"
        imports = extract_imports(source)
        assert "runner" in imports


class TestDetectModulesInText:
    def test_shorthand_match(self):
        modules = {"config", "db", "runner.session"}
        found = detect_modules_in_text("fix the bug in runner.session", modules)
        assert "runner.session" in found

    def test_filename_match(self):
        modules = {"config", "runner.session"}
        found = detect_modules_in_text("edit session.py to add the new hook", modules)
        assert "runner.session" in found

    def test_filepath_match(self):
        modules = {"runner.session"}
        found = detect_modules_in_text("change src/runner/session.py", modules)
        assert "runner.session" in found

    def test_no_match(self):
        modules = {"config", "db"}
        found = detect_modules_in_text("hello world", modules)
        assert found == set()

    def test_case_insensitive(self):
        modules = {"config"}
        found = detect_modules_in_text("update Config.py settings", modules)
        assert "config" in found

    def test_multiple_matches(self):
        modules = {"config", "db", "models"}
        found = detect_modules_in_text("refactor models.py and db.py", modules)
        assert "models" in found
        assert "db" in found
