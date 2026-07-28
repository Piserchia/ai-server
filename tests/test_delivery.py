"""
Runner-side delivery enforcement — pure decision functions (project segregation
Phase B). These are the contract for cwd scoping and deploy authority.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.registry.manifest import Delivery, DeployGate, DeployPolicy
from src.runner import delivery


# ── classify_trigger ────────────────────────────────────────────────────────


class TestClassifyTrigger:
    @pytest.mark.parametrize("cb", [
        "scheduler", "escalation:abc123", "auto-continue:ff", "evaluator:9",
        "eval-fix:1", "learning:22", "writeback:7", "event", "plan:xy",
        "self-diagnose", "cascade",
    ])
    def test_autonomous_prefixes(self, cb):
        assert delivery.classify_trigger(cb) == "autonomous"

    @pytest.mark.parametrize("cb", ["telegram:12345", "god", "user", "eval"])
    def test_human_triggers(self, cb):
        assert delivery.classify_trigger(cb) == "human"

    def test_empty_is_autonomous(self):
        # Unknown origin → stricter default.
        assert delivery.classify_trigger("") == "autonomous"
        assert delivery.classify_trigger(None) == "autonomous"


# ── deploy_permitted ────────────────────────────────────────────────────────


def _deliv(deployable=True, autonomy="gated-auto") -> Delivery:
    return Delivery(
        topology="in-place",
        deployable=deployable,
        deploy=DeployPolicy(autonomy=autonomy,
                            gates=[DeployGate(kind="healthcheck", path="/", expect=200)]),
    )


class TestDeployPermitted:
    def test_not_deployable_always_refuses(self):
        v = delivery.deploy_permitted(_deliv(deployable=False), "human")
        assert v.decision is delivery.DeployDecision.refuse

    def test_gated_auto_allows_anything(self):
        for trig in ("human", "autonomous"):
            assert delivery.deploy_permitted(_deliv(autonomy="gated-auto"), trig).decision \
                is delivery.DeployDecision.allow

    def test_manual_only_human_allowed_autonomous_refused(self):
        d = _deliv(autonomy="manual-only")
        assert delivery.deploy_permitted(d, "human").decision is delivery.DeployDecision.allow
        assert delivery.deploy_permitted(d, "autonomous").decision is delivery.DeployDecision.refuse

    def test_human_approval_human_allowed_autonomous_needs_approval(self):
        d = _deliv(autonomy="human-approval")
        assert delivery.deploy_permitted(d, "human").decision is delivery.DeployDecision.allow
        assert delivery.deploy_permitted(d, "autonomous").decision \
            is delivery.DeployDecision.needs_approval


# ── is_deploy_skill ─────────────────────────────────────────────────────────


class TestIsDeploySkill:
    def test_generic_and_suffix(self):
        assert delivery.is_deploy_skill("project-redeploy", None)
        assert delivery.is_deploy_skill("atlas-redeploy", None)

    def test_manifest_declared_skill(self):
        d = Delivery(deploy=DeployPolicy(skill="atlas-ship"))
        assert delivery.is_deploy_skill("atlas-ship", d)

    def test_non_deploy_skill(self):
        assert not delivery.is_deploy_skill("app-patch", None)
        assert not delivery.is_deploy_skill("", None)


# ── resolve_delivery_cwd ────────────────────────────────────────────────────


class TestResolveDeliveryCwd:
    def test_in_place_stays_on_runtime_clone(self, tmp_path):
        runtime = tmp_path / "projects" / "demo"
        cwd, scoped = delivery.resolve_delivery_cwd(
            runtime, Delivery(topology="in-place"), is_deploy=False)
        assert cwd == runtime and scoped is False

    def test_legacy_none_delivery_stays_on_runtime_clone(self, tmp_path):
        runtime = tmp_path / "projects" / "demo"
        cwd, scoped = delivery.resolve_delivery_cwd(runtime, None, is_deploy=False)
        assert cwd == runtime and scoped is False

    def test_dev_repo_scopes_non_deploy_to_dev_repo(self, tmp_path):
        dev = tmp_path / "devrepo"
        dev.mkdir()
        runtime = tmp_path / "projects" / "demo"
        d = Delivery(topology="dev-repo", dev_repo=str(dev), runtime_clone="pull-only")
        cwd, scoped = delivery.resolve_delivery_cwd(runtime, d, is_deploy=False)
        assert cwd == dev and scoped is True

    def test_dev_repo_deploy_job_uses_runtime_clone(self, tmp_path):
        dev = tmp_path / "devrepo"
        dev.mkdir()
        runtime = tmp_path / "projects" / "demo"
        d = Delivery(topology="dev-repo", dev_repo=str(dev), runtime_clone="pull-only")
        cwd, scoped = delivery.resolve_delivery_cwd(runtime, d, is_deploy=True)
        assert cwd == runtime and scoped is False

    def test_dev_repo_missing_falls_back_to_runtime(self, tmp_path):
        runtime = tmp_path / "projects" / "demo"
        d = Delivery(topology="dev-repo", dev_repo=str(tmp_path / "nope"),
                     runtime_clone="pull-only")
        cwd, scoped = delivery.resolve_delivery_cwd(runtime, d, is_deploy=False)
        assert cwd == runtime and scoped is False
