"""
Centralized application settings, read from environment variables.

Kept dependency-free (plain os.getenv) because the per-company database
configuration is dynamic (prefix-based env vars) and does not map cleanly
to a static settings model. See app/core/config.py for that part.
"""
import os

from dotenv import load_dotenv

load_dotenv()


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _as_list(value: str | None, default: list[str]) -> list[str]:
    if value is None or not value.strip():
        return default
    return [item.strip() for item in value.split(",") if item.strip()]


class Settings:
    # --- General ---
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # Console (stdout) logging is always on. File logging is opt-in and off by
    # default: inside a container, logs belong on stdout, not on an ephemeral file.
    LOG_TO_FILE: bool = _as_bool(os.getenv("LOG_TO_FILE"), default=False)
    LOG_FILE: str = os.getenv("LOG_FILE", "logs/app.log")

    # --- CORS ---
    # Comma-separated list of allowed origins. Defaults to "*" (internal API).
    CORS_ALLOW_ORIGINS: list[str] = _as_list(os.getenv("CORS_ALLOW_ORIGINS"), ["*"])

    # --- Database logging (audit) ---
    # Enabled automatically when a host is provided, unless explicitly disabled.
    LOG_DB_HOST: str | None = os.getenv("LOG_DB_HOST")
    LOG_DB_PORT: int = int(os.getenv("LOG_DB_PORT", "5432"))
    LOG_DB_NAME: str = os.getenv("LOG_DB_NAME", "postgres")
    LOG_DB_USER: str | None = os.getenv("LOG_DB_USER")
    LOG_DB_PASSWORD: str | None = os.getenv("LOG_DB_PASSWORD")
    LOG_DB_TABLE: str = os.getenv("LOG_DB_TABLE", "db_excel_sync_api_logs")
    LOG_DB_ENABLED: bool = _as_bool(
        os.getenv("LOG_DB_ENABLED"), default=bool(os.getenv("LOG_DB_HOST"))
    )
    # Records below this level are not persisted to the DB (stdout still gets them).
    LOG_DB_LEVEL: str = os.getenv("LOG_DB_LEVEL", "INFO")


settings = Settings()
