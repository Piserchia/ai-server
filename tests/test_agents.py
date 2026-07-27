"""
SKILL.md → AgentDefinition compilation contract.
"""

from __future__ import annotations

from src.registry.skills import SkillConfig
from src.runner import agents


def _cfg(**kw) -> SkillConfig:
    base = dict(name="demo", body="Do the demo.", description="A demo skill.")
    base.update(kw)
    return SkillConfig(**base)


class TestNormalizeEffort:
    def test_valid_pass_through(self):
        # xhigh is a native SDK value on the pinned line — must NOT be remapped.
        for e in ("low", "medium", "high", "xhigh", "max"):
            assert agents.normalize_effort(e) == e

    def test_case_and_whitespace_tolerant(self):
        assert agents.normalize_effort(" xHigh ") == "xhigh"

    def test_unknown_and_empty_give_none(self):
        assert agents.normalize_effort("turbo") is None
        assert agents.normalize_effort("") is None
        assert agents.normalize_effort(None) is None


class TestSkillToAgentDefinition:
    def test_field_mapping(self):
        cfg = _cfg(model="claude-opus-4-7", effort="xhigh",
                   permission_mode="plan", required_tools=["Read", "Grep"],
                   max_turns=5)
        d = agents.skill_to_agent_definition(cfg)
        assert d.description == "A demo skill."
        assert d.prompt == "Do the demo."
        assert d.tools == ["Read", "Grep"]
        assert d.model == "claude-opus-4-7"
        assert d.maxTurns == 5
        assert d.effort == "xhigh"
        assert d.permissionMode == "plan"

    def test_fallback_model_and_description(self):
        cfg = _cfg(description="", model="")
        d = agents.skill_to_agent_definition(cfg, fallback_model="claude-sonnet-4-6")
        assert d.model == "claude-sonnet-4-6"
        assert "demo" in d.description

    def test_no_model_anywhere_gives_none(self):
        d = agents.skill_to_agent_definition(_cfg(model=""))
        assert d.model is None

    def test_invalid_permission_mode_dropped(self):
        d = agents.skill_to_agent_definition(_cfg(permission_mode="dontAsk"))
        assert d.permissionMode is None


class TestBuildSubagents:
    def _loader(self, catalog: dict[str, SkillConfig]):
        return lambda name: catalog.get(name)

    def test_resolves_listed_skills(self):
        catalog = {"code-review": _cfg(name="code-review", permission_mode="plan")}
        parent = _cfg(name="server-patch", subagents=["code-review"])
        out = agents.build_subagents(parent, loader=self._loader(catalog))
        assert set(out) == {"code-review"}
        assert out["code-review"].permissionMode == "plan"

    def test_missing_skill_skipped(self):
        parent = _cfg(subagents=["nope"])
        assert agents.build_subagents(parent, loader=self._loader({})) == {}

    def test_god_and_host_tier_never_delegable(self):
        catalog = {
            "god": _cfg(name="god", isolation="host"),
            "hosty": _cfg(name="hosty", isolation="host"),
        }
        parent = _cfg(subagents=["god", "hosty"])
        assert agents.build_subagents(parent, loader=self._loader(catalog)) == {}

    def test_internal_and_no_llm_and_self_skipped(self):
        catalog = {
            "_evaluate": _cfg(name="_evaluate"),
            "scripty": _cfg(name="scripty", no_llm=True),
            "demo": _cfg(name="demo"),
        }
        parent = _cfg(name="demo", subagents=["_evaluate", "scripty", "demo"])
        assert agents.build_subagents(parent, loader=self._loader(catalog)) == {}

    def test_empty_subagents_list(self):
        assert agents.build_subagents(_cfg(), loader=self._loader({})) == {}
