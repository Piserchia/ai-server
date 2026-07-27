# Registry module

**Paths:** `src/registry/skills.py`, `src/registry/manifest.py`

## Purpose

Parsers for the two pieces of external declarative configuration:

- `src/registry/skills.py` — loads `skills/<n>/SKILL.md`, extracts YAML
  frontmatter (model, effort, permission_mode, tools, escalation rules) and
  the markdown body (which becomes the system prompt).

- `src/registry/manifest.py` — loads `projects/<slug>/manifest.yml`, validates
  the schema (type, subdomain, port, healthcheck, start_command, on_update
  cron, git repo).

## Public interface

### skills

- `load(name) -> SkillConfig | None` — load one skill by directory name
- `list_all() -> list[SkillConfig]` — all skills, for SKILLS_REGISTRY.md generation
- `SkillConfig` dataclass — fields mirror frontmatter schema, with sensible
  defaults. Notable: `description` (router catalog + subagent card),
  `subagents` (skills exposed as in-session SDK subagents — compiled by
  `runner.agents.build_subagents`), `isolation` (`none | workspace | host`;
  retired `container` parses and runs as workspace)

### manifest

- `load(path) -> Manifest` — load + validate; raises `ManifestError` on invalid.
  `Manifest.from_dict` tolerates unknown top-level keys (mission, platforms,
  web_strategy, env_required, services …) — before 2026-07-27 the loader did
  `Manifest(**data)` and TypeError'd on every live manifest (all carry extras),
  so the Python loader was dead; `load_all` now also catches TypeError.
- `load_all() -> list[Manifest]` — all projects, malformed ones skipped with a warning
- `Manifest` dataclass — slug, name, type, subdomain, port, healthcheck,
  start_command, env, on_update, git, **delivery**, dependencies
- `Delivery` / `DeployPolicy` / `DeployGate` dataclasses — the machine-readable
  delivery contract (2026-07-27). `topology` (dev-repo|in-place|content),
  `dev_repo`, `runtime_clone` (pull-only|writable), `deployable`, and
  `deploy` (skill, autonomy gated-auto|human-approval|manual-only, ordered
  gates, services, migrate). A manifest with no `delivery` block DERIVES a
  legacy-preserving default (in-place/writable; deployable only if a
  healthcheck exists to serve as the implicit gate) so runner enforcement is
  strictly opt-in per project. `Delivery.validate` enforces: dev-repo requires
  `dev_repo` + pull-only; content can't be deployable; deployable requires a
  gate. Consumed by `runner.session` (cwd scoping), the project guard
  (pull-only writes), the deploy-authority gate, and `project-redeploy`.

## Dependencies

- `src.config` — for settings.skills_dir and settings.projects_dir
- `yaml` (PyYAML)

## Testing

None yet (Phase 1). Phase 2: `tests/test_skills_registry.py`,
`tests/test_manifest.py` with valid + invalid fixtures.

## Gotchas

- Frontmatter with no closing `---` returns `(empty_dict, full_text)` —
  don't assume `load()` sees frontmatter.
- `list_all()` is called by `review-and-improve` monthly; keep it cheap.
  Current implementation does O(N) disk reads; fine for N < 100 skills.
- Malformed manifest.yml prints to stdout ("WARN: ...") — that's intentional
  for dev visibility; production should log via structlog.
