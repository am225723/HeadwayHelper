from fastapi import Depends, FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session, selectinload

from .auth import create_access_token, get_current_user, hash_password, require_roles, verify_password
from .config import get_settings
from .database import Base, engine, get_db
from .drive import grouped_sources, sync_patient_files
from .generation import create_billing_for_output, generate_session_note, generate_summary, generate_treatment_plan
from .models import BillingSummary, DocumentType, OutputDocument, OutputStatus, Patient, ReviewStatus, ReviewStatusValue, Role, SourceDocument, User
from .schemas import (
    BillingRecalculateRequest,
    BillingSummaryOut,
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
    return {"message": "Resync started", "created": len(created)}


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
    pseudo_pdf = f"%PDF-1.4\n% Clinical AI export\n{output.content}\n%%EOF\n"
    return Response(content=pseudo_pdf.encode(), media_type="application/pdf")


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
    db.commit()
    db.refresh(billing)
    return billing


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
    count = db.query(Patient).count()
    return {"message": "Sync started", "patients": count}
