import json
from datetime import datetime, timezone

from sqlalchemy import Engine, text


SQLITE_ADMIN_COLUMNS = {
    "users": {
        "full_name": "VARCHAR(255)",
        "is_active": "BOOLEAN DEFAULT 1",
    },
    "reimbursement_rates": {
        "created_by": "VARCHAR(255)",
        "updated_by": "VARCHAR(255)",
    },
    "billing_rules": {
        "version": "INTEGER DEFAULT 1",
        "created_at": "DATETIME",
        "updated_by": "VARCHAR(255)",
    },
    "classification_rules": {
        "updated_by": "VARCHAR(255)",
    },
    "app_settings": {
        "version": "INTEGER DEFAULT 1",
        "created_at": "DATETIME",
        "updated_by": "VARCHAR(255)",
    },
    "document_templates": {
        "version": "INTEGER DEFAULT 1",
        "updated_by": "VARCHAR(255)",
    },
}


def ensure_sqlite_admin_columns(engine: Engine) -> None:
    """Small local-dev compatibility helper for existing SQLite DBs created before migrations."""
    if engine.dialect.name != "sqlite":
        return
    with engine.begin() as conn:
        existing_tables = {row[0] for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}
        for table, columns in SQLITE_ADMIN_COLUMNS.items():
            if table not in existing_tables:
                continue
            existing_columns = {row[1] for row in conn.execute(text(f"PRAGMA table_info({table})"))}
            for column, definition in columns.items():
                if column not in existing_columns:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {definition}"))
        now = datetime.now(timezone.utc).isoformat()
        for table in ["billing_rules", "app_settings", "document_templates"]:
            if table in existing_tables:
                columns = {row[1] for row in conn.execute(text(f"PRAGMA table_info({table})"))}
                if "created_at" in columns:
                    conn.execute(text(f"UPDATE {table} SET created_at = :now WHERE created_at IS NULL"), {"now": now})
                if "version" in columns:
                    conn.execute(text(f"UPDATE {table} SET version = 1 WHERE version IS NULL"))
        if "users" in existing_tables:
            columns = {row[1] for row in conn.execute(text("PRAGMA table_info(users)"))}
            if "is_active" in columns:
                conn.execute(text("UPDATE users SET is_active = 1 WHERE is_active IS NULL"))


def jsonable(value: object) -> dict | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump()
    try:
        return json.loads(json.dumps(value, default=str))
    except TypeError:
        return {"value": str(value)}
