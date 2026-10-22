# Registry module

**Paths:** `src/registry/skills.py`, `src/registry/manifest.py`, `src/registry/models.py`

## Purpose

Parsers for the three pieces of external declarative configuration:

- `src/registry/models.py` — loads the repo-root `models.yml` (providers,
  model ids, aliases, context windows) and resolves `[provider/]model_id`
  everywhere a model id enters the system (T1, 2026-10-21).

- `src/registry/skills.py` — loads `skills/<n>/SKILL.md`, extracts YAML
  frontmatter (model, effort, permission_mode, tools, escalation rules) and
  the markdown body (which becomes the system prompt).

- `src/registry/manifest.py` — loads `projects/<slug>/manifest.yml`, validates
  the schema (type, subdomain, port, healthcheck, start_command, on_update
  cron, git repo).

## Public interface

### skills

- `load(name, skills_dir=None) -> SkillConfig | None` — load one skill by directory name
  (`skills_dir` defaults to `settings.skills_dir`; tests pass the repo's own `skills/`, 2026-10-21).
  Since 2026-08-31 raises `SkillFrontmatterError` when the skill exists but
  its frontmatter is corrupt (fail closed — never run a skill on defaults);
  `None` only means "no such skill". `list_all()` skips corrupt skills with
  an ERROR log.
- `list_all(skills_dir=None) -> list[SkillConfig]` — all skills, for SKILLS_REGISTRY.md generation
- `SkillConfig` dataclass — fields mirror frontmatter schema, with sensible
  defaults. Notable: `description` (router catalog + subagent card),
  `subagents` (skills exposed as in-session SDK subagents — compiled by
  `runner.agents.build_subagents`), `isolation` (`none | workspace | host`;
  retired `container` parses and runs as workspace)

### models (2026-10-21, cross-vendor writer slice T1; old spec §2.5)

- Grammar: `[provider/]model_id`; a bare id is `anthropic/<id>`. Unknown
  provider or model → `ProviderRefused` (C12: fail closed, never a default).
  `models.yml` is data, not a restraint: `settings.router_providers_enabled`
  (default `anthropic`) decides what may run.
- `resolve(raw) -> ModelRef` — alias or id → `ModelRef(provider, model_id)`;
  `.canonical` is bare for Anthropic, `provider/model_id` otherwise (what
  `job.payload["model"]` carries); `.qualified` always `provider/model_id`.
- `resolve_enabled(raw)` — `resolve()` plus the enabled-provider check; the
  form every entry point uses (`gateway.web` POST, `runner.session`).
- `split_model_ref(raw) -> (provider, model_id)` — pure, no lookup; `""` →
  `("", "")`. Backs `SkillConfig.provider` / `.model_id`.
- `alias_table() -> {alias: canonical}` — bare keys for Anthropic aliases,
  `provider/alias` otherwise, exactly what `resolve()` accepts (feeds
  `telegram_bot._MODEL_ALIASES`). `context_windows() -> {model_id: int}`
  (feeds `session._MODEL_BUDGETS`). `list_models(provider=None)` in yml
  order; `providers()`; `VALID_MODELS` (bare ids, the skill-contract
  allowlist); `enabled_providers()`.
- `Registry.load(path)` / `Registry.from_dict(data)` — explicit instances
  for tests; `RegistryError` on a missing or malformed file (raised at
  import for the default `DEFAULT_PATH = <repo>/models.yml` — next to the
  code, not under `settings.server_root`).
- `ProviderRefused(raw, reason, provider=, model_id=)` — `ValueError`;
  handled terminally in `runner.main._process_job`
  (`error_category=provider_refused`, audit `provider_refused`, no
  escalation) and as HTTP 422 in `gateway.web`.
- `SkillConfig.provider` / `.model_id` — derived from the raw `model`
  string; loading never validates (the job does).

### manifest

- `load(path) -> Manifest` — load + validate; raises `ManifestError` on invalid.
  `Manifest.from_dict` tolerates unknown top-level keys (mission, platforms,
  web_strategy, services …; `env_required` is read since D1) — before 2026-07-27 the loader did
  `Manifest(**data)` and TypeError'd on every live manifest (all carry extras),
  so the Python loader was dead; `load_all` now also catches TypeError.
- `load_all() -> list[Manifest]` — all projects, malformed ones skipped with a warning
- `Manifest` dataclass — slug, name, type, subdomain, port, healthcheck,
  start_command, env, on_update, git, **delivery**, dependencies, **env_required**
- `Manifest.env_required: list[str]` (READ since 2026-10-21, D1; ignored
  before) — owner-provisioned env NAMES the project needs. Consumed by the
  scheduler's `provisioning_gap` pre-check (`runner.main`): a due schedule
  row of this project is DEFERRED while its canonical `.env` lacks a declared
  name (except the INV-3 exemptions: `ANTHROPIC_API_KEY`,
  `ANTHROPIC_AUTH_TOKEN`, `CLAUDE_CODE_OAUTH_TOKEN`, any `ANTHROPIC_*`). So
  **adding a name to a project's `env_required` can defer that project's
  schedules** — additions are reviewed. Still fail-open and unvalidated:
  str-coerced via `coerce_env_names` (a bare string is one name, junk → `[]`),
  a bad entry never makes a manifest unloadable. Schedule rows may add their
  own names in `job_payload.env_required` (D-P1-7, `scripts/seed-schedules.sh`).
- `Delivery.env_files` (2026-08-10) — list of gitignored in-repo paths (e.g.
  `.env`) the runner copies from the canonical checkout into each workspace
  clone. `Delivery.validate` rejects absolute/`~`/`..` entries so a manifest
  can never pull arbitrary host files into a session-readable workspace.
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

- `src.config` — for settings.skills_dir, settings.projects_dir and
  settings.router_providers_enabled
- `yaml` (PyYAML)

## Testing

`tests/test_models_registry.py` (registry, every consumer path),
`tests/test_skill_contracts.py` (every SKILL.md resolves),
`tests/test_registry_failclosed.py`, `tests/test_manifest.py`,
`tests/test_delivery.py`.

## Gotchas

- Frontmatter with no closing `---` returns `(empty_dict, full_text)` —
  don't assume `load()` sees frontmatter.
- `list_all()` is called by `review-and-improve` monthly; keep it cheap.
  Current implementation does O(N) disk reads; fine for N < 100 skills.
- Malformed manifest.yml prints to stdout ("WARN: ...") — that's intentional
  for dev visibility; production should log via structlog.
