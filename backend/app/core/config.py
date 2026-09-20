"""Application settings loaded from the environment (pydantic-settings).

Values come from the process environment or from ``.env`` files: the repository root
``../.env`` first, then a local ``backend/.env`` which overrides it. ``.env.example`` in the
repository root documents every variable. Settings are created lazily via ``get_settings()``
so that importing the application never requires a configured environment.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration of the API server and workers."""

    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    database_url: str
    redis_url: str
    secret_key: str
    api_base_url: str
    speedtest_url: str
    ndt7_url: str = ""
    tz: str = "Asia/Almaty"

    # Who writes the draft of an appeal (T-46, ADR-011): claude or ollama. The key lives
    # only here, in the environment — never in the database and never in the panel.
    llm_provider: str = "claude"
    llm_api_key: str = ""
    llm_model: str = ""
    llm_url: str = ""
    telegram_bot_token: str = ""

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings instance (created on first use)."""
    return Settings()
