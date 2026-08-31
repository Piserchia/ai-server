"""Fail-closed skill registry + dispatch hardening (2026-08-31).

EVALUATION_2026-08-30 F1: corrupt SKILL.md frontmatter used to silently drop
the whole contract and run the skill on registry defaults (full toolset,
acceptEdits, isolation none); the dispatch MCP accepted kind='god' and
privilege-bearing payload keys from any session.

No network, no DB — pure loader/validator tests against temp skill dirs.
"""

from __future__ import annotations

import pytest

from src.config import settings
from src.registry import skills as reg
from src.runner.mcp_dispatch import (
    _sanitize_payload,
    _validate_enqueue_args,
)


@pytest.fixture()
def skills_dir(tmp_path, monkeypatch):
    # skills_dir is a computed property — patch it on the class.
    monkeypatch.setattr(type(settings), "skills_dir",
                        property(lambda self: tmp_path))
    return tmp_path


def _write_skill(root, name: str, text: str) -> None:
    d = root / name
    d.mkdir()
    (d / "SKILL.md").write_text(text)


GOOD = """---
name: good
description: fine
model: claude-sonnet-4-6
---
body
"""

# The exact real-world failure shape: unquoted `X: y` inside description.
CORRUPT = """---
name: broken
description: Trigger via job description "broken: run me".
---
body
"""


class TestLoadFailClosed:
    def test_missing_skill_returns_none(self, skills_dir):
        assert reg.load("nope") is None

    def test_good_skill_loads(self, skills_dir):
        _write_skill(skills_dir, "good", GOOD)
        cfg = reg.load("good")
        assert cfg is not None and cfg.model == "claude-sonnet-4-6"

    def test_corrupt_frontmatter_raises(self, skills_dir):
        _write_skill(skills_dir, "broken", CORRUPT)
        with pytest.raises(reg.SkillFrontmatterError):
            reg.load("broken")

    def test_non_mapping_frontmatter_raises(self, skills_dir):
        _write_skill(skills_dir, "listy", "---\n- a\n- b\n---\nbody\n")
        with pytest.raises(reg.SkillFrontmatterError):
            reg.load("listy")

    def test_list_all_skips_corrupt_but_keeps_good(self, skills_dir):
        _write_skill(skills_dir, "good", GOOD)
        _write_skill(skills_dir, "broken", CORRUPT)
        names = [c.name for c in reg.list_all()]
        assert "good" in names and "broken" not in names


class TestDispatchHardening:
    def test_god_kind_rejected(self):
        errs = _validate_enqueue_args("god", "do everything")
        assert any("owner-invoked" in e for e in errs)

    def test_god_kind_rejected_case_insensitive(self):
        assert _validate_enqueue_args(" God ", "x")

    def test_normal_kind_accepted(self):
        assert _validate_enqueue_args("atlas-report", "weekly pass") == []

    def test_privileged_payload_keys_stripped(self):
        clean, stripped = _sanitize_payload(
            {"isolation": "host", "permission_mode": "bypassPermissions",
             "project_slug": "atlas"})
        assert clean == {"project_slug": "atlas"}
        assert stripped == ["isolation", "permission_mode"]

    def test_benign_payload_untouched(self):
        clean, stripped = _sanitize_payload({"project_slug": "atlas", "effort": "high"})
        assert clean == {"project_slug": "atlas", "effort": "high"}
        assert stripped == []
