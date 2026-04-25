from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from .ai import get_ai_provider
from .billing import BillingInput, select_cpt_codes
from .drive import DriveClient, get_drive_service, mark_processed
from .models import BillingSummary, DocumentType, FileType, OutputDocument, OutputStatus, Patient, ProcessingRun, SourceDocument
from .pdf import html_to_pdf_bytes
from .templates import active_template, extract_placeholders, render_template


def get_summary_sources(db: Session, patient_id: str) -> list[SourceDocument]:
    return (
        db.query(SourceDocument)
        .filter(SourceDocument.patient_id == patient_id, SourceDocument.file_type.in_([FileType.INTAKE.value, FileType.ASSESSMENT.value]))
        .order_by(SourceDocument.uploaded_at.asc())
        .all()
    )


def get_session_note_source(db: Session, patient_id: str, source_document_id: str) -> SourceDocument | None:
    return (
        db.query(SourceDocument)
        .filter(
            SourceDocument.id == source_document_id,
            SourceDocument.patient_id == patient_id,
            SourceDocument.file_type == FileType.ZOOM_NOTE.value,
        )
        .first()
    )


def get_treatment_plan_sources(db: Session, patient_id: str) -> dict[str, Any]:
    summary = (
        db.query(OutputDocument)
        .filter(OutputDocument.patient_id == patient_id, OutputDocument.doc_type == DocumentType.SUMMARY.value, OutputDocument.status != OutputStatus.ERROR.value)
        .order_by(OutputDocument.created_at.desc())
        .first()
    )
    session = (
        db.query(OutputDocument)
        .filter(OutputDocument.patient_id == patient_id, OutputDocument.doc_type == DocumentType.SESSION_NOTE.value, OutputDocument.status != OutputStatus.ERROR.value)
        .order_by(OutputDocument.created_at.desc())
        .first()
    )
    return {"summary": summary, "session_note": session, "sources": get_summary_sources(db, patient_id)}


def create_output(
    db: Session,
    patient: Patient,
    doc_type: DocumentType,
    sources: list[SourceDocument],
    save_pdf: bool,
    summary_id: str | None = None,
    session_note_id: str | None = None,
    source_document_id: str | None = None,
    drive: DriveClient | None = None,
) -> OutputDocument:
    template, _ = active_template(db, doc_type)
    placeholders = extract_placeholders(template)
    structured = get_ai_provider().generate_structured(doc_type, patient, sources, placeholders)
    html = render_template(doc_type, structured, db=db)
    pdf_bytes = html_to_pdf_bytes(html)
    drive_file_id = None
    if save_pdf:
        client = drive or get_drive_service()
        output_folder = client.ensure_output_folder(patient.drive_folder_id)
        filename = f"{patient.name}-{doc_type.value.lower().replace('_', '-')}-{date.today().isoformat()}.pdf"
        drive_file_id = client.upload_pdf(output_folder, filename, pdf_bytes)

    output = OutputDocument(
        patient_id=patient.id,
        doc_type=doc_type.value,
        content=html,
        structured_data=structured,
        status=OutputStatus.FINAL.value if save_pdf else OutputStatus.DRAFT.value,
        drive_file_id=drive_file_id,
        summary_id=summary_id,
        session_note_id=session_note_id,
        source_document_id=source_document_id,
    )
    db.add(output)
    db.flush()
    if doc_type == DocumentType.SESSION_NOTE:
        create_billing_for_output(db, patient, output)
    db.add(ProcessingRun(patient_id=patient.id, doc_type=doc_type.value, success=True))
    for source in sources:
        mark_processed(db, source)
    db.commit()
    db.refresh(output)
    return output


def generate_summary(db: Session, patient: Patient, save_pdf: bool, drive: DriveClient | None = None) -> OutputDocument:
    sources = get_summary_sources(db, patient.id)
    if not any(source.file_type == FileType.INTAKE.value for source in sources):
        raise ValueError("Summary requires an intake source document")
    return create_output(db, patient, DocumentType.SUMMARY, sources, save_pdf, drive=drive)


def generate_session_note(db: Session, patient: Patient, source_document_id: str, save_pdf: bool, drive: DriveClient | None = None) -> OutputDocument:
    source = get_session_note_source(db, patient.id, source_document_id)
    if not source:
        raise ValueError("Session note requires a selected zoom note source")
    return create_output(db, patient, DocumentType.SESSION_NOTE, [source], save_pdf, source_document_id=source.id, drive=drive)


def generate_treatment_plan(db: Session, patient: Patient, save_pdf: bool, drive: DriveClient | None = None) -> OutputDocument:
    selected = get_treatment_plan_sources(db, patient.id)
    if not selected["summary"] or not selected["session_note"]:
        raise ValueError("Treatment plan requires an existing summary and session note")
    return create_output(
        db,
        patient,
        DocumentType.TREATMENT_PLAN,
        selected["sources"],
        save_pdf,
        summary_id=selected["summary"].id,
        session_note_id=selected["session_note"].id,
        drive=drive,
    )


def dispatch_new_sources(db: Session, patient: Patient, sources: list[SourceDocument], drive: DriveClient | None = None) -> list[OutputDocument]:
    outputs: list[OutputDocument] = []
    for source in sources:
        try:
            if source.file_type == FileType.INTAKE.value:
                outputs.append(generate_summary(db, patient, save_pdf=True, drive=drive))
            elif source.file_type == FileType.ASSESSMENT.value:
                has_intake = db.query(SourceDocument).filter(SourceDocument.patient_id == patient.id, SourceDocument.file_type == FileType.INTAKE.value).first()
                has_summary = db.query(OutputDocument).filter(OutputDocument.patient_id == patient.id, OutputDocument.doc_type == DocumentType.SUMMARY.value).first()
                if has_intake and not has_summary:
                    outputs.append(generate_summary(db, patient, save_pdf=True, drive=drive))
                else:
                    mark_processed(db, source)
                    db.commit()
            elif source.file_type == FileType.ZOOM_NOTE.value:
                session = generate_session_note(db, patient, source.id, save_pdf=True, drive=drive)
                outputs.append(session)
                selected = get_treatment_plan_sources(db, patient.id)
                if selected["summary"] and selected["session_note"]:
                    outputs.append(generate_treatment_plan(db, patient, save_pdf=True, drive=drive))
            else:
                continue
        except Exception as exc:
            db.rollback()
            db.add(ProcessingRun(patient_id=patient.id, doc_type=_doc_type_for_source(source.file_type), success=False, error_message=str(exc)))
            source.processed = False
            db.commit()
    return outputs


def create_billing_for_output(db: Session, patient: Patient, output: OutputDocument) -> BillingSummary | None:
    data = output.structured_data or {}
    required = ["date_of_service", "service_name", "icd10_codes", "psychotherapy_minutes"]
    if any(data.get(field) in (None, "", []) for field in required):
        return None
    result = select_cpt_codes(
        BillingInput(
            patient_name=patient.name,
            date_of_service=_parse_date(data["date_of_service"]),
            service_name=str(data["service_name"]),
            icd10_codes=_as_list(data["icd10_codes"]),
            psychotherapy_minutes=int(data["psychotherapy_minutes"] or 0),
            em_level=data.get("em_level"),
            is_new_patient=bool(data.get("is_new_patient", False)),
            has_medical_decision_making=bool(data.get("has_medical_decision_making", False)),
            payer=str(data.get("payer") or "Aetna"),
        )
    )
    if result.incomplete_reason:
        return None
    billing = BillingSummary(
        output_document_id=output.id,
        patient_name=patient.name,
        date_of_service=_parse_date(data["date_of_service"]),
        service_name=str(data["service_name"]),
        icd10_codes=", ".join(_as_list(data["icd10_codes"])),
        cpt_codes=", ".join(result.cpt_codes),
        psychotherapy_minutes=int(data["psychotherapy_minutes"] or 0),
        headway_block=result.headway_block,
        reimbursement_notes=result.reimbursement_notes,
    )
    db.add(billing)
    return billing


def _doc_type_for_source(file_type: str) -> str:
    if file_type in {FileType.INTAKE.value, FileType.ASSESSMENT.value}:
        return DocumentType.SUMMARY.value
    if file_type == FileType.ZOOM_NOTE.value:
        return DocumentType.SESSION_NOTE.value
    return "UNKNOWN"


def _parse_date(value: object) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _as_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return [item.strip() for item in str(value).split(",") if item.strip()]
