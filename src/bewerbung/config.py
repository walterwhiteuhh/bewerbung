"""Zentrale Konfiguration (Umgebungsvariablen mit Präfix ``BEWERBUNG_``)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BEWERBUNG_", env_file=".env", extra="ignore")

    database_url: str = Field(
        default=f"sqlite:///{(Path.cwd() / 'data' / 'bewerbung.db').as_posix()}",
        description="SQLAlchemy-URL. SQLite lokal, später z. B. postgresql+psycopg://...",
    )
    log_level: str = "INFO"
    sql_echo: bool = False
    host: str = "127.0.0.1"
    port: int = 8000
    fetch_timeout: float = Field(default=10.0, description="Timeout für den Anzeigen-Import (s)")
    # Live-Suche. Arbeitsagentur nutzt den öffentlichen Schlüssel der Jobsuche-API.
    arbeitsagentur_api_key: str = "jobboerse-jobsuche"
    adzuna_app_id: str | None = Field(default=None, description="https://developer.adzuna.com")
    adzuna_app_key: str | None = None
    jooble_api_key: str | None = Field(default=None, description="https://jooble.org/api/about")
    jooble_base_url: str = "https://jooble.org/api/"
    search_timeout: float = 15.0
    # Anschreiben über Claude, GPT oder Gemini; ohne Key füllt die App eine Vorlage aus.
    anthropic_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("BEWERBUNG_ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY"),
        description="API-Key von https://platform.claude.com",
    )
    cover_letter_model: str = "claude-opus-5-5"
    openai_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("BEWERBUNG_OPENAI_API_KEY", "OPENAI_API_KEY"),
        description="API-Key von https://platform.openai.com",
    )
    openai_model: str = "gpt-5"
    gemini_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "BEWERBUNG_GEMINI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"
        ),
        description="API-Key von https://aistudio.google.com",
    )
    gemini_model: str = "gemini-2.5-pro"
    cover_letter_timeout: float = 120.0
    documents_dir: Path | None = Field(
        default=None,
        description="Ablage für Uploads. Standard: Ordner 'documents' neben der SQLite-Datei.",
    )
    max_upload_mb: int = 15
    auto_migrate: bool = Field(
        default=True, description="Alembic-Migrationen beim Start automatisch ausführen."
    )


def resolve_documents_dir(settings: Settings) -> Path:
    """Uploads liegen neben der Datenbank, damit ein Backup des Datenordners alles enthält."""
    if settings.documents_dir is not None:
        return settings.documents_dir
    prefix = "sqlite:///"
    if settings.database_url.startswith(prefix) and settings.database_url != "sqlite://":
        db_path = Path(settings.database_url.removeprefix(prefix))
        return db_path.parent / "documents"
    return Path.cwd() / "data" / "documents"


@lru_cache
def get_settings() -> Settings:
    return Settings()
