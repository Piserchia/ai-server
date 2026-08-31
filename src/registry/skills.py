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

import logging
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from src.config import settings

logger = logging.getLogger(__name__)


@dataclass
class SkillConfig:
    name: str
    body: str                          # everything after the closing ---
    description: str = ""              # frontmatter description (router + subagent card)
    model: str = ""                    # "" means "use settings.default_model"
    effort: str = "medium"             # low | medium | high | xhigh | max (xhigh→max at SDK boundary)
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
    isolation: str = "none"            # none | workspace | host ("container" parses → workspace; see runner/workspaces.py)
    subagents: list[str] = field(default_factory=list)  # skills exposed as in-session SDK subagents
    # Management-hierarchy taxonomy (.context/org/) — declarative; the division
    # CHARTER.md is the lint-enforced source of truth for membership.
    role: str = "worker"               # worker | manager | ceo | connector
    division: str = ""                 # executive | delivery | platform-ops | knowledge | atlas
    privilege_class: str = ""          # read-only | content | guarded-writer | prod-operator | break-glass


class SkillFrontmatterError(ValueError):
    """A SKILL.md frontmatter block exists but cannot be parsed.

    Fail CLOSED (2026-08-31, EVALUATION_2026-08-30 F1.6): before this, a
    YAML error silently dropped the whole frontmatter and the skill ran on
    registry defaults — full default toolset, acceptEdits, isolation none,
    wrong model. Three atlas skills ran that way for weeks undetected.
    """


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Return (frontmatter_dict, body). If no frontmatter, return ({}, full_text).

    Raises SkillFrontmatterError if a frontmatter block is present but does
    not parse to a YAML mapping — never silently degrade to defaults.
    """
    if not text.startswith("---"):
        return {}, text
    # Split on the second "---" boundary
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    _, raw_yaml, body = parts
    try:
        data = yaml.safe_load(raw_yaml) or {}
    except yaml.YAMLError as exc:
        raise SkillFrontmatterError(f"frontmatter is not valid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise SkillFrontmatterError(
            f"frontmatter parsed to {type(data).__name__}, expected a mapping")
    return (data, body.lstrip("\n"))


def load(name: str) -> SkillConfig | None:
    """Load a skill by directory name. Returns None if not found.

    Raises SkillFrontmatterError if the skill exists but its frontmatter is
    corrupt — callers must fail the job, not run it on defaults.
    """
    path = settings.skills_dir / name / "SKILL.md"
    if not path.exists():
        return None
    fm, body = _parse_frontmatter(path.read_text())
    # Validate context_files exist
    for cf in fm.get("context_files", []):
        cf_path = settings.server_root / cf
        if not cf_path.exists():
            logger.warning(
                "Skill '%s' declares context_file '%s' but it does not exist",
                name, cf,
            )
    return SkillConfig(
        name=fm.get("name", name),
        body=body,
        description=str(fm.get("description", "") or ""),
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
        isolation=str(fm.get("isolation", "none")),
        subagents=list(fm.get("subagents", []) or []),
        role=str(fm.get("role", "worker") or "worker"),
        division=str(fm.get("division", "") or ""),
        privilege_class=str(fm.get("privilege_class", "") or ""),
    )


def list_all() -> list[SkillConfig]:
    """All skills, sorted by name. Used by SKILLS_REGISTRY.md generation."""
    if not settings.skills_dir.exists():
        return []
    out: list[SkillConfig] = []
    for child in sorted(settings.skills_dir.iterdir()):
        if child.is_dir() and (child / "SKILL.md").exists():
            try:
                cfg = load(child.name)
            except SkillFrontmatterError as exc:
                # Listing must not crash registry generation on one bad file,
                # but the error is loud; execution paths (load via
                # session._resolve_skill) still fail closed.
                logger.error("skill '%s' has corrupt frontmatter — excluded "
                             "from listing: %s", child.name, exc)
                continue
            if cfg is not None:
                out.append(cfg)
    return out
