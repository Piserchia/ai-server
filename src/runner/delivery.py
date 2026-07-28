"""
Runner-side project delivery enforcement (project segregation Phase B, 2026-07-27).

Reads each project's `manifest.yml` delivery contract and turns it from prose
into structure:

  - **cwd scoping** (`resolve_delivery_cwd`): for `topology: dev-repo`, code
    sessions are scoped to the canonical dev repo (e.g. ~/Documents/repos/atlas),
    NOT the runtime clone under projects/<slug>. Combined with the existing
    workspace guard (which denies writes outside the per-job clone), this makes
    the single-writer rule structural — a patch session literally isn't in the
    runtime clone and can't write to it. Deploy jobs are the exception: they
    operate ON the runtime clone (pull + build + restart).

  - **deploy authority** (`deploy_permitted`): a deploy job is gated by the
    contract's `deployable` + `deploy.autonomy` and by whether a human or an
    autonomous actor triggered it.

Pure decision functions at the top (unit-tested); a thin manifest loader below.
Everything fails OPEN to legacy behavior: a project with no/invalid manifest,
or no `delivery` block, behaves exactly as before this module existed.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from src.config import settings
from src.registry.manifest import Delivery, Manifest, ManifestError
from src.registry.manifest import load as load_manifest

logger = logging.getLogger(__name__)


# ── Trigger classification ──────────────────────────────────────────────────

# created_by prefixes the runner itself stamps on autonomously-spawned jobs.
# Anything else (telegram:<chat>, a bare user, god, eval) is a human trigger.
_AUTONOMOUS_PREFIXES = (
    "scheduler", "escalation", "auto-continue", "evaluator", "eval-fix",
    "learning", "writeback", "event", "plan:", "self-diagnose", "cascade",
)


def classify_trigger(created_by: str | None) -> str:
    """'autonomous' if the job was spawned by the runner's own machinery,
    else 'human'. Pure function."""
    cb = (created_by or "").strip().lower()
    if not cb:
        return "autonomous"   # unknown origin → treat as autonomous (stricter)
    for p in _AUTONOMOUS_PREFIXES:
        if cb.startswith(p):
            return "autonomous"
    return "human"


# ── Deploy authority ────────────────────────────────────────────────────────


class DeployDecision(Enum):
    allow = "allow"
    refuse = "refuse"
    needs_approval = "needs_approval"


@dataclass
class DeployVerdict:
    decision: DeployDecision
    reason: str = ""


def deploy_permitted(delivery: Delivery, trigger: str) -> DeployVerdict:
    """Decide whether a deploy job may proceed. Pure function.

    - deployable=false            → refuse
    - autonomy=gated-auto         → allow (the deploy skill's gates protect prod)
    - autonomy=manual-only        → allow iff a human triggered it, else refuse
    - autonomy=human-approval     → allow iff human, else needs_approval
    """
    if not delivery.deployable:
        return DeployVerdict(DeployDecision.refuse,
                             "project is not deployable (delivery.deployable=false)")
    autonomy = delivery.deploy.autonomy
    if autonomy == "gated-auto":
        return DeployVerdict(DeployDecision.allow)
    if autonomy == "manual-only":
        if trigger == "human":
            return DeployVerdict(DeployDecision.allow)
        return DeployVerdict(DeployDecision.refuse,
                             "deploy is manual-only; an autonomous trigger cannot "
                             "deploy this project")
    if autonomy == "human-approval":
        if trigger == "human":
            return DeployVerdict(DeployDecision.allow)
        return DeployVerdict(DeployDecision.needs_approval,
                             "deploy requires human approval; an autonomous trigger "
                             "must be confirmed before it can proceed")
    return DeployVerdict(DeployDecision.refuse, f"unknown deploy autonomy {autonomy!r}")


class DeployRefused(Exception):
    """A deploy job violated its project's delivery contract (terminal — no
    escalation; escalating a policy refusal would just retry the violation)."""


class DeployNeedsApproval(Exception):
    """A deploy job needs a human to confirm (autonomy: human-approval)."""


# ── cwd scoping ─────────────────────────────────────────────────────────────


def is_deploy_skill(skill_name: str, delivery: Delivery | None) -> bool:
    """True if this skill is a deploy skill for the project. Pure function.

    The generic engine (`project-redeploy`) and any `*-redeploy` skill count;
    so does whatever the manifest names in `delivery.deploy.skill`."""
    if not skill_name:
        return False
    if skill_name == "project-redeploy" or skill_name.endswith("-redeploy"):
        return True
    if delivery is not None and skill_name == delivery.deploy.skill:
        return True
    return False


def resolve_delivery_cwd(
    runtime_clone: Path,
    delivery: Delivery | None,
    is_deploy: bool,
) -> tuple[Path, bool]:
    """Return (cwd, scoped_to_dev_repo). Pure function.

    dev-repo topology + a non-deploy job → the canonical dev repo (the
    separate git thread). Deploy jobs, in-place, and content stay on the
    runtime clone. Falls back to the runtime clone (scoped_to_dev_repo=False)
    when the dev repo is declared but absent — the caller audits the fallback.
    """
    if delivery is not None and delivery.topology == "dev-repo" and not is_deploy:
        dev = delivery.dev_repo_path
        if dev is not None and dev.exists():
            return dev, True
        return runtime_clone, False
    return runtime_clone, False


# ── Manifest loading (thin; fails open) ─────────────────────────────────────


def load_project_manifest(slug: str) -> Manifest | None:
    """Load projects/<slug>/manifest.yml, or None if missing/invalid.

    Never raises — a broken manifest must not crash a job; the runner falls
    back to legacy behavior and the lint check surfaces the breakage."""
    if not slug:
        return None
    path = settings.projects_dir / slug / "manifest.yml"
    if not path.exists():
        return None
    try:
        return load_manifest(path)
    except (ManifestError, TypeError, ValueError) as exc:  # noqa: BLE001
        logger.warning("project %s has an invalid manifest — using legacy "
                       "delivery behavior: %s", slug, exc)
        return None
