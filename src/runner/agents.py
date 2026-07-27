"""
SKILL.md → SDK AgentDefinition compilation (2026-07-27).

Skills remain the single source of truth (MISSION.md objective I: capability
is data, not code). This module maps SkillConfig onto the Agent SDK's
programmatic subagent surface, so a session can delegate in-session via the
Task tool instead of a separate job round-trip.

Opt-in: a skill declares `subagents: [code-review, ...]` in its frontmatter;
`session._build_options` compiles those skills into
ClaudeAgentOptions(agents={...}).

Compilation rules:
  - never compile `god` or any host-isolation skill (break-glass is never
    delegable — INV-18), internal skills (leading `_`, runner-orchestrated),
    `no_llm` skills (scripts, not prompts), or self-references
  - `effort` is validated against the SDK ladder (low|medium|high|xhigh|max);
    unrecognized values fall back to the SDK default. NOTE: `xhigh` IS a
    native SDK value on the pinned line (0.1.81) — it passes through
    unchanged. Do not silently promote it to `max`; server-patch/app-patch
    picked xhigh deliberately to preserve subscription headroom.
  - `permission_mode` passes through when valid; the SDK may still clamp a
    subagent to the parent's mode (bypassPermissions is never widened)
"""

from __future__ import annotations

import logging

from claude_agent_sdk import AgentDefinition

from src.registry.skills import SkillConfig, load as load_skill

logger = logging.getLogger(__name__)

# The SDK effort ladder on the pinned line (0.1.63..<0.2). `xhigh` is native —
# verified against ClaudeAgentOptions.effort / AgentDefinition.effort.
_SDK_EFFORTS = {"low", "medium", "high", "xhigh", "max"}
_SDK_PERMISSION_MODES = {"default", "acceptEdits", "plan", "bypassPermissions"}


def normalize_effort(effort: str | None) -> str | None:
    """Validate a frontmatter/payload effort against the SDK's accepted ladder.

    Returns the value unchanged when valid, else None (SDK default) — never
    promotes one level to another. Pure function.
    """
    if not effort:
        return None
    e = effort.strip().lower()
    if e in _SDK_EFFORTS:
        return e
    logger.warning("unknown effort %r — letting the SDK default apply", effort)
    return None


def skill_to_agent_definition(cfg: SkillConfig, fallback_model: str = "") -> AgentDefinition:
    """Compile one skill into an AgentDefinition. Pure function."""
    permission = (cfg.permission_mode
                  if cfg.permission_mode in _SDK_PERMISSION_MODES else None)
    return AgentDefinition(
        description=cfg.description or f"The `{cfg.name}` skill.",
        prompt=cfg.body,
        tools=list(cfg.required_tools),
        model=cfg.model or (fallback_model or None),
        maxTurns=cfg.max_turns,
        effort=normalize_effort(cfg.effort),
        permissionMode=permission,
    )


def build_subagents(
    cfg: SkillConfig,
    fallback_model: str = "",
    loader=load_skill,
) -> dict[str, AgentDefinition]:
    """Resolve a skill's `subagents:` list into an agents= dict.

    Missing or non-delegable skills are skipped with a warning — a bad
    frontmatter entry must never block the parent session.
    """
    out: dict[str, AgentDefinition] = {}
    for name in cfg.subagents:
        if name == cfg.name:
            logger.warning("skill %s lists itself as a subagent — skipped", cfg.name)
            continue
        if name.startswith("_"):
            logger.warning("internal skill %s cannot be a subagent — skipped", name)
            continue
        sub = loader(name)
        if sub is None:
            logger.warning("skill %s lists unknown subagent %r — skipped", cfg.name, name)
            continue
        if sub.name == "god" or sub.isolation == "host":
            logger.warning("host-tier skill %s is never delegable (INV-18) — skipped", name)
            continue
        if sub.no_llm:
            logger.warning("no_llm skill %s cannot be a subagent — skipped", name)
            continue
        out[name] = skill_to_agent_definition(sub, fallback_model)
    return out
