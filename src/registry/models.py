"""
Models registry — provider-qualified model ids (cross-vendor writer slice T1,
2026-10-21; old spec §2.5).

Reads `models.yml` at the repo root (next to the code, NOT under
`settings.server_root`, so the registry and the code that interprets it
always travel together) and answers one question everywhere a model id
enters the system: *which provider, which model, is it real?*

Grammar: `[provider/]model_id`. A bare id means `anthropic/<id>` — the
existing Anthropic path keeps its bare strings in skill frontmatter, job
payloads and `jobs.resolved_model`. Anything the registry does not know
raises `ProviderRefused` (C12: fail closed, never a default).

Callers:
- `runner.session._resolve_model`   — skill pin / payload / default → `ModelRef`
- `gateway.web` POST /api/jobs       — refuses unknown ids with 422; dropdown
- `gateway.telegram_bot`             — `_MODEL_ALIASES = alias_table()`
- `runner.session._MODEL_BUDGETS`    — `context_windows()`
- `tests/test_skill_contracts.py`    — `VALID_MODELS`

The yml is data, not a restraint: adding a provider here enables nothing;
`settings.router_providers_enabled` (default `anthropic`) decides what may
run, and `enabled_providers()` / `resolve_enabled()` read it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from src.config import settings

DEFAULT_PROVIDER = "anthropic"
DEFAULT_PATH = Path(__file__).resolve().parents[2] / "models.yml"


class RegistryError(ValueError):
    """`models.yml` is missing or malformed. Raised at import — the server
    must not start on a registry it cannot trust."""


class ProviderRefused(ValueError):
    """A model reference the registry (or the enabled-provider set) does not
    accept. Terminal for a job: `runner.main` fails it with
    `error_category=provider_refused` and never escalates (a policy refusal
    would re-refuse on a bigger model)."""

    def __init__(self, raw: str, reason: str, *,
                 provider: str | None = None, model_id: str | None = None):
        self.raw = raw
        self.reason = reason
        self.provider = provider
        self.model_id = model_id
        super().__init__(f"model {raw!r} refused: {reason}")


@dataclass(frozen=True)
class ModelRef:
    provider: str
    model_id: str

    @property
    def qualified(self) -> str:
        """Always `provider/model_id`."""
        return f"{self.provider}/{self.model_id}"

    @property
    def canonical(self) -> str:
        """The string form that round-trips through `resolve()` and keeps the
        Anthropic path byte-identical: bare for `anthropic/`, qualified
        otherwise. This is what lands in `job.payload["model"]`."""
        return self.model_id if self.provider == DEFAULT_PROVIDER else self.qualified


@dataclass(frozen=True)
class ModelEntry:
    provider: str
    model_id: str
    label: str
    context_window: int
    aliases: tuple[str, ...] = ()

    @property
    def ref(self) -> ModelRef:
        return ModelRef(self.provider, self.model_id)


@dataclass(frozen=True)
class ProviderEntry:
    name: str
    executor: str
    models: dict[str, ModelEntry]   # insertion order = yml order
    aliases: dict[str, str]         # alias → model_id, this provider only


def split_model_ref(raw: str) -> tuple[str, str]:
    """Pure, TOTAL split of `[provider/]model_id` → `(provider, model_id)`,
    lowercased and stripped. Bare → `("anthropic", id)`; `""` → `("", "")`
    (no pin). Never raises: a malformed id with extra slashes splits on the
    FIRST slash (`"a/b/c"` → `("a", "b/c")`) and `resolve()` refuses it as an
    unknown model. No registry lookup, so `SkillConfig.provider` never fails
    at load time (list_all() for SKILLS_REGISTRY.md must survive any
    frontmatter)."""
    s = (raw or "").strip().lower()
    if not s:
        return "", ""
    if "/" not in s:
        return DEFAULT_PROVIDER, s
    provider, _, model_id = s.partition("/")
    return provider, model_id


_DEFAULT_WINDOW = 200_000


class Registry:
    def __init__(self, providers: dict[str, ProviderEntry]):
        self._providers = providers

    # ── loading ──────────────────────────────────────────────────────────

    @classmethod
    def load(cls, path: Path | str = DEFAULT_PATH) -> "Registry":
        path = Path(path)
        if not path.exists():
            raise RegistryError(f"models registry not found: {path}")
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            raise RegistryError(f"{path}: not valid YAML: {exc}") from exc
        return cls.from_dict(data, source=str(path))

    @classmethod
    def from_dict(cls, data: dict, *, source: str = "<dict>") -> "Registry":
        if not isinstance(data, dict) or not isinstance(data.get("providers"), dict):
            raise RegistryError(f"{source}: top level must be a mapping with a "
                                f"'providers' mapping")
        providers: dict[str, ProviderEntry] = {}
        if not data["providers"]:
            raise RegistryError(f"{source}: 'providers' is empty")
        for pname, pdata in data["providers"].items():
            if not isinstance(pname, str) or pname != pname.strip().lower() or "/" in pname:
                raise RegistryError(f"{source}: provider name {pname!r} must be "
                                    f"lowercase with no '/'")
            if not isinstance(pdata, dict) or not isinstance(pdata.get("models"), dict) \
                    or not pdata["models"]:
                raise RegistryError(f"{source}: provider {pname!r} needs a non-empty "
                                    f"'models' mapping")
            models: dict[str, ModelEntry] = {}
            aliases: dict[str, str] = {}
            for mid, mdata in pdata["models"].items():
                mdata = mdata or {}
                if not isinstance(mid, str) or mid != mid.strip().lower() or "/" in mid:
                    raise RegistryError(f"{source}: {pname}: model id {mid!r} must be "
                                        f"lowercase with no '/'")
                if not isinstance(mdata, dict):
                    raise RegistryError(f"{source}: {pname}/{mid}: entry must be a mapping")
                window = mdata.get("context_window", _DEFAULT_WINDOW)
                if not isinstance(window, int) or isinstance(window, bool) or window <= 0:
                    raise RegistryError(f"{source}: {pname}/{mid}: context_window must "
                                        f"be a positive int")
                raw_aliases = mdata.get("aliases", []) or []
                if not isinstance(raw_aliases, list) or not all(
                        isinstance(a, str) and a for a in raw_aliases):
                    raise RegistryError(f"{source}: {pname}/{mid}: aliases must be a "
                                        f"list of strings")
                models[mid] = ModelEntry(
                    provider=pname, model_id=mid,
                    label=str(mdata.get("label") or mid),
                    context_window=window,
                    aliases=tuple(a.strip().lower() for a in raw_aliases),
                )
            for entry in models.values():
                for alias in entry.aliases:
                    if alias in aliases or alias in models:
                        raise RegistryError(f"{source}: {pname}: alias {alias!r} "
                                            f"collides with another alias or model id")
                    aliases[alias] = entry.model_id
            providers[pname] = ProviderEntry(
                name=pname, executor=str(pdata.get("executor") or ""),
                models=models, aliases=aliases)
        return cls(providers)

    # ── queries ──────────────────────────────────────────────────────────

    def providers(self) -> tuple[str, ...]:
        return tuple(self._providers)

    def provider(self, name: str) -> ProviderEntry | None:
        return self._providers.get(name)

    def list_models(self, provider: str | None = None) -> list[ModelEntry]:
        """yml order, grouped by provider in yml order."""
        names = [provider] if provider is not None else list(self._providers)
        out: list[ModelEntry] = []
        for n in names:
            p = self._providers.get(n)
            if p is not None:
                out.extend(p.models.values())
        return out

    @property
    def valid_models(self) -> frozenset[str]:
        """Bare model ids across all providers (the skill-contract allowlist).
        Membership says the id exists somewhere; `resolve()` says where."""
        return frozenset(m.model_id for m in self.list_models())

    def resolve(self, raw: str) -> ModelRef:
        """`[provider/]model_id` or alias → `ModelRef`. Raises `ProviderRefused`
        on empty, malformed, unknown provider, or unknown model/alias."""
        provider, model_id = split_model_ref(raw)
        if not provider:
            raise ProviderRefused(raw, "empty model id")
        p = self._providers.get(provider)
        if p is None:
            raise ProviderRefused(raw, f"unknown provider {provider!r}",
                                  provider=provider, model_id=model_id)
        model_id = p.aliases.get(model_id, model_id)
        if model_id not in p.models:
            raise ProviderRefused(raw, f"unknown model {model_id!r} for provider {provider!r}",
                                  provider=provider, model_id=model_id)
        return ModelRef(provider, model_id)

    def alias_table(self) -> dict[str, str]:
        """Flat alias → canonical id, keyed exactly as `resolve()` accepts it:
        bare for Anthropic aliases, `provider/alias` otherwise — so
        `parse_flags` and `resolve()` can never disagree."""
        out: dict[str, str] = {}
        for p in self._providers.values():
            for alias, mid in p.aliases.items():
                ref = ModelRef(p.name, mid)
                key = alias if p.name == DEFAULT_PROVIDER else f"{p.name}/{alias}"
                out[key] = ref.canonical
        return out

    def context_windows(self) -> dict[str, int]:
        """Bare model id → input-token window (the session budget table)."""
        return {m.model_id: m.context_window for m in self.list_models()}


# ── module-level default registry ────────────────────────────────────────

REGISTRY = Registry.load(DEFAULT_PATH)
VALID_MODELS: frozenset[str] = REGISTRY.valid_models


def providers() -> tuple[str, ...]:
    return REGISTRY.providers()


def list_models(provider: str | None = None) -> list[ModelEntry]:
    return REGISTRY.list_models(provider)


def resolve(raw: str) -> ModelRef:
    return REGISTRY.resolve(raw)


def alias_table() -> dict[str, str]:
    return REGISTRY.alias_table()


def context_windows() -> dict[str, int]:
    return REGISTRY.context_windows()


def enabled_providers() -> frozenset[str]:
    """`settings.router_providers_enabled` as a set (CSV, case-folded).
    Default `anthropic`: every other provider is refused fail-closed until
    the owner flips the switch (plan §7 item 1)."""
    raw = settings.router_providers_enabled or ""
    return frozenset(p.strip().lower() for p in raw.split(",") if p.strip())


def resolve_enabled(raw: str) -> ModelRef:
    """`resolve()` plus the enabled-provider check. Used at every entry point
    (web request, session) so a disabled provider is refused with the same
    `ProviderRefused` as an unknown one."""
    ref = REGISTRY.resolve(raw)
    if ref.provider not in enabled_providers():
        raise ProviderRefused(
            raw, f"provider {ref.provider!r} is not enabled "
                 f"(ROUTER_PROVIDERS_ENABLED={settings.router_providers_enabled!r})",
            provider=ref.provider, model_id=ref.model_id)
    return ref
