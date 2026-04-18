"""
Skill registry. Parses the YAML frontmatter from skills/<skill>/SKILL.md so the runner
can resolve model/effort/permission/escalation per skill, before spinning up a session.

A minimal SKILL.md looks like:

    ---
    name: chat
    description: One-shot conversation, no tools.
    model: claude-sonnet-4-6
    effort: low
    permission_mode: default
    required_tools: []
    max_turns: 5
    ---

    # Chat

    <prose instructions here; everything below the closing --- is the system-prompt body>

This module is deliberately tolerant: missing skills, missing frontmatter fields, and
malformed YAML all fall back to sensible defaults (driven by settings.default_model).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from src.config import settings


@dataclass
class SkillConfig:
    name: str
    body: str                          # everything after the closing ---
    model: str = ""                    # "" means "use settings.default_model"
    effort: str = "medium"             # low | medium | high | xhigh | max
    permission_mode: str = "acceptEdits"
    required_tools: list[str] = field(default_factory=lambda: [
        "Read", "Write", "Edit", "Bash", "Glob", "Grep",
        "WebSearch", "WebFetch", "AskUserQuestion",
    ])
    max_turns: int | None = None
    escalation: dict = field(default_factory=dict)
    post_review: dict = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    context_files: list[str] = field(default_factory=list)  # files the session should read first
    no_llm: bool = False               # if True, skill is implemented as a script, runner skips SDK


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Return (frontmatter_dict, body). If no frontmatter, return ({}, full_text)."""
    if not text.startswith("---"):
        return {}, text
    # Split on the second "---" boundary
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    _, raw_yaml, body = parts
    try:
        data = yaml.safe_load(raw_yaml) or {}
    except yaml.YAMLError:
        data = {}
    return (data, body.lstrip("\n"))


def load(name: str) -> SkillConfig | None:
    """Load a skill by directory name. Returns None if not found."""
    path = settings.skills_dir / name / "SKILL.md"
    if not path.exists():
        return None
    fm, body = _parse_frontmatter(path.read_text())
    return SkillConfig(
        name=fm.get("name", name),
        body=body,
        model=fm.get("model", ""),
        effort=fm.get("effort", "medium"),
        permission_mode=fm.get("permission_mode", "acceptEdits"),
        required_tools=fm.get("required_tools",
                              ["Read", "Write", "Edit", "Bash", "Glob", "Grep",
                               "WebSearch", "WebFetch", "AskUserQuestion"]),
        max_turns=fm.get("max_turns"),
        escalation=fm.get("escalation", {}),
        post_review=fm.get("post_review", {}),
        tags=fm.get("tags", []),
        context_files=fm.get("context_files", []),
        no_llm=bool(fm.get("no_llm", False)),
    )


def list_all() -> list[SkillConfig]:
    """All skills, sorted by name. Used by SKILLS_REGISTRY.md generation."""
    if not settings.skills_dir.exists():
        return []
    out: list[SkillConfig] = []
    for child in sorted(settings.skills_dir.iterdir()):
        if child.is_dir() and (child / "SKILL.md").exists():
            cfg = load(child.name)
            if cfg is not None:
                out.append(cfg)
    return out
