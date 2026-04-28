"""Application configuration settings.

This module centralizes configuration logic for the backend application. It
handles loading environment variables and exposing sane defaults. When
deploying to production, override these values via environment variables or
configuration management.
"""

from __future__ import annotations

import os
from functools import lru_cache
from dataclasses import dataclass

from dotenv import load_dotenv

# Load .env only for local development. On Vercel, use Vercel Environment Variables.
if not os.getenv("VERCEL"):
    load_dotenv()


def _normalize_database_url(url: str) -> str:
    """Return a SQLAlchemy async database URL."""
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def _parse_allowed_origins(raw_origins: str) -> list[str]:
    """Parse comma-separated CORS origins."""
    return [
        origin.strip().rstrip("/")
        for origin in raw_origins.split(",")
        if origin.strip()
    ]


@dataclass(frozen=True)
class Settings:
    # Google Drive
    google_drive_root_folder_id: str = os.getenv("GOOGLE_DRIVE_ROOT_FOLDER_ID", "")
    google_service_account_file: str = os.getenv(
        "GOOGLE_SERVICE_ACCOUNT_FILE",
        "service-account.json",
    )
    google_service_account_json: str = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")

    # AI providers
    perplexity_api_key: str = os.getenv("PERPLEXITY_API_KEY", "")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")

    # Templates
    tx_template_name: str = os.getenv("TX_TEMPLATE_NAME", "Clinical_Treatment_Plan.html")
    session_template_name: str = os.getenv("SESSION_TEMPLATE_NAME", "Session_Notes_Template.html")
    summary_template_name: str = os.getenv("SUMMARY_TEMPLATE_NAME", "Clinical_Summary_Template.html")

    # Database
    db_url: str = _normalize_database_url(
        os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./clinical_ai.db")
    )

    # CORS
    allowed_origins: list[str] = None  # set below in __post_init__

    def __post_init__(self) -> None:
        raw_origins = os.getenv(
            "ALLOWED_ORIGINS",
            ",".join(
                [
                    "https://headway.docz.space",
                    "https://backend.docz.space",
                    "http://localhost:3000",
                    "http://localhost:5173",
                    "http://127.0.0.1:3000",
                    "http://127.0.0.1:5173",
                ]
            ),
        )
        object.__setattr__(self, "allowed_origins", _parse_allowed_origins(raw_origins))


@lru_cache
def get_settings() -> Settings:
    """Return cached app settings."""
    return Settings()


settings = get_settings()

# Backward-compatible constants used by the rest of the app.
GOOGLE_DRIVE_ROOT_FOLDER_ID: str = settings.google_drive_root_folder_id
GOOGLE_SERVICE_ACCOUNT_FILE: str = settings.google_service_account_file
GOOGLE_SERVICE_ACCOUNT_JSON: str = settings.google_service_account_json

PERPLEXITY_API_KEY: str = settings.perplexity_api_key
GEMINI_API_KEY: str = settings.gemini_api_key

TX_TEMPLATE_NAME: str = settings.tx_template_name
SESSION_TEMPLATE_NAME: str = settings.session_template_name
SUMMARY_TEMPLATE_NAME: str = settings.summary_template_name

DB_URL: str = settings.db_url
ALLOWED_ORIGINS: list[str] = settings.allowed_origins


def get_templates_dir() -> str:
    """Return the absolute path to the templates directory."""
    return os.path.join(os.path.dirname(__file__), "templates")
