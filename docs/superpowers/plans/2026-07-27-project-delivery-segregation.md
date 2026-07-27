# Project Delivery Segregation — Implementation Plan (2026-07-27)

> **For agentic workers:** implement task-by-task; steps use checkbox (`- [ ]`) syntax.
> This is a **server-code** change set → ships via `server-patch` PRs (INV-4, manual merge,
> `code-review` LGTM required). Skills/docs may be committed directly.

**Goal:** Turn "how a project is delivered" from an informal, prose-only convention into a
**machine-readable per-project delivery contract that the runner enforces structurally**, so
every code project is worked in its own git thread (canonical dev repo separate from the
ai-server repo and from the running copy) and nothing deploys except under rules the project
declares. Generalize the bespoke `atlas-redeploy` into one config-driven deploy engine.

**Why:** Today `session.py:_resolve_cwd()` always scopes a project job to the runtime clone
(`projects/<slug>`); the ONLY thing that redirects an atlas patch to its real dev repo is the
`app-patch` "STEP 0" prose asking the LLM to read the project's CLAUDE.md. An LLM choosing
correctly is the entire safety mechanism — and mis-choosing is the 2026-07-09 single-writer
incident. The manifest `git:` field is an unparsed human string; there is no "is this
deployable / by whom" gate anywhere; `atlas-redeploy` is hand-written and would need
re-writing per project.

## Decisions locked in (owner, 2026-07-27)

1. **Uniform topology.** Every *code* project moves to the atlas-style split: canonical dev
   repo at `~/Documents/repos/<slug>`, runtime clone at `projects/<slug>` is **pull-only**.
   Content projects (`research`, `ideas`, `research-deep`) stay content (`topology: content`).
2. **Gated-autonomous deploys.** Any job may trigger a deploy, but it proceeds only if the
   manifest's declared gates pass (red gate → old code keeps running). Per-project override to
   `human-approval` or `manual-only`.
3. **Structural + guarded enforcement.** The runner scopes dev-repo project sessions to the dev
   repo automatically; writes to a pull-only runtime clone are guard-denied (the same
   PreToolUse hook mechanism shipped 2026-07-27 for the server). CLAUDE.md prose becomes
   documentation, not the control path.

**Architecture:** No new process. New `delivery` block in `manifest.yml`, parsed by
`registry/manifest.py`; a project-guard layer reusing `runner/guards.py`; cwd-resolution and a
deploy-authority gate in the runner; one generic `project-redeploy` skill driven by the
contract. **Tech stack:** Python 3.12, SQLAlchemy async, Redis, Claude Agent SDK, pytest, bash/launchd.

## The delivery contract (manifest schema)

```yaml
# projects/<slug>/manifest.yml — replaces the freeform `git:` string
delivery:
  topology: dev-repo | in-place | content
  dev_repo: ~/Documents/repos/<slug>      # REQUIRED iff topology == dev-repo
  runtime_clone: pull-only | writable     # dev-repo ⇒ pull-only (enforced)
  branch: main
  deployable: true | false                # content/false ⇒ deploy jobs refuse
  deploy:
    skill: project-redeploy               # generic engine (default); or a bespoke skill name
    autonomy: gated-auto | human-approval | manual-only   # default gated-auto
    gates:                                # ordered; each must pass before restart
      - kind: test        cmd: "..."      # red ⇒ STOP, old code keeps running
      - kind: build       cmd: "..."  when_paths: ["web/"]   # deterministic path-gated build
      - kind: healthcheck path: "/healthz" expect: 200
    services: [<launchd-suffix>, ...]     # restart-only-what-changed targets
    migrate: "dbmate ... up"              # optional, idempotent
```

Validation rules (`Manifest.validate`): `dev-repo` requires an existing `dev_repo` dir and
forces `runtime_clone: pull-only`; `content` forces `deployable: false`; `deployable: true`
requires a non-empty `deploy.gates`; unknown `topology`/`autonomy` → `ManifestError`.

---

### Phase A — Contract schema + validation + lint (non-breaking)

**Files:** `src/registry/manifest.py`, `tests/test_manifest.py` (new), `scripts/lint_docs.py`,
`.context/modules/registry/{CONTEXT,CHANGELOG}.md`.

- [ ] `Delivery`, `DeployPolicy`, `DeployGate` dataclasses + `topology`/`autonomy` enums.
- [ ] `Manifest.delivery` field; back-compat: a manifest with no `delivery` block resolves to a
      derived default (`type: static/service/api` + own-repo `git.repo` ⇒ `in-place, writable,
      gated-auto`; no manifest ⇒ `content`) so nothing breaks pre-migration.
- [ ] `validate()` rules above; pure, fully unit-tested (valid + every invalid shape).
- [ ] `lint_docs.py`: new `check_delivery_contracts()` — every hosted project's manifest parses,
      dev-repo projects point at an existing dev repo, deployable projects declare gates.
- [ ] **Gate:** `pipenv run pytest -q`, `pipenv run python scripts/lint_docs.py`.

### Phase B — Runner enforcement (the load-bearing phase)

**Files:** `src/runner/session.py` (`_resolve_cwd`), `src/runner/project_guards.py` (new) or an
extension of `runner/guards.py`, `src/runner/main.py` (deploy-authority gate), tests.

- [ ] **cwd scoping:** `_resolve_cwd` reads the contract. `topology: dev-repo` → session cwd is
      `delivery.dev_repo` (the separate thread), NOT the runtime clone. `in-place` → runtime
      clone as today. Content → project dir. Audited (`project_cwd_resolved`, topology + path).
- [ ] **pull-only guard:** when a workspace-tier project session's canonical is a `pull-only`
      runtime clone, attach a guard that denies writes/commits/pushes targeting that path
      (reuse `guards.make_guard_hooks` shape; new `guard_denied` reason `pull-only-runtime`).
      This is the generalized single-writer rule — structural, not prose.
- [ ] **deploy-authority gate:** a helper `deploy_permitted(manifest, trigger) -> (bool, reason)`.
      `deployable:false` → refuse; `manual-only` → refuse for autonomous/scheduled triggers;
      `human-approval` → enqueue a Telegram Y/N (reuse the project-deletion confirm path) and
      defer; `gated-auto` → proceed. Called by `project-redeploy` and by any restart path.
- [ ] Tests: cwd resolution per topology; guard denial for pull-only; authority matrix (pure).
- [ ] **Gate:** pytest + lint + a live probe (dev-repo project job lands in the dev repo; a
      write to its runtime clone is denied).

### Phase C — Generic `project-redeploy` skill

**Files:** `skills/project-redeploy/SKILL.md` (new), `skills/atlas-redeploy/SKILL.md` (retire →
thin alias or delete via the propose-PR path), `.context/SKILLS_REGISTRY.md`, router rule.

- [ ] Port atlas-redeploy's deterministic discipline into a contract-driven body: read
      `delivery.deploy`, run gates in order (red = STOP + report), path-gated builds, restart
      only listed services, healthcheck, evidence in the summary. ff-only pull; divergence is a
      finding, never forced.
- [ ] Router: "redeploy <slug>" / "deploy <slug>" → `project-redeploy` with `project_slug`.
- [ ] atlas-redeploy becomes a config of the generic engine (its manifest carries the three
      services + web build gate). Keep the name as an alias only if muscle-memory warrants.

### Phase D — `new-project` topology support

**Files:** `skills/new-project/SKILL.md`, `.context/modules/hosting/CONTEXT.md`.

- [ ] Ask topology up front (default dev-repo for code projects). For dev-repo: create
      `~/Documents/repos/<slug>` as canonical, `gh repo create` as offsite backup, then a
      pull-only runtime clone under `projects/<slug>` (origin → dev repo) — instead of today's
      commit-in-the-runtime-clone flow. Write the `delivery` block. Register + gates unchanged.

### Phase E — Migrate the live projects

**Files:** each `projects/<slug>/manifest.yml` (+ dev-repo moves for in-place projects).

- [ ] `atlas`: formalize its CLAUDE.md prose into a `delivery` block (topology dev-repo,
      dev_repo `~/Documents/repos/atlas`, pull-only, three services, web build gate,
      gated-auto). No behavior change — just makes the existing rule machine-enforced.
- [ ] `baseball-bingo`: **promote to dev-repo** per decision 1 — establish
      `~/Documents/repos/baseball-bingo` as canonical, re-point `projects/baseball-bingo` to
      pull-only. (This is the one real migration; sequence it carefully — see Rollback.)
- [ ] `research` / `research-deep` / `ideas`: `topology: content, deployable: false`.
- [ ] Update `PROJECTS_REGISTRY.md`; add `topology` + `deployable` to the `projects` table
      (Alembic migration) and surface on `/api/projects` + dashboard tiles.

---

## Global constraints

- Never set `ANTHROPIC_API_KEY` (subscription auth only, INV-3).
- `src/`, `scripts/`, `alembic/` ship via `server-patch` PR — manual merge, `code-review` LGTM
  (INV-4). Skills/docs may be committed directly.
- Never write tracked files inside a pull-only runtime clone (this plan is the enforcement of
  that rule; until Phase B lands, obey it by hand for atlas).
- Every module touched gets a `.context/modules/<x>/CHANGELOG.md` entry.
- `pipenv run pytest -q` + `pipenv run python scripts/lint_docs.py` green before each commit.

## Rollback

- Phases A–D are additive or behind the contract; revert the commit + `pipenv sync`.
- Phase E baseball-bingo promotion is the only risky step: keep the current runtime-clone repo
  intact under a `backup-<date>` branch and tag before re-pointing origin; if the dev-repo cut
  misbehaves, restore origin to GitHub and revert the manifest `delivery` block to `in-place`.

## NOT in this plan

- Multi-machine / multi-host deploy. Single Mac Mini only.
- Cloud deploy targets (still prohibited — MISSION § Safety ceilings).
- Changing what the projects DO; this is purely delivery/segregation plumbing.
- The SDK `sandbox` (Seatbelt) OS-level hardening — tracked separately in SYSTEM.md debt.
