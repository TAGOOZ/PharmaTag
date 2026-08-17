"""Env-driven configuration (ticket #2 AC1).

Every value overridable via PHARMATAG_* env vars (or a .env file in the CWD).
Defaults mirror the provisioned test database; production overrides via env.
"""
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "pharmatag"
    environment: str = "development"

    # Same PHARMATAG_DB_URL var that alembic env.py reads (consistent tooling).
    database_url: str = Field(
        default=(
            "postgresql+psycopg://pharmatag_test:pharmatag_test@localhost:5432/pharmatag_test"
        ),
        validation_alias="PHARMATAG_DB_URL",
    )

    # Bundle-all + runtime gate (A12): plugin code ships with the repo under
    # <repo-root>/plugins/<slug>/; the registry loads it at runtime, DB rows gate it.
    plugins_dir: Path = Field(
        default=Path(__file__).resolve().parents[3] / "plugins",
        validation_alias="PHARMATAG_PLUGINS_DIR",
    )

    jwt_secret: str = "dev-only-change-me-0123456789abcdef012345"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 30

    # Web app origins allowed to call the API (S0.3: web /drugs reads via the
    # API; Next dev defaults to 3000/3001). Override via PHARMATAG_CORS_ORIGINS.
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://localhost:3001",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:3001",
        ],
        validation_alias="PHARMATAG_CORS_ORIGINS",
    )

    model_config = SettingsConfigDict(
        env_prefix="PHARMATAG_",
        env_file=".env",
        extra="ignore",
    )


settings = Settings()