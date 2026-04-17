"""
Settings. One place; everything else imports `settings` from here.

Auth model: Claude subscription via bundled Claude Code CLI.
NO anthropic_api_key field — setting it would silently switch the SDK to
API billing. The bootstrap script actively unsets ANTHROPIC_API_KEY.
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Models
    default_model: str = "claude-sonnet-4-6"

    # Database
    postgres_dsn: str

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Telegram
    telegram_bot_token: str = ""
    telegram_allowed_chat_ids: str = ""  # comma-separated

    # Web
    web_auth_token: str = ""
    web_port: int = 8080

    # Paths
    server_root: Path = Path.home() / "Library" / "Application Support" / "assistant"

    # Runner
    max_concurrent_jobs: int = 2
    session_timeout_seconds: int = 1800

    # Quota
    quota_pause_minutes: int = 60

    # Domain (Phase 3+)
    server_domain: str = ""

    @property
    def allowed_chat_ids(self) -> list[int]:
        if not self.telegram_allowed_chat_ids.strip():
            return []
        return [int(x.strip()) for x in self.telegram_allowed_chat_ids.split(",") if x.strip()]

    @property
    def audit_log_dir(self) -> Path:
        return self.server_root / "volumes" / "audit_log"

    @property
    def logs_dir(self) -> Path:
        return self.server_root / "volumes" / "logs"

    @property
    def projects_dir(self) -> Path:
        return self.server_root / "projects"

    @property
    def skills_dir(self) -> Path:
        return self.server_root / "skills"

    @property
    def context_dir(self) -> Path:
        return self.server_root / ".context"


settings = Settings()  # type: ignore[call-arg]
