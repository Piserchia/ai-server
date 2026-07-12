"""
LLM routing fallback (P2). The regex router (`runner.router`) promised an LLM
fallback for ambiguous inputs since Phase 4 — this is it, finally.

When the rules don't match, a one-turn Haiku classifier picks the best skill
from the installed catalog (or `plan` for multi-step asks, or `""` for a
generic task). Same invocation pattern as `runner.learning`: cheap model, plan
permission mode, no tools, one turn, never raises.

Routing decisions (rule / llm / fallback) are recorded in the audit log by the
caller (`session._resolve_skill`) so retrospective can measure routing
precision — misroutes are now a tunable metric instead of an anecdote.
"""

from __future__ import annotations

import json
import logging

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    TextBlock,
)

from src.config import settings

logger = logging.getLogger(__name__)

# Skills the LLM may never route to: internal (leading _), break-glass, or
# destructive-without-confirmation lanes. `plan` IS allowed — multi-step asks
# should decompose.
_EXCLUDED = {"god", "restore", "chat"}


ROUTER_SYSTEM_PROMPT = """\
You are the job router for a personal assistant server. You receive one user
request plus a catalog of installed skills (name: description). Pick the ONE
skill whose description best matches the request.

Rules:
- If the request clearly needs MULTIPLE distinct pieces of work (e.g. "add X,
  then update the docs site and schedule a weekly report"), answer "plan".
- If no skill is a confident match, answer "" (empty string) — the server
  runs it as a generic task, which is a safe default.
- NEVER invent a skill name not in the catalog.
- Answer with a single JSON object, nothing else:
  {"skill": "<name-or-plan-or-empty>", "confidence": <0.0-1.0>}
"""


def parse_route_response(text: str, valid_skills: set[str]) -> tuple[str, float]:
    """Parse the classifier output. Pure function.

    Returns ("", 0.0) for anything malformed or not in the valid set —
    fail-open to generic task, never to a wrong skill.
    """
    text = text.strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return "", 0.0
    try:
        obj = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return "", 0.0
    skill = str(obj.get("skill", "") or "")
    try:
        confidence = float(obj.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    if skill and skill not in valid_skills:
        logger.info("llm router proposed unknown skill %r — treating as generic", skill)
        return "", 0.0
    return skill, max(0.0, min(1.0, confidence))


def build_catalog_with_descriptions(entries: list[tuple[str, str]]) -> str:
    """entries: (name, description) pairs. Pure function."""
    return "\n".join(
        f"- {name}: {desc[:160]}" for name, desc in entries
        if not name.startswith("_") and name not in _EXCLUDED
    )


async def llm_route(description: str) -> tuple[str, float]:
    """Route an ambiguous description via Haiku. Returns (skill, confidence).

    ("", 0.0) means generic task. "plan" means decompose first.
    Never raises.
    """
    if not settings.llm_router_enabled:
        return "", 0.0

    try:
        # Late import to avoid registry work at module import time
        from src.registry.skills import list_all
        entries: list[tuple[str, str]] = [
            (cfg.name, _skill_description(cfg.name)) for cfg in list_all()
        ]
        valid = {name for name, _ in entries
                 if not name.startswith("_") and name not in _EXCLUDED}
        valid.add("plan")
        catalog = build_catalog_with_descriptions(entries)
    except Exception as exc:  # noqa: BLE001
        logger.warning("llm router could not build catalog: %s", exc)
        return "", 0.0

    user_prompt = (
        f"Installed skills:\n{catalog}\n\n"
        f"User request:\n{description[:1200]}\n\n"
        "Emit the JSON object now."
    )

    options = ClaudeAgentOptions(
        cwd=str(settings.server_root),
        system_prompt=ROUTER_SYSTEM_PROMPT,
        model="claude-haiku-4-5-20251001",
        effort="low",
        permission_mode="plan",
        allowed_tools=[],
        max_turns=1,
    )

    final_text = ""
    try:
        client = ClaudeSDKClient(options=options)
        async with client:
            await client.query(user_prompt)
            async for message in client.receive_response():
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            final_text += block.text
    except Exception as exc:  # noqa: BLE001
        logger.warning("llm router SDK error: %s", exc)
        return "", 0.0

    return parse_route_response(final_text, valid)


def _skill_description(name: str) -> str:
    """Read a skill's frontmatter description (cheap, cached by OS page cache)."""
    try:
        import yaml
        path = settings.skills_dir / name / "SKILL.md"
        text = path.read_text()
        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) >= 3:
                fm = yaml.safe_load(parts[1]) or {}
                return str(fm.get("description", ""))
    except Exception:  # noqa: BLE001
        pass
    return ""
