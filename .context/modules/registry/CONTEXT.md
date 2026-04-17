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
- `SkillConfig` dataclass — fields mirror frontmatter schema, with sensible defaults

### manifest

- `load(path) -> Manifest` — load + validate; raises `ManifestError` on invalid
- `load_all() -> list[Manifest]` — all projects, malformed ones skipped with a warning
- `Manifest` dataclass — slug, name, type, subdomain, port, healthcheck,
  start_command, env, on_update, git, dependencies

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
