from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.admin_defaults import seed_bootstrap_admin
from app.config import Settings, get_settings
from app.database import Base, SessionLocal
from app.main import app
from app.models import User
from app.seed import run_seed


def test_health_endpoints_return_statuses():
    from fastapi.testclient import TestClient

    client = TestClient(app)
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/health/db").json()["status"] == "ok"
    assert client.get("/health/drive").json()["status"] in {"ok", "not_configured"}
    assert client.get("/health/ai").json()["status"] in {"ok", "not_configured"}
    assert client.get("/health/templates").json()["status"] in {"ok", "not_configured"}


def test_bootstrap_admin_creation_is_idempotent(monkeypatch):
    monkeypatch.setenv("ADMIN_EMAIL", "aleix@drzelisko.com")
    monkeypatch.setenv("ADMIN_PASSWORD", "Admin123")
    get_settings.cache_clear()
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    try:
        first = seed_bootstrap_admin(db)
        second = seed_bootstrap_admin(db)
        assert first.email == "aleix@drzelisko.com"
        assert first.full_name == "Aleixander Puerta"
        assert first.is_active is True
        assert second.id == first.id
    finally:
        db.close()
        get_settings.cache_clear()


def test_env_config_warns_for_missing_production_values():
    settings = Settings(app_env="production", database_url="sqlite:///tmp.db", jwt_secret_key="change-me", ai_provider="perplexity", perplexity_api_key="")
    warnings = settings.startup_warnings()
    assert any("Postgres" in warning for warning in warnings)
    assert any("JWT_SECRET_KEY" in warning for warning in warnings)
    assert any("PERPLEXITY_API_KEY" in warning for warning in warnings)


def test_seed_command_runs_idempotently():
    first = run_seed("settings")
    second = run_seed("settings")
    assert first["defaults"] == "seeded"
    assert second["defaults"] == "seeded"


def test_inactive_user_cannot_login():
    from fastapi.testclient import TestClient

    client = TestClient(app)
    email = "inactive@example.com"
    password = "long-password"
    client.post("/api/auth/register", json={"email": email, "password": password, "role": "PROVIDER"})
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        user.is_active = False
        db.commit()
    finally:
        db.close()
    assert client.post("/api/auth/login", json={"email": email, "password": password}).status_code == 401
