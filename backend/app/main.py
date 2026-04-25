from fastapi import Depends, FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session, selectinload

from .auth import create_access_token, get_current_user, hash_password, require_roles, verify_password
from .admin_defaults import seed_admin_defaults
from .config import get_settings
from .database import Base, SessionLocal, engine, get_db
from .billing import BillingInput, psychiatric_evaluation_comparison
from .drive import get_drive_service, grouped_sources, sync_all_patient_folders, sync_patient_files
from .generation import create_billing_for_output, dispatch_new_sources, generate_session_note, generate_summary, generate_treatment_plan
from .models import AppSetting, BillingRule, BillingSummary, ClassificationRule, DocumentTemplate, DocumentType, OutputDocument, OutputStatus, Patient, ReimbursementRate, ReviewStatus, ReviewStatusValue, Role, ServiceType, SourceDocument, User
from .pdf import html_to_pdf_bytes
from .templates import extract_placeholders, render_template_source
from .schemas import (
    AppSettingIn,
    AppSettingOut,
    BillingRecalculateRequest,
    BillingRuleIn,
    BillingRuleOut,
    BillingSummaryOut,
    BillingComparisonResponse,
    ClassificationRuleIn,
    ClassificationRuleOut,
    ClassificationUpdate,
    DocumentTemplateIn,
    DocumentTemplateOut,
    GenerateResponse,
    GenerateSessionNoteRequest,
    GenerateSummaryRequest,
    GenerateTreatmentPlanRequest,
    LocalResyncRequest,
    PatientCreate,
    PatientDetail,
    PatientList,
    ReimbursementRateIn,
    ReimbursementRateOut,
    ReviewItem,
    ReviewRequest,
    ServiceTypeIn,
    ServiceTypeOut,
    SourceDocumentsResponse,
    TemplatePreviewRequest,
    TemplatePreviewResponse,
    Token,
    UserLogin,
    UserOut,
    UserRegister,
)


Base.metadata.create_all(bind=engine)
seed_db = SessionLocal()
try:
    seed_admin_defaults(seed_db)
finally:
    seed_db.close()
settings = get_settings()
app = FastAPI(title="Clinical AI Webapp", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/auth/register", response_model=UserOut, status_code=201)
def register(payload: UserRegister, db: Session = Depends(get_db)) -> User:
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email already exists")
    user = User(email=payload.email, password_hash=hash_password(payload.password), role=payload.role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.post("/api/auth/login", response_model=Token)
def login(payload: UserLogin, db: Session = Depends(get_db)) -> Token:
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return Token(access_token=create_access_token(user.id, user.role))


@app.get("/api/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user


def patient_or_404(db: Session, patient_id: str) -> Patient:
    patient = (
        db.query(Patient)
        .options(selectinload(Patient.source_documents), selectinload(Patient.output_documents))
        .filter(Patient.id == patient_id)
        .first()
    )
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient


@app.get("/api/patients", response_model=PatientList)
def list_patients(page: int = 1, size: int = 25, db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> PatientList:
    page = max(page, 1)
    size = min(max(size, 1), 100)
    query = db.query(Patient).options(selectinload(Patient.source_documents), selectinload(Patient.output_documents))
    total = query.count()
    patients = query.order_by(Patient.updated_at.desc()).offset((page - 1) * size).limit(size).all()
    return PatientList(items=patients, page=page, size=size, total=total)


@app.post("/api/patients", response_model=PatientDetail, status_code=201)
def create_patient(payload: PatientCreate, db: Session = Depends(get_db), _: User = Depends(require_roles(Role.ADMIN))) -> Patient:
    patient = Patient(name=payload.name, drive_folder_id=payload.drive_folder_id)
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient


@app.get("/api/patients/{patient_id}", response_model=PatientDetail)
def get_patient(patient_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> Patient:
    return patient_or_404(db, patient_id)


@app.get("/api/patients/{patient_id}/sources", response_model=SourceDocumentsResponse)
def list_sources(patient_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> dict:
    patient = patient_or_404(db, patient_id)
    return {"patient_id": patient.id, "grouped": grouped_sources(patient.source_documents)}


@app.post("/api/patients/{patient_id}/sources/resync", status_code=202)
def resync_patient(patient_id: str, payload: LocalResyncRequest | None = None, db: Session = Depends(get_db), _: User = Depends(require_roles(Role.ADMIN))) -> dict:
    patient = patient_or_404(db, patient_id)
    files = [item.model_dump() for item in (payload.files if payload else [])]
    created = sync_patient_files(db, patient, files)
    outputs = dispatch_new_sources(db, patient, created)
    return {"message": "Resync completed", "created": len(created), "outputs": len(outputs)}


@app.patch("/api/source-documents/{source_id}/classification", response_model=PatientDetail)
def update_classification(source_id: str, payload: ClassificationUpdate, db: Session = Depends(get_db), _: User = Depends(require_roles(Role.ADMIN))) -> Patient:
    source = db.get(SourceDocument, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source document not found")
    source.file_type = payload.file_type
    source.processed = False
    db.commit()
    return patient_or_404(db, source.patient_id)


@app.post("/api/patients/{patient_id}/generate/summary", response_model=GenerateResponse, status_code=202)
def route_generate_summary(patient_id: str, payload: GenerateSummaryRequest, db: Session = Depends(get_db), _: User = Depends(require_roles(Role.ADMIN, Role.PROVIDER))) -> GenerateResponse:
    patient = patient_or_404(db, patient_id)
    try:
        output = generate_summary(db, patient, payload.save_pdf)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return GenerateResponse(job_id=output.id, status=output.status, output_document_id=output.id)


@app.post("/api/patients/{patient_id}/generate/session-note", response_model=GenerateResponse, status_code=202)
def route_generate_session_note(patient_id: str, payload: GenerateSessionNoteRequest, db: Session = Depends(get_db), _: User = Depends(require_roles(Role.ADMIN, Role.PROVIDER))) -> GenerateResponse:
    patient = patient_or_404(db, patient_id)
    try:
        output = generate_session_note(db, patient, payload.source_document_id, payload.save_pdf)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return GenerateResponse(job_id=output.id, status=output.status, output_document_id=output.id)


@app.post("/api/patients/{patient_id}/generate/treatment-plan", response_model=GenerateResponse, status_code=202)
def route_generate_treatment_plan(patient_id: str, payload: GenerateTreatmentPlanRequest, db: Session = Depends(get_db), _: User = Depends(require_roles(Role.ADMIN, Role.PROVIDER))) -> GenerateResponse:
    patient = patient_or_404(db, patient_id)
    try:
        output = generate_treatment_plan(db, patient, payload.save_pdf)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return GenerateResponse(job_id=output.id, status=output.status, output_document_id=output.id)


@app.get("/api/outputs/{output_id}")
def download_output(output_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> Response:
    output = db.get(OutputDocument, output_id)
    if not output:
        raise HTTPException(status_code=404, detail="Output document not found")
    return Response(content=html_to_pdf_bytes(output.content), media_type="application/pdf")


@app.get("/api/patients/{patient_id}/billing/latest", response_model=BillingSummaryOut)
def latest_billing(patient_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> BillingSummary:
    patient_or_404(db, patient_id)
    billing = (
        db.query(BillingSummary)
        .join(OutputDocument)
        .filter(OutputDocument.patient_id == patient_id)
        .order_by(BillingSummary.created_at.desc())
        .first()
    )
    if not billing:
        raise HTTPException(status_code=404, detail="No billing summary available")
    return billing


@app.post("/api/patients/{patient_id}/billing/recalculate", response_model=BillingSummaryOut)
def recalculate_billing(patient_id: str, payload: BillingRecalculateRequest, db: Session = Depends(get_db), _: User = Depends(require_roles(Role.ADMIN, Role.PROVIDER))) -> BillingSummary:
    patient = patient_or_404(db, patient_id)
    output = db.get(OutputDocument, payload.output_document_id)
    if not output or output.patient_id != patient.id:
        raise HTTPException(status_code=404, detail="Output document not found")
    db.query(BillingSummary).filter(BillingSummary.output_document_id == output.id).delete()
    billing = create_billing_for_output(db, patient, output)
    if not billing:
        raise HTTPException(status_code=400, detail="Billing fields are incomplete and require clinician/admin confirmation")
    db.commit()
    db.refresh(billing)
    return billing


@app.get("/api/patients/{patient_id}/billing/psych-eval-comparison", response_model=list[BillingComparisonResponse])
def psych_eval_comparison(patient_id: str, output_document_id: str | None = None, db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> list[dict]:
    patient = patient_or_404(db, patient_id)
    output = db.get(OutputDocument, output_document_id) if output_document_id else None
    data = output.structured_data if output and output.structured_data else {}
    return psychiatric_evaluation_comparison(
        BillingInput(
            patient_name=patient.name,
            date_of_service=__import__("datetime").date.today(),
            service_name="Psychiatric Evaluation",
            icd10_codes=data.get("icd10_codes") or ["UNCONFIRMED"],
            psychotherapy_minutes=int(data.get("psychotherapy_minutes") or 60),
            em_level=data.get("em_level") or "99205",
            has_medical_decision_making=bool(data.get("has_medical_decision_making", True)),
            is_new_patient=True,
        )
    )


@app.post("/api/outputs/{output_id}/review")
def review_output(output_id: str, payload: ReviewRequest, db: Session = Depends(get_db), user: User = Depends(require_roles(Role.PROVIDER))) -> dict:
    output = db.get(OutputDocument, output_id)
    if not output:
        raise HTTPException(status_code=404, detail="Output document not found")
    if payload.status == ReviewStatusValue.REJECTED and not payload.comments:
        raise HTTPException(status_code=400, detail="Comments are required when rejecting a draft")
    output.status = OutputStatus.FINAL.value if payload.status == ReviewStatusValue.APPROVED else OutputStatus.DRAFT.value
    db.add(ReviewStatus(output_document_id=output.id, reviewer_id=user.id, status=payload.status, comments=payload.comments))
    db.commit()
    return {"message": "Review recorded"}


@app.get("/api/review/queue", response_model=list[ReviewItem])
def review_queue(db: Session = Depends(get_db), _: User = Depends(require_roles(Role.PROVIDER))) -> list[ReviewItem]:
    rows = (
        db.query(OutputDocument, Patient)
        .join(Patient, OutputDocument.patient_id == Patient.id)
        .filter(OutputDocument.status == OutputStatus.DRAFT.value)
        .order_by(OutputDocument.created_at.asc())
        .all()
    )
    return [
        ReviewItem(output_id=output.id, patient_id=patient.id, patient_name=patient.name, doc_type=output.doc_type, status=output.status, created_at=output.created_at)
        for output, patient in rows
    ]


@app.post("/api/admin/drive-sync", status_code=202)
def admin_drive_sync(db: Session = Depends(get_db), _: User = Depends(require_roles(Role.ADMIN))) -> dict:
    drive = get_drive_service()
    created = sync_all_patient_folders(db, drive)
    by_patient: dict[str, list[SourceDocument]] = {}
    for source in created:
        by_patient.setdefault(source.patient_id, []).append(source)
    outputs = 0
    for patient_id, sources in by_patient.items():
        patient = patient_or_404(db, patient_id)
        outputs += len(dispatch_new_sources(db, patient, sources, drive=drive))
    return {"message": "Sync completed", "created": len(created), "outputs": outputs}


def _template_out(row: DocumentTemplate) -> DocumentTemplateOut:
    data = DocumentTemplateOut.model_validate(row)
    data.placeholders = extract_placeholders(row.template_source)
    return data


@app.get("/api/admin/reimbursement-rates", response_model=list[ReimbursementRateOut])
def list_reimbursement_rates(db: Session = Depends(get_db), _: User = Depends(require_roles(Role.ADMIN))) -> list[ReimbursementRate]:
    return db.query(ReimbursementRate).order_by(ReimbursementRate.payer_name, ReimbursementRate.cpt_code).all()


@app.post("/api/admin/reimbursement-rates", response_model=ReimbursementRateOut, status_code=201)
def create_reimbursement_rate(payload: ReimbursementRateIn, db: Session = Depends(get_db), _: User = Depends(require_roles(Role.ADMIN))) -> ReimbursementRate:
    row = ReimbursementRate(**payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@app.put("/api/admin/reimbursement-rates/{rate_id}", response_model=ReimbursementRateOut)
def update_reimbursement_rate(rate_id: str, payload: ReimbursementRateIn, db: Session = Depends(get_db), _: User = Depends(require_roles(Role.ADMIN))) -> ReimbursementRate:
    row = db.get(ReimbursementRate, rate_id)
    if not row:
        raise HTTPException(status_code=404, detail="Rate not found")
    for key, value in payload.model_dump().items():
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    return row


@app.delete("/api/admin/reimbursement-rates/{rate_id}")
def delete_reimbursement_rate(rate_id: str, db: Session = Depends(get_db), _: User = Depends(require_roles(Role.ADMIN))) -> dict:
    row = db.get(ReimbursementRate, rate_id)
    if not row:
        raise HTTPException(status_code=404, detail="Rate not found")
    db.delete(row)
    db.commit()
    return {"message": "Rate deleted"}


@app.get("/api/admin/billing-rules", response_model=list[BillingRuleOut])
def list_billing_rules(db: Session = Depends(get_db), _: User = Depends(require_roles(Role.ADMIN))) -> list[BillingRule]:
    return db.query(BillingRule).order_by(BillingRule.rule_key).all()


@app.put("/api/admin/billing-rules/{rule_key}", response_model=BillingRuleOut)
def upsert_billing_rule(rule_key: str, payload: BillingRuleIn, db: Session = Depends(get_db), _: User = Depends(require_roles(Role.ADMIN))) -> BillingRule:
    row = db.query(BillingRule).filter(BillingRule.rule_key == rule_key).first()
    if not row:
        row = BillingRule(rule_key=rule_key, rule_value_json=payload.rule_value_json, description=payload.description)
        db.add(row)
    else:
        row.rule_value_json = payload.rule_value_json
        row.description = payload.description
    db.commit()
    db.refresh(row)
    return row


@app.get("/api/admin/service-types", response_model=list[ServiceTypeOut])
def list_service_types(db: Session = Depends(get_db), _: User = Depends(require_roles(Role.ADMIN))) -> list[ServiceType]:
    return db.query(ServiceType).order_by(ServiceType.display_order, ServiceType.name).all()


@app.post("/api/admin/service-types", response_model=ServiceTypeOut, status_code=201)
def create_service_type(payload: ServiceTypeIn, db: Session = Depends(get_db), _: User = Depends(require_roles(Role.ADMIN))) -> ServiceType:
    row = ServiceType(**payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@app.put("/api/admin/service-types/{service_type_id}", response_model=ServiceTypeOut)
def update_service_type(service_type_id: str, payload: ServiceTypeIn, db: Session = Depends(get_db), _: User = Depends(require_roles(Role.ADMIN))) -> ServiceType:
    row = db.get(ServiceType, service_type_id)
    if not row:
        raise HTTPException(status_code=404, detail="Service type not found")
    for key, value in payload.model_dump().items():
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    return row


@app.get("/api/admin/classification-rules", response_model=list[ClassificationRuleOut])
def list_classification_rules(db: Session = Depends(get_db), _: User = Depends(require_roles(Role.ADMIN))) -> list[ClassificationRule]:
    return db.query(ClassificationRule).order_by(ClassificationRule.category, ClassificationRule.keyword_or_pattern).all()


@app.post("/api/admin/classification-rules", response_model=ClassificationRuleOut, status_code=201)
def create_classification_rule(payload: ClassificationRuleIn, db: Session = Depends(get_db), _: User = Depends(require_roles(Role.ADMIN))) -> ClassificationRule:
    row = ClassificationRule(**payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@app.put("/api/admin/classification-rules/{rule_id}", response_model=ClassificationRuleOut)
def update_classification_rule(rule_id: str, payload: ClassificationRuleIn, db: Session = Depends(get_db), _: User = Depends(require_roles(Role.ADMIN))) -> ClassificationRule:
    row = db.get(ClassificationRule, rule_id)
    if not row:
        raise HTTPException(status_code=404, detail="Classification rule not found")
    for key, value in payload.model_dump().items():
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    return row


@app.delete("/api/admin/classification-rules/{rule_id}")
def delete_classification_rule(rule_id: str, db: Session = Depends(get_db), _: User = Depends(require_roles(Role.ADMIN))) -> dict:
    row = db.get(ClassificationRule, rule_id)
    if not row:
        raise HTTPException(status_code=404, detail="Classification rule not found")
    db.delete(row)
    db.commit()
    return {"message": "Classification rule deleted"}


@app.get("/api/admin/settings", response_model=list[AppSettingOut])
def list_settings(db: Session = Depends(get_db), _: User = Depends(require_roles(Role.ADMIN))) -> list[AppSetting]:
    return db.query(AppSetting).order_by(AppSetting.setting_key).all()


@app.put("/api/admin/settings/{setting_key}", response_model=AppSettingOut)
def upsert_setting(setting_key: str, payload: AppSettingIn, db: Session = Depends(get_db), _: User = Depends(require_roles(Role.ADMIN))) -> AppSetting:
    row = db.query(AppSetting).filter(AppSetting.setting_key == setting_key).first()
    if not row:
        row = AppSetting(setting_key=setting_key, setting_value_json=payload.setting_value_json, description=payload.description)
        db.add(row)
    else:
        row.setting_value_json = payload.setting_value_json
        row.description = payload.description
    db.commit()
    db.refresh(row)
    return row


@app.get("/api/admin/templates", response_model=list[DocumentTemplateOut])
def list_templates(db: Session = Depends(get_db), _: User = Depends(require_roles(Role.ADMIN))) -> list[DocumentTemplateOut]:
    return [_template_out(row) for row in db.query(DocumentTemplate).order_by(DocumentTemplate.document_type, DocumentTemplate.template_name).all()]


@app.get("/api/admin/templates/{template_id}", response_model=DocumentTemplateOut)
def get_template(template_id: str, db: Session = Depends(get_db), _: User = Depends(require_roles(Role.ADMIN))) -> DocumentTemplateOut:
    row = db.get(DocumentTemplate, template_id)
    if not row:
        raise HTTPException(status_code=404, detail="Template not found")
    return _template_out(row)


@app.put("/api/admin/templates/{template_id}", response_model=DocumentTemplateOut)
def update_template(template_id: str, payload: DocumentTemplateIn, db: Session = Depends(get_db), _: User = Depends(require_roles(Role.ADMIN))) -> DocumentTemplateOut:
    row = db.get(DocumentTemplate, template_id)
    if not row:
        raise HTTPException(status_code=404, detail="Template not found")
    for key, value in payload.model_dump().items():
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    return _template_out(row)


@app.post("/api/admin/templates/{template_id}/preview", response_model=TemplatePreviewResponse)
def preview_template(template_id: str, payload: TemplatePreviewRequest, db: Session = Depends(get_db), _: User = Depends(require_roles(Role.ADMIN))) -> TemplatePreviewResponse:
    row = db.get(DocumentTemplate, template_id)
    if not row:
        raise HTTPException(status_code=404, detail="Template not found")
    placeholders = extract_placeholders(row.template_source)
    values = {key: payload.values.get(key, f"Sample {key.replace('_', ' ')}") for key in placeholders}
    html = render_template_source(row.template_source, values, row.cleanup_rules_json)
    return TemplatePreviewResponse(html=html, placeholders=placeholders)
