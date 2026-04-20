"""
Route a free-form description to a skill. Rules first (instant, free); LLM fallback
via the `route` skill for ambiguous inputs.

Keep rules narrow and honest. When a rule doesn't match confidently, fall through to
None (generic task — uses full tool set + global default model).

Coding intent → `app-patch` → Opus 4.7 / high via skill frontmatter.
"""

from __future__ import annotations

import re


# Rule format: (pattern, skill_name). First match wins.
# Patterns are lowercased regex fragments run against the lowercased description.
_RULES: list[tuple[str, str]] = [
    # ── Coding intent (routes to app-patch which defaults to Opus 4.7 / high) ──
    (r"\b(write|implement|build|refactor|fix|debug|optimize|add|update|patch|rewrite)\s+"
     r".*\b(function|class|method|module|script|endpoint|test|tests|bug|feature|"
     r"api|handler|route|model|migration|schema|query|component|hook)\b", "app-patch"),
    # Action verb + "app" or project-like noun (catches "update the bingo app to...")
    (r"\b(fix|update|patch|add|modify|change|upgrade)\s+.*\b(app|project|site|dashboard|page)\b",
     "app-patch"),
    (r"\b(python|typescript|javascript|rust|go|sql|bash|fastapi|react|sqlalchemy)\b.*"
     r"\b(script|function|code|app|service)\b", "app-patch"),
    (r"\bcode (me |up |)\b", "app-patch"),
    (r"\b(typeerror|valueerror|nameerror|attributeerror|keyerror|indexerror|"
     r"runtimeerror|stack trace|traceback|segfault)\b", "app-patch"),

    # ── Code review ──
    (r"\b(review|code review|review (the |this |my )?diff)\b", "code-review"),

    # ── Project evaluation ──
    (r"\b(evaluate|assess|document|onboard)\s+(project|app)\b", "project-evaluate"),

    # ── Projects ──
    (r"\bnew project[:\s]", "new-project"),
    (r"\b(scaffold|create a project|make me an app|spin up)\b", "new-project"),

    # ── Diagnosis (different from patching — investigate, not fix) ──
    (r"\b(why (did|is|isn't)|what (went wrong|happened|broke))\b", "self-diagnose"),
    (r"\b(diagnose|investigate)\b", "self-diagnose"),

    # ── Skills (meta) — must come BEFORE research rules so
    #    "new skill: daily BTC summary" doesn't match "summary" first
    (r"\bnew skill[:\s]", "new-skill"),
    (r"\badd a skill\b", "new-skill"),

    # ── Research ──
    (r"\bdeep (research|dive|analysis)\b", "research-deep"),
    (r"\b(research|summarize|summary|report on|weekly update on|market summary)\b",
     "research-report"),

    # ── Restore ──
    (r"\brestore\b", "restore"),

    # ── Server ──
    (r"\bserver:", "server-patch"),
    (r"\bupdate (the )?(server|runner|bot|web gateway)\b", "server-patch"),

    # ── Ideas ──
    (r"\b(brainstorm|ideas for|generate ideas|idea generation)\b", "idea-generation"),

    # ── Retrospective ──
    (r"\b(retrospective|audit the system|review (my|the) (system|server|projects))\b",
     "review-and-improve"),
]


def route(description: str) -> str | None:
    """
    Return a skill name if a rule matches confidently, or None for generic task.
    Never raises.
    """
    if not description:
        return "chat"
    text = description.strip().lower()
    for pattern, skill in _RULES:
        if re.search(pattern, text):
            return skill
    return None
