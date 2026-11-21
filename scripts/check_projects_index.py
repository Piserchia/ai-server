#!/usr/bin/env python3
"""
Check the combined project index (.context/PROJECTS_INDEX.yml) against the
files it summarises, so the index Claude uses to drive updates and deploys
cannot quietly drift from the real contracts.

Checks:
  1. The index parses; every project has the required keys; slugs are unique;
     status / topology / manifest.location use known values.
  2. Ports: no port is claimed twice (core + every live project and service);
     a project's retired ports are not reused by anything live.
  3. projects/_ports.yml: every allocation is in the index under the same
     owner, and every live port in the index is allocated there.
  4. Hostnames: none is claimed twice.
  5. .context/PROJECTS_REGISTRY.md: the "Currently hosted" table and the index
     list exactly the same slugs.
  6. Caddyfile.d/*.conf: every committed snippet's host is in the index and
     proxies to the port the index gives it. A live project with a hostname
     but no committed snippet is a WARNING (it may exist only on the Mini).
  7. Manifests: for every project whose manifest.yml is readable here
     (projects/<slug>/manifest.yml, or --manifest <slug>=<path>), slug, port,
     hostname, healthcheck, topology, deploy skill/autonomy and services must
     match the index. An unreadable manifest is a WARNING, or an ERROR with
     --strict (run --strict on the Mini, where projects/ holds them all).

Usage:
    python scripts/check_projects_index.py
    python scripts/check_projects_index.py --strict                # on the Mini
    python scripts/check_projects_index.py --manifest atlas=../atlas/manifest.yml

Exit 0 when there are no errors (warnings are printed but allowed), 1 otherwise.
Standalone: needs only PyYAML, reads files, never touches the network.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_REL = Path(".context/PROJECTS_INDEX.yml")

STATUSES = {"live", "retired", "content"}
TOPOLOGIES = {"dev-repo", "in-place", "content"}
LOCATIONS = {"github", "mini", "none"}
REQUIRED = ("slug", "name", "status", "type", "topology", "manifest", "verified")
LIVE_REQUIRED = ("hostname", "port", "services", "deploy", "health")


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)


# ── loaders ─────────────────────────────────────────────────────────────────

def load_index(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text())
    if not isinstance(data, dict):
        raise TypeError(f"{path}: top level must be a mapping")
    return data


def load_ports_file(path: Path) -> dict[int, str]:
    """`NNNN: owner  # comment` lines → {port: owner}. Comment lines are skipped."""
    ports: dict[int, str] = {}
    for line in path.read_text().splitlines():
        m = re.match(r"^\s*(\d+)\s*:\s*([A-Za-z0-9_.-]+)", line)
        if m:
            ports[int(m.group(1))] = m.group(2)
    return ports


def load_registry_slugs(path: Path) -> list[str]:
    """Slugs from the first column of the "Currently hosted" table."""
    slugs: list[str] = []
    in_table = False
    for line in path.read_text().splitlines():
        if line.startswith("## "):
            in_table = line.strip() == "## Currently hosted"
            continue
        if in_table:
            m = re.match(r"^\|\s*`([^`]+)`\s*\|", line)
            if m:
                slugs.append(m.group(1))
    return slugs


def load_caddy_snippets(directory: Path) -> dict[str, tuple[str, int | None]]:
    """{host: (file name, first reverse_proxy port)} for each Caddyfile.d/*.conf."""
    snippets: dict[str, tuple[str, int | None]] = {}
    if not directory.is_dir():
        return snippets
    for conf in sorted(directory.glob("*.conf")):
        text = conf.read_text()
        port_m = re.search(r"reverse_proxy\s+(?:localhost|127\.0\.0\.1):(\d+)", text)
        port = int(port_m.group(1)) if port_m else None
        for host in re.findall(r"^\s*https?://([A-Za-z0-9.-]+)\s*\{", text, re.MULTILINE):
            snippets[host] = (conf.name, port)
    return snippets


# ── checks ──────────────────────────────────────────────────────────────────

def _projects(index: dict[str, Any]) -> list[dict[str, Any]]:
    return [p for p in (index.get("projects") or []) if isinstance(p, dict)]


def check_shape(index: dict[str, Any], rep: Report) -> None:
    seen: set[str] = set()
    for i, p in enumerate(_projects(index)):
        slug = p.get("slug") or f"<project #{i}>"
        for key in REQUIRED:
            if key not in p:
                rep.error(f"{slug}: missing required key `{key}`")
        if slug in seen:
            rep.error(f"{slug}: slug listed twice")
        seen.add(slug)
        if p.get("status") not in STATUSES:
            rep.error(f"{slug}: status must be one of {sorted(STATUSES)} (got {p.get('status')!r})")
        if p.get("topology") not in TOPOLOGIES:
            rep.error(f"{slug}: topology must be one of {sorted(TOPOLOGIES)} (got {p.get('topology')!r})")
        loc = (p.get("manifest") or {}).get("location")
        if loc not in LOCATIONS:
            rep.error(f"{slug}: manifest.location must be one of {sorted(LOCATIONS)} (got {loc!r})")
        if p.get("status") == "live":
            for key in LIVE_REQUIRED:
                if p.get(key) in (None, "", []):
                    rep.error(f"{slug}: live project needs `{key}`")
            if not (p.get("deploy") or {}).get("command"):
                rep.error(f"{slug}: live project needs deploy.command")
            if not (p.get("health") or {}).get("command"):
                rep.error(f"{slug}: live project needs health.command")
            if p.get("topology") == "dev-repo" and not p.get("dev_clone"):
                rep.error(f"{slug}: dev-repo topology needs `dev_clone`")


def claimed_ports(index: dict[str, Any]) -> list[tuple[int, str]]:
    """(port, owner) for core + every LIVE project's main port and service ports.
    A service on its project's main port counts once."""
    out: list[tuple[int, str]] = []
    for entry in (index.get("core") or {}).get("ports") or []:
        out.append((int(entry["port"]), str(entry.get("service", "core"))))
    for p in _projects(index):
        if p.get("status") != "live":
            continue
        slug = p["slug"]
        main = p.get("port")
        if main is not None:
            out.append((int(main), slug))
        for svc in p.get("services") or []:
            sp = svc.get("port")
            if sp is not None and sp != main:
                out.append((int(sp), slug))
    return out


def check_ports(index: dict[str, Any], ports_file: dict[int, str], rep: Report) -> None:
    owners: dict[int, str] = {}
    for port, owner in claimed_ports(index):
        if port in owners and owners[port] != owner:
            rep.error(f"port {port} claimed by both `{owners[port]}` and `{owner}`")
        elif port in owners:
            rep.error(f"port {port} listed twice for `{owner}`")
        owners[port] = owner

    retired: dict[int, str] = {}
    for p in _projects(index):
        for rp in p.get("retired_ports") or []:
            retired[int(rp)] = p["slug"]
    for port, slug in retired.items():
        if port in owners:
            rep.error(f"port {port} was retired by `{slug}` but is reused by `{owners[port]}`")
        if port in ports_file:
            rep.error(f"port {port} was retired by `{slug}` but _ports.yml allocates it to `{ports_file[port]}`")

    for port, owner in sorted(ports_file.items()):
        if port not in owners:
            rep.error(f"_ports.yml allocates {port} to `{owner}` but the index has no live owner for it")
        elif owners[port] != owner:
            rep.error(f"_ports.yml says {port} is `{owner}`, the index says `{owners[port]}`")
    for port, owner in sorted(owners.items()):
        if port not in ports_file:
            rep.error(f"the index gives {port} to `{owner}` but _ports.yml does not allocate it")


def claimed_hosts(index: dict[str, Any]) -> list[tuple[str, str, int | None]]:
    out: list[tuple[str, str, int | None]] = []
    for h in (index.get("core") or {}).get("hostnames") or []:
        out.append((h["host"], "core", h.get("port")))
    for p in _projects(index):
        if p.get("status") == "live" and p.get("hostname"):
            out.append((p["hostname"], p["slug"], p.get("port")))
    return out


def check_hostnames(index: dict[str, Any], rep: Report) -> None:
    seen: dict[str, str] = {}
    for host, owner, _ in claimed_hosts(index):
        if host in seen:
            rep.error(f"hostname {host} claimed by both `{seen[host]}` and `{owner}`")
        seen[host] = owner


def check_registry(index: dict[str, Any], registry_slugs: list[str], rep: Report) -> None:
    idx = {p["slug"] for p in _projects(index) if "slug" in p}
    reg = set(registry_slugs)
    for slug in sorted(reg - idx):
        rep.error(f"`{slug}` is in PROJECTS_REGISTRY.md but missing from the index")
    for slug in sorted(idx - reg):
        rep.error(f"`{slug}` is in the index but missing from PROJECTS_REGISTRY.md")


def check_caddy(index: dict[str, Any], snippets: dict[str, tuple[str, int | None]],
                rep: Report) -> None:
    hosts = {h: (owner, port) for h, owner, port in claimed_hosts(index)}
    apex = index.get("domain")
    for host, (fname, port) in sorted(snippets.items()):
        if host not in hosts:
            rep.error(f"Caddyfile.d/{fname} routes {host}, which no live index entry owns")
            continue
        owner, want = hosts[host]
        if port is not None and want is not None and port != want:
            rep.error(f"Caddyfile.d/{fname} sends {host} to :{port}; the index says `{owner}` is on :{want}")
    for host, owner, _ in claimed_hosts(index):
        if owner == "core" or host == apex:
            continue
        if host not in snippets:
            rep.warn(f"`{owner}`: no committed Caddyfile.d snippet for {host} "
                     f"(it may exist only on the Mini)")


def _manifest_services(m: dict[str, Any], slug: str) -> set[str]:
    deploy_services = ((m.get("delivery") or {}).get("deploy") or {}).get("services")
    if deploy_services:
        return {str(s) for s in deploy_services}
    names = {slug} if m.get("type") in ("service", "api") else set()
    for svc in m.get("services") or []:
        if isinstance(svc, dict) and svc.get("name"):
            names.add(f"{slug}-{svc['name']}")
    return names


def check_manifest(p: dict[str, Any], m: dict[str, Any], domain: str | None,
                   rep: Report) -> None:
    slug = p["slug"]

    def differ(field_name: str, got: Any, want: Any) -> None:
        rep.error(f"{slug}: index {field_name} is {want!r} but the manifest says {got!r}")

    if m.get("slug") != slug:
        differ("slug", m.get("slug"), slug)
    if p.get("status") == "retired":
        return  # a retired manifest is kept for history; only identity is checked
    if p.get("port") != m.get("port"):
        differ("port", m.get("port"), p.get("port"))
    if p.get("healthcheck") is not None and p.get("healthcheck") != m.get("healthcheck"):
        differ("healthcheck", m.get("healthcheck"), p.get("healthcheck"))
    if p.get("hostname") and m.get("subdomain") and domain:
        want_sub = p["hostname"].removesuffix("." + domain)
        if want_sub != m["subdomain"]:
            differ("subdomain", m["subdomain"], want_sub)

    delivery = m.get("delivery") or {}
    topology = delivery.get("topology", "in-place")
    if topology != p.get("topology"):
        differ("topology", topology, p.get("topology"))
    if delivery.get("dev_repo") and p.get("dev_clone") and delivery["dev_repo"] != p["dev_clone"]:
        differ("dev_clone", delivery["dev_repo"], p["dev_clone"])
    deploy = delivery.get("deploy") or {}
    idx_deploy = p.get("deploy") or {}
    if deploy:
        if deploy.get("skill", "project-redeploy") != idx_deploy.get("skill"):
            differ("deploy.skill", deploy.get("skill", "project-redeploy"), idx_deploy.get("skill"))
        if deploy.get("autonomy", "gated-auto") != idx_deploy.get("autonomy"):
            differ("deploy.autonomy", deploy.get("autonomy", "gated-auto"), idx_deploy.get("autonomy"))
    elif p.get("status") == "live" and idx_deploy.get("skill") not in (None, "app-patch"):
        rep.error(f"{slug}: manifest has no delivery.deploy block, so "
                  f"`{idx_deploy.get('skill')}` cannot deploy it")

    want_svcs = {s["name"] for s in p.get("services") or [] if s.get("name")}
    got_svcs = _manifest_services(m, slug)
    if want_svcs != got_svcs:
        differ("services", sorted(got_svcs), sorted(want_svcs))


def check_manifests(index: dict[str, Any], root: Path, overrides: dict[str, Path],
                    strict: bool, rep: Report) -> None:
    domain = index.get("domain")
    for p in _projects(index):
        slug = p.get("slug")
        if not slug:
            continue
        loc = (p.get("manifest") or {}).get("location")
        path = overrides.get(slug) or root / "projects" / slug / "manifest.yml"
        if loc == "none":
            if path.exists():
                rep.error(f"{slug}: index says it has no manifest, but {path} exists")
            continue
        if not path.exists():
            msg = f"{slug}: manifest not readable here ({loc}); index values are unverified against it"
            # A retired project's runtime clone is gone (or quarantined) by
            # design, so its missing manifest is never an error.
            (rep.error if strict and p.get("status") != "retired" else rep.warn)(msg)
            continue
        try:
            manifest = yaml.safe_load(path.read_text()) or {}
        except yaml.YAMLError as exc:
            rep.error(f"{slug}: {path} does not parse: {exc}")
            continue
        check_manifest(p, manifest, domain, rep)


def run(root: Path, overrides: dict[str, Path] | None = None, strict: bool = False,
        index_path: Path | None = None) -> Report:
    rep = Report()
    index_path = index_path or root / INDEX_REL
    try:
        index = load_index(index_path)
    except (OSError, TypeError, yaml.YAMLError) as exc:
        rep.error(f"cannot read the index: {exc}")
        return rep

    check_shape(index, rep)
    if rep.errors:
        return rep  # later checks assume a well-formed index

    ports_path = root / "projects" / "_ports.yml"
    ports_file = load_ports_file(ports_path) if ports_path.exists() else {}
    if not ports_path.exists():
        rep.error("projects/_ports.yml not found")
    check_ports(index, ports_file, rep)
    check_hostnames(index, rep)

    registry_path = root / ".context" / "PROJECTS_REGISTRY.md"
    if registry_path.exists():
        check_registry(index, load_registry_slugs(registry_path), rep)
    else:
        rep.error(".context/PROJECTS_REGISTRY.md not found")

    check_caddy(index, load_caddy_snippets(root / "Caddyfile.d"), rep)
    check_manifests(index, root, overrides or {}, strict, rep)
    return rep


def _parse_overrides(items: list[str]) -> dict[str, Path]:
    out: dict[str, Path] = {}
    for item in items:
        slug, sep, path = item.partition("=")
        if not sep or not slug or not path:
            raise SystemExit(f"--manifest expects <slug>=<path>, got {item!r}")
        out[slug] = Path(path).expanduser()
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--root", type=Path, default=REPO_ROOT, help="ai-server checkout (default: this repo)")
    ap.add_argument("--manifest", action="append", default=[], metavar="SLUG=PATH",
                    help="read this project's manifest from PATH (repeatable)")
    ap.add_argument("--strict", action="store_true",
                    help="an unreadable manifest is an error (use on the Mini)")
    args = ap.parse_args(argv)

    rep = run(args.root, _parse_overrides(args.manifest), args.strict)
    for w in rep.warnings:
        print(f"WARN  {w}")
    for e in rep.errors:
        print(f"ERROR {e}")
    print(f"projects index: {len(rep.errors)} error(s), {len(rep.warnings)} warning(s)")
    return 1 if rep.errors else 0


if __name__ == "__main__":
    sys.exit(main())
