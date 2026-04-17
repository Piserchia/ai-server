"""
Project manifest schema + loader. Used by:

- scripts/register-project.sh (reads manifest.yml to generate Caddy snippet + launchd plist)
- the healthcheck loop (to know each project's /health path and port)
- the `new-project` skill (writes manifests)
- the `project-update-poll` skill (reads on_update.command)

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
    git:
      repo: str | None
      branch: str = "main"
    dependencies:
      python: str | None
    description: str
    created_at: str (ISO date)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from src.config import settings


class ManifestError(ValueError):
    pass


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


def load(path: Path) -> Manifest:
    data = yaml.safe_load(path.read_text()) or {}
    on_update = OnUpdate(**(data.pop("on_update", {}) or {}))
    git = GitConfig(**(data.pop("git", {}) or {}))
    m = Manifest(on_update=on_update, git=git, **data)
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
            except ManifestError as exc:
                # Skip malformed manifests — don't let one bad project break the registry
                print(f"WARN: skipping {child.name}: {exc}")
    return results
