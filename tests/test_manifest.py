"""
Project manifest schema + delivery contract (2026-07-27).

The delivery block is the machine-readable contract the runner enforces
(cwd scoping, pull-only guard, deploy authority), so these tests are the
contract for that enforcement — plus a regression guard for the loader, which
TypeError'd on every live manifest before 2026-07-27.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from src.registry.manifest import (
    Delivery,
    DeployGate,
    DeployPolicy,
    Manifest,
    ManifestError,
    load,
)


def _write(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "manifest.yml"
    p.write_text(textwrap.dedent(body))
    return p


BASE = """\
slug: demo
name: Demo
type: service
subdomain: demo
port: 8999
start_command: "run"
description: A demo.
"""


# ── loader tolerance (the regression the loader had) ────────────────────────


class TestLoaderTolerance:
    def test_unknown_top_level_keys_ignored(self, tmp_path):
        # mission/platforms/web_strategy/env_required/services are read by the
        # yq shell tooling, not the Python model — must not be fatal.
        p = _write(tmp_path, BASE + textwrap.dedent("""\
            mission: "big things"
            web_strategy: native-web
            platforms:
              primary: ios
            env_required: [SECRET]
            services:
              - name: worker
                start_command: "./w"
            """))
        m = load(p)
        assert m.slug == "demo" and m.type == "service"

    def test_missing_delivery_derives_inplace(self, tmp_path):
        m = load(_write(tmp_path, BASE))
        assert m.delivery.topology == "in-place"
        assert m.delivery.runtime_clone == "writable"

    def test_derived_deployable_requires_healthcheck(self, tmp_path):
        # No healthcheck → no implicit gate → not auto-deployable.
        m = load(_write(tmp_path, BASE))
        assert m.delivery.deployable is False
        # With a healthcheck → implicit gate → deployable.
        m2 = load(_write(tmp_path, BASE + "healthcheck: /healthz\n"))
        assert m2.delivery.deployable is True
        assert m2.delivery.deploy.gates[0].kind == "healthcheck"


# ── dev-repo topology ───────────────────────────────────────────────────────


DEVREPO = BASE + textwrap.dedent("""\
    delivery:
      topology: dev-repo
      dev_repo: ~/Documents/repos/demo
      runtime_clone: pull-only
      deployable: true
      deploy:
        autonomy: gated-auto
        gates:
          - kind: test
            cmd: "pytest -q"
          - kind: build
            cmd: "npm run build"
            when_paths: ["web/"]
          - kind: healthcheck
            path: /healthz
            expect: 200
        services: [demo]
    """)


class TestDevRepoTopology:
    def test_parses_full_contract(self, tmp_path):
        m = load(_write(tmp_path, DEVREPO))
        d = m.delivery
        assert d.topology == "dev-repo"
        assert d.is_pull_only
        assert d.dev_repo_path == Path.home() / "Documents/repos/demo"
        assert [g.kind for g in d.deploy.gates] == ["test", "build", "healthcheck"]
        assert d.deploy.gates[1].when_paths == ["web/"]
        assert d.deploy.services == ["demo"]

    def test_dev_repo_required(self, tmp_path):
        body = DEVREPO.replace("  dev_repo: ~/Documents/repos/demo\n", "")
        with pytest.raises(ManifestError, match="requires `dev_repo`"):
            load(_write(tmp_path, body))

    def test_dev_repo_forces_pull_only(self, tmp_path):
        body = DEVREPO.replace("runtime_clone: pull-only", "runtime_clone: writable")
        with pytest.raises(ManifestError, match="pull-only"):
            load(_write(tmp_path, body))


# ── validation rules ────────────────────────────────────────────────────────


class TestDeliveryValidation:
    def test_content_cannot_be_deployable(self, tmp_path):
        body = BASE + textwrap.dedent("""\
            delivery:
              topology: content
              deployable: true
            """)
        with pytest.raises(ManifestError, match="content topology cannot be deployable"):
            load(_write(tmp_path, body))

    def test_deployable_requires_gates(self, tmp_path):
        body = BASE + textwrap.dedent("""\
            delivery:
              topology: in-place
              deployable: true
              deploy:
                gates: []
            """)
        with pytest.raises(ManifestError, match="at least one deploy gate"):
            load(_write(tmp_path, body))

    def test_bad_topology_rejected(self, tmp_path):
        body = BASE + "delivery:\n  topology: teleport\n"
        with pytest.raises(ManifestError, match="topology must be one of"):
            load(_write(tmp_path, body))

    def test_bad_autonomy_rejected(self, tmp_path):
        body = BASE + textwrap.dedent("""\
            delivery:
              topology: in-place
              deployable: false
              deploy:
                autonomy: whenever
            """)
        with pytest.raises(ManifestError, match="autonomy must be one of"):
            load(_write(tmp_path, body))

    def test_test_gate_requires_cmd(self, tmp_path):
        body = BASE + textwrap.dedent("""\
            delivery:
              topology: in-place
              deployable: true
              deploy:
                gates:
                  - kind: test
            """)
        with pytest.raises(ManifestError, match="test gate requires a `cmd`"):
            load(_write(tmp_path, body))

    def test_healthcheck_gate_requires_path(self, tmp_path):
        body = BASE + textwrap.dedent("""\
            delivery:
              topology: in-place
              deployable: true
              deploy:
                gates:
                  - kind: healthcheck
                    expect: 200
            """)
        with pytest.raises(ManifestError, match="healthcheck gate requires a `path`"):
            load(_write(tmp_path, body))


# ── pure dataclass helpers ──────────────────────────────────────────────────


class TestFromDict:
    def test_deploy_policy_defaults(self):
        p = DeployPolicy.from_dict({})
        assert p.skill == "project-redeploy" and p.autonomy == "gated-auto"
        assert p.gates == [] and p.services == []

    def test_gate_shorthand_string(self):
        # A bare string gate is treated as a kind (still validated later).
        p = DeployPolicy.from_dict({"gates": ["test"]})
        assert p.gates[0].kind == "test"

    def test_delivery_defaults(self):
        d = Delivery.from_dict({})
        assert d.topology == "in-place" and not d.is_pull_only
        assert d.dev_repo_path is None


class TestEnvFiles:
    """delivery.env_files — gitignored secrets copied into workspace clones."""

    def _delivery(self, env_files) -> Delivery:
        return Delivery(
            topology="dev-repo", dev_repo="~/x", runtime_clone="pull-only",
            deployable=True,
            deploy=DeployPolicy(gates=[DeployGate(kind="test", cmd="pytest")]),
            env_files=env_files,
        )

    def test_parsed_from_dict(self):
        d = Delivery.from_dict({"env_files": [".env", "config/.env.local"]})
        assert d.env_files == [".env", "config/.env.local"]

    def test_default_empty(self):
        assert Delivery.from_dict({}).env_files == []

    def test_relative_paths_validate(self):
        self._delivery([".env"]).validate("atlas")  # no raise

    def test_absolute_path_rejected(self):
        with pytest.raises(ManifestError, match="relative"):
            self._delivery(["/etc/passwd"]).validate("atlas")

    def test_home_relative_rejected(self):
        with pytest.raises(ManifestError, match="relative"):
            self._delivery(["~/.ssh/id_rsa"]).validate("atlas")

    def test_traversal_rejected(self):
        with pytest.raises(ManifestError, match="traverse"):
            self._delivery(["../secrets/.env"]).validate("atlas")

    def test_whitespace_rejected(self):
        with pytest.raises(ManifestError, match="non-empty"):
            self._delivery([" .env"]).validate("atlas")
