from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class FilterRules(BaseModel):
    """Configurable hard-filter rule sets designed for future database storage."""

    pfe_keywords: list[str] = Field(
        default=[
            "pfe",
            "stage",
            "internship",
            "intern",
            "stagiaire",
            "projet de fin d'etudes",
            "fin d'etudes",
            "final year project",
            "graduation project",
            "memoire",
            "apprenticeship",
            "alternance",
        ]
    )
    location_whitelist: list[str] = Field(
        default=[
            "tunisia",
            "tunisie",
            "france",
            "remote",
            "hybrid",
            "teletravail",
            "paris",
            "tunis",
        ]
    )
    location_blacklist: list[str] = Field(
        default=["usa", "united states", "canada", "uk", "germany"]
    )
    seniority_blacklist: list[str] = Field(
        default=[
            "senior",
            "lead",
            "principal",
            "staff",
            "manager",
            "director",
            "head of",
            "vp of",
            "chief",
            "expert",
        ]
    )
    cs_field_keywords: list[str] = Field(
        default=[
            "computer science",
            "software",
            "data",
            "artificial intelligence",
            "machine learning",
            "deep learning",
            "cloud",
            "devops",
            "cybersecurity",
            "backend",
            "full-stack",
            "fullstack",
            "frontend",
            "mobile",
            "web",
            "api",
            "engineering",
            "developer",
            "programmer",
            "data scientist",
            "data engineer",
            "ml engineer",
            "ai engineer",
            "systems",
            "infrastructure",
        ]
    )
    employment_type_keywords: list[str] = Field(
        default=["internship", "stage", "pfe", "apprenticeship", "alternance", "graduate"]
    )
    employment_type_blacklist: list[str] = Field(
        default=["full-time", "permanent", "cdi", "contractor", "freelance"]
    )
    remote_keywords: dict[str, list[str]] = Field(
        default={
            "remote": [
                "remote",
                "teletravail",
                "work from home",
                "wfh",
                "home office",
                "distantiel",
            ],
            "hybrid": ["hybrid", "mixte", "semi-presentiel"],
            "onsite": ["on-site", "onsite", "presentiel", "in office", "in-office"],
        }
    )
    fuzzy_title_threshold: float = Field(default=80.0, ge=0.0, le=100.0)


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

    filter_rules: FilterRules = Field(default_factory=FilterRules)

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
