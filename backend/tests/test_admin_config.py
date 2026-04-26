from uuid import uuid4

from fastapi.testclient import TestClient

from app.admin_defaults import seed_admin_defaults
from app.config import get_settings
from app.drive import classify_file
from app.main import app
from app.models import ClassificationRule, DocumentTemplate, DocumentType, FileType, Patient, SourceDocument, TemplateRenderLog
from app.pdf import html_to_pdf_bytes
from app.generation import generate_summary
from app.templates import extract_placeholders, placeholder_counts, render_template, render_template_source


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
    assert placeholder_counts("{{name}} {{ name }} $$NAME$$") == {"name": 3}


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


def test_admin_rate_crud_csv_and_change_log():
    headers = _login("ADMIN")
    create = client.post(
        "/api/admin/reimbursement-rates",
        headers=headers,
        json={"payer_name": "Aetna", "cpt_code": "99214", "amount": 123.45, "is_active": True, "notes": "test"},
    )
    assert create.status_code == 201
    rate_id = create.json()["id"]

    update = client.put(
        f"/api/admin/reimbursement-rates/{rate_id}",
        headers=headers,
        json={"payer_name": "Aetna", "cpt_code": "99214", "amount": 130.0, "is_active": True, "notes": "updated"},
    )
    assert update.status_code == 200
    assert update.json()["updated_by"]

    export = client.get("/api/admin/reimbursement-rates/export.csv", headers=headers)
    assert export.status_code == 200
    assert "payer_name,cpt_code,amount" in export.text

    imported = client.post(
        "/api/admin/reimbursement-rates/import-csv",
        headers={**headers, "Content-Type": "text/csv"},
        content="payer_name,cpt_code,amount,is_active,notes\nCigna,90837,155.50,true,imported\n",
    )
    assert imported.status_code == 200
    assert imported.json()["count"] == 1

    log = client.get("/api/admin/config-change-log", headers=headers)
    assert log.status_code == 200
    assert any(row["config_type"] == "reimbursement_rate" for row in log.json())


def test_template_preview_placeholder_pdf_endpoints():
    headers = _login("ADMIN")
    templates = client.get("/api/admin/templates", headers=headers).json()
    template_id = templates[0]["id"]

    placeholders = client.get(f"/api/admin/templates/{template_id}/placeholders", headers=headers)
    assert placeholders.status_code == 200
    assert placeholders.json()["placeholder_count"] > 0

    preview = client.post(f"/api/admin/templates/{template_id}/preview-html", headers=headers, json={"values": {}})
    assert preview.status_code == 200
    assert "html" in preview.json()
    assert "placeholders" in preview.json()

    pdf = client.post(f"/api/admin/templates/{template_id}/preview-pdf", headers=headers, json={"values": {}})
    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF")


def test_pdf_rendering_has_no_raw_placeholders_or_ai_instructions():
    html = render_template_source(
        "<h1>$$PATIENT_NAME$$</h1><p>[AI: hidden]</p>",
        {"patient_name": "Jane Doe"},
        {"strip_instruction_blocks": True},
    )
    pdf = html_to_pdf_bytes(html)
    assert pdf.startswith(b"%PDF")
    assert b"$$PATIENT_NAME$$" not in pdf
    assert b"AI:" not in pdf


def test_generation_stores_template_render_log(db_session, monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "local")
    get_settings.cache_clear()
    seed_admin_defaults(db_session)
    patient = Patient(name="Jane Doe", drive_folder_id="folder")
    db_session.add(patient)
    db_session.flush()
    db_session.add(SourceDocument(patient_id=patient.id, drive_file_id="intake-log", name="intake.pdf", file_type=FileType.INTAKE.value))
    db_session.commit()

    output = generate_summary(db_session, patient, save_pdf=False)
    log = db_session.query(TemplateRenderLog).filter(TemplateRenderLog.output_document_id == output.id).first()
    assert log is not None
    assert log.document_type == DocumentType.SUMMARY.value
    assert log.render_context_snapshot_json
    get_settings.cache_clear()
