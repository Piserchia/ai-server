"""
Structural contract evals for every skill (fast, no LLM).

Guards against typos and drift in SKILL.md frontmatter that the tolerant runtime
loader would silently paper over (it falls back to defaults on bad values). Reuses
the canonical valid-value sets from the gateway so this test and the command parser
never disagree.

Run: pipenv run pytest tests/test_skill_contracts.py -v
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.config import settings
from src.gateway.telegram_bot import (
    _MODEL_ALIASES,
    _VALID_EFFORTS,
    _VALID_PERMISSIONS,
)
from src.registry.skills import SkillConfig, list_all
from src.runner import router

VALID_MODELS = set(_MODEL_ALIASES.values())

ALL_SKILLS = list_all()
SKILL_IDS = [s.name for s in ALL_SKILLS]


def test_there_are_skills():
    # Guards against a loader/path regression silently yielding an empty list,
    # which would make every parametrized test below vacuously pass.
    assert len(ALL_SKILLS) >= 15


@pytest.fixture(params=ALL_SKILLS, ids=SKILL_IDS)
def skill(request) -> SkillConfig:
    return request.param


class TestSkillContracts:
    def test_name_nonempty(self, skill: SkillConfig):
        assert skill.name and skill.name.strip()

    def test_model_valid(self, skill: SkillConfig):
        # "" is allowed — means "use settings.default_model".
        assert skill.model == "" or skill.model in VALID_MODELS, (
            f"{skill.name}: model {skill.model!r} not in {sorted(VALID_MODELS)}"
        )

    def test_effort_valid(self, skill: SkillConfig):
        assert skill.effort in _VALID_EFFORTS, (
            f"{skill.name}: effort {skill.effort!r} not in {sorted(_VALID_EFFORTS)}"
        )

    def test_permission_mode_valid(self, skill: SkillConfig):
        assert skill.permission_mode in _VALID_PERMISSIONS, (
            f"{skill.name}: permission_mode {skill.permission_mode!r} not in "
            f"{sorted(_VALID_PERMISSIONS)}"
        )

    def test_required_tools_is_list(self, skill: SkillConfig):
        assert isinstance(skill.required_tools, list)

    def test_context_files_exist(self, skill: SkillConfig):
        for cf in skill.context_files:
            assert (settings.server_root / cf).exists(), (
                f"{skill.name}: context_file {cf!r} does not exist"
            )

    def test_escalation_targets_valid(self, skill: SkillConfig):
        on_failure = (skill.escalation or {}).get("on_failure", {})
        model = on_failure.get("model")
        effort = on_failure.get("effort")
        if model is not None:
            assert model in VALID_MODELS, (
                f"{skill.name}: escalation model {model!r} invalid"
            )
        if effort is not None:
            assert effort in _VALID_EFFORTS, (
                f"{skill.name}: escalation effort {effort!r} invalid"
            )

    def test_body_nonempty(self, skill: SkillConfig):
        # The body is the system prompt; an empty one means a broken/omitted skill.
        assert skill.body.strip(), f"{skill.name}: SKILL.md body is empty"


# Skills reached by kind (web app / schedules / runner-internal spawns) rather
# than by router rule. Adding a skill? Either give it a router rule or list it
# here with a comment naming its dispatcher. This is the contract that killed
# the "SKILL.md advertises a trigger nobody implements" class of bug
# (EVALUATION_2026-07-10 §3.6).
KIND_DISPATCHED = {
    "chat": "telegram /chat + JobKind.chat",
    "code-review": "runner post-review sub-agent (review.py)",
    "server-upkeep": "schedule server-upkeep-daily",
    "review-and-improve": "events.py idle-queue trigger",
    "project-update-poll": "per-project schedules",
    "atlas-report-sweep": "schedule atlas-weekly-reports",
    "god": "owner-only, explicit kind",
    "restore": "owner-only, explicit kind",
}


def test_every_skill_is_reachable():
    targets = {skill for _, skill in router._RULES}
    skills_dir = Path(settings.server_root) / "skills"
    for d in sorted(p for p in skills_dir.iterdir() if p.is_dir()):
        name = d.name
        if name.startswith("_"):
            continue  # internal: runner-spawned
        assert name in targets or name in KIND_DISPATCHED, (
            f"skill '{name}' is unreachable: no router rule and not declared "
            f"in KIND_DISPATCHED"
        )
