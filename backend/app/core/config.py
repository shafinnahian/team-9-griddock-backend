"""Deployment configuration (Twelve-Factor): env-driven, validated at startup.

This holds *only* deployment concerns (DB URL, data paths, CORS). Domain/model
constants live in ``params.py``. Importing this module constructs ``settings``
and fails fast if a required variable is missing or malformed.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Required — the app will not start without it.
    database_url: str = "postgresql+psycopg2://griddock:griddock@db:5432/griddock"

    # Data locations (inside the container the repo ./data is mounted read-only).
    data_dir: str = "/app/data"
    sessions_md_path: str = "/app/data/source/nml_ev_sessions.md"
    sessions_csv_path: str = "/app/data/NML_ev_sessions.csv"

    # Golden artifacts used as validation oracles in scripts/05_validate.py.
    golden_integrated_path: str = "/app/data/_golden_integrated_pool_smard_15min.csv"
    golden_aggregate_path: str = "/app/data/_golden_aggregate_pool_15min.csv"

    # CORS — permissive for the local demo only.
    cors_origins: list[str] = ["*"]

    # App metadata.
    app_name: str = "GridDock API"
    app_version: str = "0.1.0"

    @field_validator("database_url")
    @classmethod
    def _non_empty_db_url(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("DATABASE_URL must not be empty")
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
