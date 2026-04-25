from datetime import date
from sqlalchemy.orm import Session

from .billing import BillingInput, select_cpt_codes
from .models import BillingSummary, DocumentType, FileType, OutputDocument, OutputStatus, Patient, ProcessingRun, SourceDocument


def get_summary_sources(db: Session, patient_id: str) -> list[SourceDocument]:
    return (
        db.query(SourceDocument)
        .filter(SourceDocument.patient_id == patient_id, SourceDocument.file_type.in_([FileType.INTAKE, FileType.ASSESSMENT]))
        .order_by(SourceDocument.uploaded_at.asc())
        .all()
    )


def get_session_note_source(db: Session, patient_id: str, source_document_id: str) -> SourceDocument | None:
    return (
        db.query(SourceDocument)
        .filter(
            SourceDocument.id == source_document_id,
            SourceDocument.patient_id == patient_id,
            SourceDocument.file_type == FileType.ZOOM_NOTE,
        )
        .first()
    )


def get_treatment_plan_sources(db: Session, patient_id: str) -> dict:
    summary = (
        db.query(OutputDocument)
        .filter(OutputDocument.patient_id == patient_id, OutputDocument.doc_type == DocumentType.SUMMARY)
        .order_by(OutputDocument.created_at.desc())
        .first()
    )
    session = (
        db.query(OutputDocument)
        .filter(OutputDocument.patient_id == patient_id, OutputDocument.doc_type == DocumentType.SESSION_NOTE)
        .order_by(OutputDocument.created_at.desc())
        .first()
    )
    sources = get_summary_sources(db, patient_id)
    return {"summary": summary, "session_note": session, "sources": sources}


def render_document(patient: Patient, doc_type: DocumentType, source_names: list[str]) -> str:
    title = doc_type.value.replace("_", " ").title()
    source_block = "\n".join(f"- {name}" for name in source_names) or "- No source files"
    return (
        f"{title}\n\n"
        f"Patient: {patient.name}\n"
        f"Source files:\n{source_block}\n\n"
        "Clinical content is ready for provider review. "
        "Diagnosis: F41.1. Psychotherapy minutes: 45. Medical decision making: moderate."
    )


def create_output(db: Session, patient: Patient, doc_type: DocumentType, content: str, save_pdf: bool, summary_id: str | None = None, session_note_id: str | None = None) -> OutputDocument:
    output = OutputDocument(
        patient_id=patient.id,
        doc_type=doc_type.value,
        content=content,
        status=OutputStatus.FINAL.value if save_pdf else OutputStatus.DRAFT.value,
        drive_file_id=f"local-{doc_type.value.lower()}-{patient.id}" if save_pdf else None,
        summary_id=summary_id,
        session_note_id=session_note_id,
    )
    db.add(output)
    db.flush()
    if doc_type == DocumentType.SESSION_NOTE:
        create_billing_for_output(db, patient, output)
    db.add(ProcessingRun(patient_id=patient.id, doc_type=doc_type.value, success=True))
    db.commit()
    db.refresh(output)
    return output


def generate_summary(db: Session, patient: Patient, save_pdf: bool) -> OutputDocument:
    sources = get_summary_sources(db, patient.id)
    if not any(source.file_type == FileType.INTAKE for source in sources):
        raise ValueError("Summary requires an intake source document")
    content = render_document(patient, DocumentType.SUMMARY, [source.name for source in sources])
    return create_output(db, patient, DocumentType.SUMMARY, content, save_pdf)


def generate_session_note(db: Session, patient: Patient, source_document_id: str, save_pdf: bool) -> OutputDocument:
    source = get_session_note_source(db, patient.id, source_document_id)
    if not source:
        raise ValueError("Session note requires a selected zoom note source")
    content = render_document(patient, DocumentType.SESSION_NOTE, [source.name])
    return create_output(db, patient, DocumentType.SESSION_NOTE, content, save_pdf)


def generate_treatment_plan(db: Session, patient: Patient, save_pdf: bool) -> OutputDocument:
    selected = get_treatment_plan_sources(db, patient.id)
    if not selected["summary"] or not selected["session_note"]:
        raise ValueError("Treatment plan requires an existing summary and session note")
    source_names = [source.name for source in selected["sources"]]
    source_names.extend([f"Summary {selected['summary'].id}", f"Session note {selected['session_note'].id}"])
    content = render_document(patient, DocumentType.TREATMENT_PLAN, source_names)
    return create_output(
        db,
        patient,
        DocumentType.TREATMENT_PLAN,
        content,
        save_pdf,
        summary_id=selected["summary"].id,
        session_note_id=selected["session_note"].id,
    )


def create_billing_for_output(db: Session, patient: Patient, output: OutputDocument) -> BillingSummary:
    result = select_cpt_codes(
        BillingInput(
            patient_name=patient.name,
            date_of_service=date.today(),
            service_name="Follow-up",
            icd10_codes=["F41.1"],
            psychotherapy_minutes=45,
            em_level="99214",
            has_medical_decision_making=True,
        )
    )
    billing = BillingSummary(
        output_document_id=output.id,
        patient_name=patient.name,
        date_of_service=date.today(),
        service_name="Follow-up",
        icd10_codes="F41.1",
        cpt_codes=", ".join(result.cpt_codes),
        psychotherapy_minutes=45,
        headway_block=result.headway_block,
        reimbursement_notes=result.reimbursement_notes,
    )
    db.add(billing)
    return billing
