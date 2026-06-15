"""
Centralized, typed application settings (pydantic-settings).

Values are read from environment variables (and a local .env file), validated
at startup so the app fails fast on a bad configuration. The per-company
database configuration stays dynamic (prefix-based env vars) and lives in
app/core/config.py — it does not map cleanly to a static settings model.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # ignore per-company DB vars (e.g. ACME_HOST)
    )

    # --- General logging ---
    LOG_LEVEL: str = "INFO"
    # Console (stdout) logging is always on. File logging is opt-in: inside a
    # container, logs belong on stdout, not on an ephemeral file.
    LOG_TO_FILE: bool = False
    LOG_FILE: str = "logs/app.log"

    # --- CORS ---
    # Comma-separated list of allowed origins. "*" allows any origin.
    CORS_ALLOW_ORIGINS: str = "*"

    # --- Uploads ---
    # Reject request bodies larger than this (bytes). Defaults to 50 MB.
    MAX_UPLOAD_BYTES: int = 50 * 1024 * 1024

    # --- Audit logging to Postgres ---
    LOG_DB_HOST: str | None = None
    LOG_DB_PORT: int = 5432
    LOG_DB_NAME: str = "postgres"
    LOG_DB_USER: str | None = None
    LOG_DB_PASSWORD: str | None = None
    LOG_DB_TABLE: str = "db_excel_sync_api_logs"
    LOG_DB_LEVEL: str = "INFO"
    # If unset, DB logging is enabled automatically when a host is configured.
    LOG_DB_ENABLED: bool | None = None

    @property
    def cors_origins(self) -> list[str]:
        origins = [o.strip() for o in self.CORS_ALLOW_ORIGINS.split(",") if o.strip()]
        return origins or ["*"]

    @property
    def db_logging_enabled(self) -> bool:
        if self.LOG_DB_ENABLED is not None:
            return self.LOG_DB_ENABLED
        return bool(self.LOG_DB_HOST)


settings = Settings()
