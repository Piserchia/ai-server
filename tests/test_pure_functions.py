"""
Tests for pure functions. No DB, no Redis, no SDK — just logic.

Run: pipenv run pytest tests/test_pure_functions.py -v
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

import pytest

from src.gateway.telegram_bot import parse_flags
from src.runner import router, writeback


# ── Router tests ────────────────────────────────────────────────────────────


class TestRouter:
    @pytest.mark.parametrize("description,expected_skill", [
        # Coding intent → app-patch
        ("fix the bug in market-tracker", "app-patch"),
        ("write me a Python function to parse CSV", "app-patch"),
        ("implement a FastAPI endpoint for user login", "app-patch"),
        ("refactor the auth module", "app-patch"),
        ("debug this traceback: TypeError: 'NoneType' is not iterable", "app-patch"),
        ("code me up a quick script to rename files", "app-patch"),

        # Projects
        ("new project: NBA live scores widget", "new-project"),
        ("scaffold me a blog", "new-project"),
        ("spin up a dashboard for crypto prices", "new-project"),

        # Research
        ("research the 2026 NBA trade deadline", "research-report"),
        ("summarize the latest Fed decision", "research-report"),
        ("deep research on quantum computing", "research-deep"),

        # Diagnose
        ("why did the bot crash yesterday", "self-diagnose"),
        ("investigate the stuck jobs", "self-diagnose"),
        ("what went wrong with the last deploy", "self-diagnose"),

        # Meta
        ("new skill: daily BTC price summary", "new-skill"),
        ("brainstorm startup ideas", "idea-generation"),

        # Generic (no match) → None
        ("hello there", None),
        ("tell me about yourself", None),
    ])
    def test_routing(self, description: str, expected_skill: str | None) -> None:
        assert router.route(description) == expected_skill

    def test_empty_description_goes_to_chat(self) -> None:
        assert router.route("") == "chat"

    def test_case_insensitive(self) -> None:
        assert router.route("RESEARCH THE NBA TRADE DEADLINE") == "research-report"


# ── Flag parser tests ───────────────────────────────────────────────────────


class TestFlagParser:
    def test_no_flags(self) -> None:
        desc, flags = parse_flags("fix the bug")
        assert desc == "fix the bug"
        assert flags == {}

    def test_single_flag(self) -> None:
        desc, flags = parse_flags("--model=opus fix the bug")
        assert desc == "fix the bug"
        assert flags == {"model": "claude-opus-4-7"}

    def test_multiple_flags(self) -> None:
        desc, flags = parse_flags("--model=sonnet --effort=high do the thing")
        assert desc == "do the thing"
        assert flags["model"] == "claude-sonnet-4-6"
        assert flags["effort"] == "high"

    def test_model_alias_expansion(self) -> None:
        assert parse_flags("--model=opus x")[1]["model"] == "claude-opus-4-7"
        assert parse_flags("--model=sonnet x")[1]["model"] == "claude-sonnet-4-6"
        assert parse_flags("--model=haiku x")[1]["model"] == "claude-haiku-4-5-20251001"
        assert parse_flags("--model=opus-4-6 x")[1]["model"] == "claude-opus-4-6"

    def test_invalid_effort_dropped(self) -> None:
        _, flags = parse_flags("--effort=bogus x")
        assert "effort" not in flags

    def test_invalid_permission_dropped(self) -> None:
        _, flags = parse_flags("--permission=yolo x")
        assert "permission_mode" not in flags

    def test_unknown_flag_stops_parsing(self) -> None:
        # Unknown flag lands in description; later flags not parsed
        desc, flags = parse_flags("--unknown=x --model=opus real task")
        assert "--unknown=x" in desc
        assert "model" not in flags

    def test_flags_only_no_description(self) -> None:
        desc, flags = parse_flags("--model=opus")
        assert desc == ""
        assert flags["model"] == "claude-opus-4-7"


# ── Writeback classifier tests ──────────────────────────────────────────────


class TestWritebackClassifier:
    @pytest.mark.parametrize("path,expected", [
        # Docs — should NOT trigger writeback
        (".context/SYSTEM.md", True),
        (".context/modules/runner/CONTEXT.md", True),
        (".context/modules/runner/CHANGELOG.md", True),
        ("skills/chat/SKILL.md", True),
        ("skills/research-report/SKILL.md", True),
        ("skills/research-report/templates/README.md", True),
        ("docs/assistant-system-design.md", True),
        ("README.md", True),      # top-level .md
        ("MISSION.md", True),
        ("SERVER.md", True),
        ("CLAUDE.md", True),

        # Code / config — SHOULD trigger writeback
        ("src/runner/main.py", False),
        ("src/models.py", False),
        ("alembic/versions/002_new.py", False),
        ("scripts/bootstrap.sh", False),
        (".env.example", False),
        ("pyproject.toml", False),
        ("projects/nba-scores/src/app.py", False),  # project code
    ])
    def test_is_doc_path(self, path: str, expected: bool) -> None:
        assert writeback._is_doc_path(path) == expected

    def test_needs_writeback_no_git(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            needs, modified = writeback.needs_writeback(Path(td))
            assert needs is False
            assert modified == []

    def test_needs_writeback_clean_repo(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            cwd = Path(td)
            subprocess.run(["git", "init", "-q"], cwd=td, check=True)
            subprocess.run(["git", "config", "user.email", "t@t"], cwd=td, check=True)
            subprocess.run(["git", "config", "user.name", "t"], cwd=td, check=True)
            (cwd / "README.md").write_text("x")
            subprocess.run(["git", "add", "-A"], cwd=td, check=True)
            subprocess.run(["git", "commit", "-qm", "i"], cwd=td, check=True)
            needs, modified = writeback.needs_writeback(cwd)
            assert needs is False
            assert modified == []

    def test_needs_writeback_code_modified_no_changelog(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            cwd = Path(td)
            subprocess.run(["git", "init", "-q"], cwd=td, check=True)
            subprocess.run(["git", "config", "user.email", "t@t"], cwd=td, check=True)
            subprocess.run(["git", "config", "user.name", "t"], cwd=td, check=True)
            (cwd / "src").mkdir()
            (cwd / "src" / "thing.py").write_text("x = 1\n")
            needs, modified = writeback.needs_writeback(cwd)
            assert needs is True
            assert "src/thing.py" in modified

    def test_needs_writeback_code_modified_with_changelog(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            cwd = Path(td)
            subprocess.run(["git", "init", "-q"], cwd=td, check=True)
            subprocess.run(["git", "config", "user.email", "t@t"], cwd=td, check=True)
            subprocess.run(["git", "config", "user.name", "t"], cwd=td, check=True)
            (cwd / "src").mkdir()
            (cwd / ".context" / "modules" / "x").mkdir(parents=True)
            (cwd / "src" / "thing.py").write_text("x = 1\n")
            (cwd / ".context" / "modules" / "x" / "CHANGELOG.md").write_text("entry\n")
            needs, _ = writeback.needs_writeback(cwd)
            assert needs is False, "CHANGELOG update should satisfy the check"

    def test_needs_writeback_only_docs_modified(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            cwd = Path(td)
            subprocess.run(["git", "init", "-q"], cwd=td, check=True)
            subprocess.run(["git", "config", "user.email", "t@t"], cwd=td, check=True)
            subprocess.run(["git", "config", "user.name", "t"], cwd=td, check=True)
            (cwd / "README.md").write_text("hello\n")
            needs, _ = writeback.needs_writeback(cwd)
            assert needs is False, "Editing only a top-level .md should not trigger writeback"


# ── Skill config tests ─────────────────────────────────────────────────────


class TestSkillConfig:
    def test_context_files_parsed(self) -> None:
        from src.registry.skills import _parse_frontmatter, SkillConfig
        text = """---
name: test-skill
description: test
context_files: ["docs/Troubleshooting.md", ".context/SYSTEM.md"]
---

Body here.
"""
        fm, body = _parse_frontmatter(text)
        assert fm["context_files"] == ["docs/Troubleshooting.md", ".context/SYSTEM.md"]

    def test_context_files_defaults_empty(self) -> None:
        from src.registry.skills import _parse_frontmatter
        text = """---
name: test-skill
description: test
---

Body here.
"""
        fm, _ = _parse_frontmatter(text)
        assert fm.get("context_files") is None  # absent, defaults to [] in load()


# ── Server directive tests ─────────────────────────────────────────────────


class TestServerDirective:
    def test_chat_gets_minimal_directive(self) -> None:
        from src.registry.skills import SkillConfig
        from src.runner.session import _build_server_directive
        from src.config import settings

        cfg = SkillConfig(name="chat", body="")
        result = _build_server_directive(cfg, settings.server_root)
        assert "No tool use" in result
        assert "SYSTEM.md" not in result

    def test_project_scoped_gets_project_directive(self) -> None:
        from src.registry.skills import SkillConfig
        from src.runner.session import _build_server_directive

        cfg = SkillConfig(name="app-patch", body="")
        result = _build_server_directive(cfg, Path("/projects/market-tracker"))
        assert "market-tracker" in result
        assert "CLAUDE.md" in result

    def test_server_scoped_gets_full_directive(self) -> None:
        from src.registry.skills import SkillConfig
        from src.runner.session import _build_server_directive
        from src.config import settings

        cfg = SkillConfig(name="server-patch", body="")
        result = _build_server_directive(cfg, settings.server_root)
        assert "SYSTEM.md" in result
        assert "CHANGELOG.md" in result

    def test_context_files_appended(self) -> None:
        from src.registry.skills import SkillConfig
        from src.runner.session import _build_server_directive
        from src.config import settings

        cfg = SkillConfig(
            name="self-diagnose", body="",
            context_files=["docs/Troubleshooting.md"],
        )
        result = _build_server_directive(cfg, settings.server_root)
        assert "docs/Troubleshooting.md" in result
        assert "Read these files first" in result
