from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env files."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="STAGEPILOT_",
        extra="ignore",
    )

    app_name: str = "StagePilot Automation"
    app_env: Literal["local", "test", "development", "staging", "production"] = "local"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_json: bool = True

    mysql_host: str = "localhost"
    mysql_port: int = Field(default=3306, ge=1, le=65535)
    mysql_user: str = "stagepilot"
    mysql_password: str = Field(default="", repr=False)
    mysql_database: str = "stagepilot"

    data_dir: Path = Path("data")
    master_profile_json_path: Path = Path("data/master_profile/master_profile.json")

    discovery_http_timeout_seconds: int = Field(default=20, ge=1, le=120)
    discovery_retry_attempts: int = Field(default=3, ge=1, le=10)
    discovery_user_agent: str = "StagePilotAutomation/0.1"

    email_dry_run: bool = True
    telegram_allowed_user_id: int | None = None
    gemini_api_key: str | None = None
    openrouter_api_key: str | None = None

    @field_validator(
        "telegram_allowed_user_id",
        "gemini_api_key",
        "openrouter_api_key",
        mode="before",
    )
    @classmethod
    def empty_string_to_none(cls, value: object) -> object:
        """Treat blank optional environment variables as unset values."""
        if value == "":
            return None
        return value

    @computed_field
    @property
    def database_url(self) -> str:
        """Build the SQLAlchemy database URL for the configured MySQL database."""
        return URL.create(
            drivername="mysql+pymysql",
            username=self.mysql_user,
            password=self.mysql_password,
            host=self.mysql_host,
            port=self.mysql_port,
            database=self.mysql_database,
        ).render_as_string(hide_password=False)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
