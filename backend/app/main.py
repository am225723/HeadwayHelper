from fastapi import Depends, FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session, selectinload

from .auth import create_access_token, get_current_user, hash_password, require_roles, verify_password
from .config import get_settings
from .database import Base, engine, get_db
from .billing import BillingInput, psychiatric_evaluation_comparison
from .drive import get_drive_service, grouped_sources, sync_all_patient_folders, sync_patient_files
from .generation import create_billing_for_output, dispatch_new_sources, generate_session_note, generate_summary, generate_treatment_plan
from .models import BillingSummary, DocumentType, FileType, OutputDocument, OutputStatus, Patient, ReviewStatus, ReviewStatusValue, Role, SourceDocument, User
from .pdf import html_to_pdf_bytes
from .schemas import (
    BillingRecalculateRequest,
    BillingSummaryOut,
    BillingComparisonResponse,
    ClassificationUpdate,
    GenerateResponse,
    GenerateSessionNoteRequest,
    GenerateSummaryRequest,
    GenerateTreatmentPlanRequest,
    LocalResyncRequest,
    PatientCreate,
    PatientDetail,
    PatientList,
    ReviewItem,
    ReviewRequest,
    SourceDocumentsResponse,
    Token,
    UserLogin,
    UserOut,
    UserRegister,
)


Base.metadata.create_all(bind=engine)
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
