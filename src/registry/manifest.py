"""
Project manifest schema + loader. Used by:

- scripts/register-project.sh (reads manifest.yml to generate Caddy snippet + launchd plist)
- the healthcheck loop (to know each project's /health path and port)
- the `new-project` skill (writes manifests)
- the `project-update-poll` skill (reads on_update.command)
- the runner (reads `delivery` to scope cwd, guard the runtime clone, gate deploys)
- the `project-redeploy` skill (reads `delivery.deploy`)

Manifest schema (see projects/<slug>/manifest.yml):

    slug: str
    name: str
    type: static | service | api
    subdomain: str
    port: int | None           # required if type != static
    healthcheck: str | None    # HTTP path; required for services
    start_command: str | None  # required if type != static
    working_dir: str = "."
    env: dict[str, str] = {}
    on_update:
      cron: str | None
      command: str | None
    git:                       # legacy freeform pointer (superseded by delivery)
      repo: str | None
      branch: str = "main"
    delivery:                  # machine-readable delivery contract (2026-07-27)
      topology: dev-repo | in-place | content
      dev_repo: str | None     # required iff topology == dev-repo
      runtime_clone: pull-only | writable
      branch: str = "main"
      deployable: bool
      env_files: [str, ...]    # gitignored files (e.g. ".env") copied from the
                               # canonical checkout into each workspace clone;
                               # relative in-repo paths only
      deploy:
        skill: str = "project-redeploy"
        autonomy: gated-auto | human-approval | manual-only
        gates: [ {kind, cmd?, path?, expect?, when_paths?}, ... ]
        services: [str, ...]
        migrate: str | None
    dependencies:
      python: str | None
    description: str
    created_at: str (ISO date)

Tolerance: unknown top-level keys (mission, platforms, web_strategy,
env_required, services, …) are IGNORED, not fatal. Before 2026-07-27 the loader
constructed `Manifest(**data)` directly and raised TypeError on every live
manifest (they all carry extra keys) — so the Python loader was dead and only
the yq-based shell scripts worked. `from_dict` now filters to known fields.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

import yaml

from src.config import settings

logger = logging.getLogger(__name__)


class ManifestError(ValueError):
    pass


# ── Delivery contract (2026-07-27) ──────────────────────────────────────────

VALID_TOPOLOGIES = ("dev-repo", "in-place", "content")
VALID_RUNTIME_CLONE = ("pull-only", "writable")
VALID_AUTONOMY = ("gated-auto", "human-approval", "manual-only")
VALID_GATE_KINDS = ("test", "build", "healthcheck", "command")


@dataclass
class DeployGate:
    kind: str
    cmd: str | None = None
    path: str | None = None          # healthcheck path
    expect: int | None = None        # healthcheck expected status
    when_paths: list[str] = field(default_factory=list)  # path-gated (e.g. build only if web/ changed)

    def validate(self, slug: str) -> None:
        if self.kind not in VALID_GATE_KINDS:
            raise ManifestError(
                f"{slug}: gate kind must be one of {VALID_GATE_KINDS} (got {self.kind!r})")
        if self.kind in ("test", "build", "command") and not self.cmd:
            raise ManifestError(f"{slug}: {self.kind} gate requires a `cmd`")
        if self.kind == "healthcheck" and not self.path:
            raise ManifestError(f"{slug}: healthcheck gate requires a `path`")


@dataclass
class DeployPolicy:
    skill: str = "project-redeploy"
    autonomy: str = "gated-auto"
    gates: list[DeployGate] = field(default_factory=list)
    services: list[str] = field(default_factory=list)
    migrate: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DeployPolicy":
        raw_gates = data.get("gates", []) or []
        gates = [DeployGate(**g) if isinstance(g, dict) else DeployGate(kind=str(g))
                 for g in raw_gates]
        return cls(
            skill=str(data.get("skill", "project-redeploy") or "project-redeploy"),
            autonomy=str(data.get("autonomy", "gated-auto") or "gated-auto"),
            gates=gates,
            services=list(data.get("services", []) or []),
            migrate=data.get("migrate"),
        )


@dataclass
class Delivery:
    topology: str = "in-place"
    dev_repo: str | None = None
    runtime_clone: str = "writable"
    branch: str = "main"
    deployable: bool = True
    deploy: DeployPolicy = field(default_factory=DeployPolicy)
    # Gitignored files (secrets like ".env") to copy from the canonical
    # checkout into each per-job workspace clone — `git clone` doesn't carry
    # them, so without this a workspace session never sees owner-provisioned
    # credentials. Relative in-repo paths only (validated).
    env_files: list[str] = field(default_factory=list)

    @property
    def is_pull_only(self) -> bool:
        return self.runtime_clone == "pull-only"

    @property
    def dev_repo_path(self) -> Path | None:
        return Path(self.dev_repo).expanduser() if self.dev_repo else None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Delivery":
        deploy = DeployPolicy.from_dict(data.get("deploy", {}) or {})
        return cls(
            topology=str(data.get("topology", "in-place") or "in-place"),
            dev_repo=data.get("dev_repo"),
            runtime_clone=str(data.get("runtime_clone", "writable") or "writable"),
            branch=str(data.get("branch", "main") or "main"),
            deployable=bool(data.get("deployable", True)),
            deploy=deploy,
            env_files=[str(e) for e in (data.get("env_files", []) or [])],
        )

    def validate(self, slug: str) -> None:
        if self.topology not in VALID_TOPOLOGIES:
            raise ManifestError(
                f"{slug}: delivery.topology must be one of {VALID_TOPOLOGIES} "
                f"(got {self.topology!r})")
        if self.runtime_clone not in VALID_RUNTIME_CLONE:
            raise ManifestError(
                f"{slug}: delivery.runtime_clone must be one of {VALID_RUNTIME_CLONE} "
                f"(got {self.runtime_clone!r})")
        if self.deploy.autonomy not in VALID_AUTONOMY:
            raise ManifestError(
                f"{slug}: delivery.deploy.autonomy must be one of {VALID_AUTONOMY} "
                f"(got {self.deploy.autonomy!r})")

        if self.topology == "dev-repo":
            if not self.dev_repo:
                raise ManifestError(f"{slug}: dev-repo topology requires `dev_repo`")
            # dev-repo topology means the runtime clone is a deploy target only.
            if self.runtime_clone != "pull-only":
                raise ManifestError(
                    f"{slug}: dev-repo topology requires runtime_clone: pull-only "
                    f"(the whole point is that commits are born in the dev repo)")
        if self.topology == "content" and self.deployable:
            raise ManifestError(
                f"{slug}: content topology cannot be deployable (nothing to deploy)")
        for ef in self.env_files:
            p = Path(ef)
            if not ef.strip() or ef != ef.strip():
                raise ManifestError(f"{slug}: delivery.env_files entries must be "
                                    f"non-empty plain paths (got {ef!r})")
            if p.is_absolute() or ef.startswith("~"):
                raise ManifestError(f"{slug}: delivery.env_files must be relative "
                                    f"in-repo paths (got {ef!r})")
            if ".." in p.parts:
                raise ManifestError(f"{slug}: delivery.env_files may not traverse "
                                    f"out of the repo (got {ef!r})")
        if self.deployable and not self.deploy.gates:
            raise ManifestError(
                f"{slug}: a deployable project must declare at least one deploy gate "
                f"(red gate = old code keeps running; declare what 'good' means)")
        for g in self.deploy.gates:
            g.validate(slug)


@dataclass
class OnUpdate:
    cron: str | None = None
    command: str | None = None


@dataclass
class GitConfig:
    repo: str | None = None
    branch: str = "main"


@dataclass
class Manifest:
    slug: str
    name: str
    type: str
    subdomain: str
    description: str
    port: int | None = None
    healthcheck: str | None = None
    start_command: str | None = None
    working_dir: str = "."
    env: dict[str, str] = field(default_factory=dict)
    on_update: OnUpdate = field(default_factory=OnUpdate)
    git: GitConfig = field(default_factory=GitConfig)
    delivery: Delivery = field(default_factory=Delivery)
    dependencies: dict[str, str] = field(default_factory=dict)
    created_at: str | None = None

    def validate(self) -> None:
        if self.type not in {"static", "service", "api"}:
            raise ManifestError(f"type must be one of static/service/api (got {self.type!r})")
        if self.type in {"service", "api"}:
            if self.port is None:
                raise ManifestError("service/api projects require a port")
            if self.start_command is None:
                raise ManifestError("service/api projects require a start_command")
        if "/" in self.slug or " " in self.slug:
            raise ManifestError(f"invalid slug: {self.slug!r}")
        self.delivery.validate(self.slug)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Manifest":
        """Build a Manifest from parsed YAML, tolerating unknown top-level keys.

        Extra keys the shell tooling reads directly (mission, platforms,
        web_strategy, env_required, services, …) are ignored here rather than
        fatal — the pre-2026-07-27 loader constructed `Manifest(**data)` and
        raised TypeError on every real manifest.
        """
        data = dict(data)
        on_update = OnUpdate(**(data.pop("on_update", {}) or {}))
        git = GitConfig(**(data.pop("git", {}) or {}))
        delivery = _resolve_delivery(data.pop("delivery", None), data)

        known = {f.name for f in fields(cls)}
        kwargs = {k: v for k, v in data.items() if k in known}
        return cls(on_update=on_update, git=git, delivery=delivery, **kwargs)


def _resolve_delivery(raw: dict[str, Any] | None, data: dict[str, Any]) -> Delivery:
    """Parse an explicit `delivery` block, or DERIVE a legacy-preserving default.

    Back-compat is the load-bearing property: a manifest with no `delivery`
    block must behave exactly as it did before this field existed, so the new
    runner enforcement is strictly opt-in per project. Derivation:
      - topology `in-place`, runtime_clone `writable`, deploy autonomy
        `gated-auto` — i.e. the legacy model where app-patch commits in the
        runtime clone and deploys inline.
      - if the manifest declares a `healthcheck`, that becomes the single
        derived gate and `deployable` is True; with no healthcheck there is no
        gate and `deployable` is False (a deployable contract requires a gate).
      NOTE: the generic `project-redeploy` skill fails closed on a derived
      default (no explicit `delivery.deploy` / empty `services`) — a legacy
      project is deployed via its EXISTING path (app-patch inline restart, or a
      bespoke `<x>-redeploy` skill), not the generic engine, until it opts in.
    """
    if raw is not None:
        return Delivery.from_dict(raw)

    # Derived default (no explicit block) — preserve pre-2026-07-27 behavior.
    healthcheck = data.get("healthcheck")
    gates: list[DeployGate] = []
    if healthcheck:
        gates.append(DeployGate(kind="healthcheck", path=str(healthcheck), expect=200))
    return Delivery(
        topology="in-place",
        runtime_clone="writable",
        deployable=bool(gates),   # only 'deployable' if we have an implicit gate
        deploy=DeployPolicy(skill="project-redeploy", autonomy="gated-auto", gates=gates),
    )


def load(path: Path) -> Manifest:
    data = yaml.safe_load(path.read_text()) or {}
    m = Manifest.from_dict(data)
    m.validate()
    return m


def load_all() -> list[Manifest]:
    results = []
    if not settings.projects_dir.exists():
        return results
    for child in sorted(settings.projects_dir.iterdir()):
        manifest = child / "manifest.yml"
        if manifest.exists():
            try:
                results.append(load(manifest))
            except (ManifestError, TypeError, yaml.YAMLError) as exc:
                # Skip malformed manifests — don't let one bad project break the registry
                print(f"WARN: skipping {child.name}: {exc}")
    return results
