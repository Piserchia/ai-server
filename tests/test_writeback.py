"""
Writeback classifier — new path cases.

Covers the extensions to `_is_doc_path()` added for proposal
a164301b (2026-10-05): agent-config directories and top-level AGENTS.md
should classify as doc paths so the runner stops spawning `_writeback`
jobs on sessions whose only "code" diffs are `.codex/agents/*.toml`,
`.agents/skills/*.md`, `.claude/agents/*`, and `AGENTS.md`.

Older classifier cases live alongside the pure-function suite in
`tests/test_pure_functions.py::TestWritebackClassifier`.

Run: pipenv run pytest tests/test_writeback.py -v
"""

from __future__ import annotations

import pytest

from src.runner import writeback


class TestIsDocPathNewRules:
    """New doc-path rules added for proposal a164301b (2026-10-05)."""

    @pytest.mark.parametrize("path", [
        # .codex/agents/ — the atlas-repo pattern observed in 5/23 failed
        # writeback jobs over the preceding 30 days.
        ".codex/agents/alpha-research.toml",
        ".codex/agents/alpha-governor.toml",
        ".codex/agents/atlas-build.toml",
        ".codex/agents/nested/sub.toml",
        # .agents/ — e.g. .agents/skills/*.md
        ".agents/skills/foo.md",
        ".agents/skills/bar/qux.md",
        ".agents/README.md",
        # .claude/agents/ — mirror for Claude-flavored agent configs
        ".claude/agents/code-review.md",
        ".claude/agents/plan.md",
        ".claude/agents/nested/deep.md",
        # top-level AGENTS.md — called out explicitly in the proposal; also
        # covered by the pre-existing top-level-.md rule, so this test pins
        # the behavior so a future refactor can't regress it silently.
        "AGENTS.md",
    ])
    def test_classified_as_doc(self, path: str) -> None:
        assert writeback._is_doc_path(path) is True, (
            f"{path!r} should classify as a doc path (proposal a164301b)"
        )

    @pytest.mark.parametrize("path", [
        # Near-miss negatives: the new rules must not swallow non-agent
        # paths that happen to live near those directory names.
        "codex/agents/foo.toml",         # no leading dot
        "agents/foo.md",                  # no leading dot
        "src/claude/agents/thing.py",     # not a top-level .claude
        "projects/atlas/.codex/agents/x.toml",  # nested under a project
        "nested/AGENTS.md",               # not top-level
    ])
    def test_still_treated_as_code(self, path: str) -> None:
        assert writeback._is_doc_path(path) is False, (
            f"{path!r} should NOT classify as a doc path — only "
            "top-level .codex/agents/, .agents/, .claude/agents/, and "
            "top-level AGENTS.md are documentation."
        )
