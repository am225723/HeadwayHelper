from uuid import uuid4

from fastapi.testclient import TestClient

from app.admin_defaults import seed_admin_defaults
from app.drive import classify_file
from app.main import app
from app.models import ClassificationRule, DocumentTemplate, DocumentType, FileType
from app.templates import extract_placeholders, render_template, render_template_source


client = TestClient(app)


def _login(role: str) -> dict[str, str]:
    suffix = uuid4().hex
    email = f"{role.lower()}-{suffix}@example.com"
    password = "long-password"
    response = client.post("/api/auth/register", json={"email": email, "password": password, "role": role})
    assert response.status_code == 201
    login = client.post("/api/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_admin_config_endpoints_are_admin_only():
    admin_headers = _login("ADMIN")
    provider_headers = _login("PROVIDER")

    allowed = client.get("/api/admin/templates", headers=admin_headers)
    assert allowed.status_code == 200
    assert any(row["document_type"] == "SUMMARY" and row["placeholders"] for row in allowed.json())

    blocked = client.get("/api/admin/templates", headers=provider_headers)
    assert blocked.status_code == 403


def test_seeded_admin_defaults_include_backend_owned_config(db_session):
    seed_admin_defaults(db_session)

    assert db_session.query(DocumentTemplate).count() == 3
    assert db_session.query(ClassificationRule).filter(ClassificationRule.category == FileType.INTAKE.value).count() >= 1


def test_db_backed_classification_rule_overrides_defaults(db_session):
    db_session.add(ClassificationRule(category=FileType.INTAKE.value, keyword_or_pattern="custom-intake-marker"))
    db_session.commit()

    assert classify_file("patient_custom-intake-marker.pdf", db_session) == FileType.INTAKE.value


def test_template_placeholder_detection_supports_both_styles():
    assert extract_placeholders("Hello $$PATIENT_NAME$$ on {{ date_of_service }}") == ["date_of_service", "patient_name"]


def test_template_rendering_strips_ai_blocks_and_removes_not_documented_lines():
    html = render_template_source(
        "<section>[AI: remove this]<p>Keep {{patient_name}}</p><p>Risk: {{risk}}</p></section>",
        {"patient_name": "Jane Doe", "risk": ""},
        {"strip_instruction_blocks": True, "remove_not_documented_lines": True},
    )

    assert "AI:" not in html
    assert "Jane Doe" in html
    assert "Risk:" not in html


def test_active_db_template_is_used_for_generation_rendering(db_session):
    db_session.add(
        DocumentTemplate(
            document_type=DocumentType.SUMMARY.value,
            template_name="Test Summary",
            template_source="<h1>$$PATIENT_NAME$$</h1>",
            placeholder_style="dollar",
            cleanup_rules_json={"strip_instruction_blocks": True},
            is_active=True,
        )
    )
    db_session.commit()

    assert render_template(DocumentType.SUMMARY, {"patient_name": "Jane Doe"}, db_session) == "<h1>Jane Doe</h1>"
