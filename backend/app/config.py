"""Environment-driven configuration for the AgriShield API."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="", env_file=str(BACKEND_ROOT / ".env"), extra="ignore"
    )

    app_env: str = "development"
    app_name: str = "AgriShield API"

    secret_key: str = "dev-only-insecure-secret-change-me"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 30

    database_url: str = "sqlite:///./agrishield.db"
    cors_origins: str = "*"

    model_path: str = "ml/artifacts/agrishield_model.tflite"
    keras_model_path: str = "ml/artifacts/agrishield_model.keras"
    class_names_path: str = "ml/artifacts/class_names.json"
    advisory_dir: str = "advisory"
    upload_dir: str = "backend/uploads"

    max_upload_mb: int = 8
    min_confidence: float = 0.55
    healthy_confidence: float = 0.60
    gradcam_enabled: bool = True
    rate_limit_per_minute: int = 60
    weather_cache_seconds: int = 600
    open_meteo_url: str = "https://api.open-meteo.com/v1/forecast"

    @field_validator("database_url")
    @classmethod
    def _normalise_database_url(cls, value: str) -> str:
        """Accept the URLs managed hosts hand out (Render uses `postgres://`)."""
        if value.startswith("postgres://"):
            return "postgresql+psycopg://" + value[len("postgres://") :]
        if value.startswith("postgresql://"):
            return "postgresql+psycopg://" + value[len("postgresql://") :]
        return value

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() in {"production", "prod"}

    def resolve(self, maybe_relative: str | Path) -> Path:
        p = Path(maybe_relative)
        return p if p.is_absolute() else (REPO_ROOT / p)

    @property
    def model_file(self) -> Path:
        return self.resolve(self.model_path)

    @property
    def keras_file(self) -> Path:
        return self.resolve(self.keras_model_path)

    @property
    def class_names_file(self) -> Path:
        return self.resolve(self.class_names_path)

    @property
    def advisory_path(self) -> Path:
        return self.resolve(self.advisory_dir)

    @property
    def upload_path(self) -> Path:
        return self.resolve(self.upload_dir)

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
