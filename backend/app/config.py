"""Application configuration settings.

This module centralizes configuration logic for the backend application. It
handles loading environment variables and exposing sane defaults. When
deploying to production, override these values via environment variables or
configuration management. The configuration is intentionally simple to keep
the rest of the codebase clean and easy to maintain.
"""

import os
from dotenv import load_dotenv

# Load .env only for local development. On Vercel, environment variables
# should come from the Vercel dashboard instead.
if not os.getenv("VERCEL"):
    load_dotenv()

# Google Drive configuration
GOOGLE_DRIVE_ROOT_FOLDER_ID: str = os.getenv("GOOGLE_DRIVE_ROOT_FOLDER_ID", "")

# Path to the JSON credentials file for a service account. This account
# requires access to the Google Drive folder hierarchy. In production you
# should secure this file and not commit it to source control.
GOOGLE_SERVICE_ACCOUNT_FILE: str = os.getenv(
    "GOOGLE_SERVICE_ACCOUNT_FILE",
    "service-account.json",
)

# Raw service account JSON for serverless platforms where writing a
# credentials file is awkward or undesirable.
GOOGLE_SERVICE_ACCOUNT_JSON: str = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")

# API keys for third-party AI providers. These values are optional; if they
# are absent the application will fall back to stubbed responses.
PERPLEXITY_API_KEY: str = os.getenv("PERPLEXITY_API_KEY", "")
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

# HTML template filenames.
TX_TEMPLATE_NAME: str = os.getenv("TX_TEMPLATE_NAME", "Clinical_Treatment_Plan.html")
SESSION_TEMPLATE_NAME: str = os.getenv("SESSION_TEMPLATE_NAME", "Session_Notes_Template.html")
SUMMARY_TEMPLATE_NAME: str = os.getenv("SUMMARY_TEMPLATE_NAME", "Clinical_Summary_Template.html")


def _normalize_database_url(url: str) -> str:
    """Return a SQLAlchemy async database URL.

    Vercel marketplace providers commonly expose plain postgres:// or
    postgresql:// URLs. SQLAlchemy async sessions need the asyncpg driver
    suffix, while local SQLite should keep using aiosqlite.
    """
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


DB_URL: str = _normalize_database_url(
    os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./clinical_ai.db")
)


def _parse_allowed_origins(raw_origins: str) -> list[str]:
    """Parse comma-separated CORS origins from an environment variable."""
    return [
        origin.strip().rstrip("/")
        for origin in raw_origins.split(",")
        if origin.strip()
    ]


# CORS configuration.
#
# Required production frontend:
#   https://headway.docz.space
#
# Backend domain is included too for direct browser/API testing.
ALLOWED_ORIGINS: list[str] = _parse_allowed_origins(
    os.getenv(
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
)


def get_templates_dir() -> str:
    """Return the absolute path to the templates directory.

    The templates directory is expected to live in the same folder as this
    config module under `templates`. This helper avoids hardcoding
    platform-specific separators throughout the application.
    """
    return os.path.join(os.path.dirname(__file__), "templates")
