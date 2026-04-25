import re
from datetime import datetime
from sqlalchemy.orm import Session

from .models import FileType, Patient, ProcessedFile, SourceDocument


ZOOM_NOTE_RE = re.compile(r"^\d{6}-zoomn?note\.pdf$", re.IGNORECASE)


def classify_file(filename: str) -> FileType:
    lower = filename.lower()
    if "headway intake" in lower or "intake" in lower:
        return FileType.INTAKE
    if any(token in lower for token in ("asrs", "phq9", "gad7", "phq-9")):
        return FileType.ASSESSMENT
    if ZOOM_NOTE_RE.match(filename):
        return FileType.ZOOM_NOTE
    return FileType.UNKNOWN


def sync_patient_files(db: Session, patient: Patient, files: list[dict]) -> list[SourceDocument]:
    created: list[SourceDocument] = []
    for item in files:
        drive_file_id = item["id"]
        exists = db.query(SourceDocument).filter(SourceDocument.drive_file_id == drive_file_id).first()
        if exists:
            continue
        source = SourceDocument(
            patient_id=patient.id,
            drive_file_id=drive_file_id,
            name=item["name"],
            file_type=classify_file(item["name"]).value,
            uploaded_at=item.get("modified_time") or datetime.utcnow(),
            processed=False,
        )
        db.add(source)
        db.flush()
        db.add(ProcessedFile(source_document_id=source.id))
        source.processed = True
        created.append(source)
    db.commit()
    for source in created:
        db.refresh(source)
    return created


def grouped_sources(sources: list[SourceDocument]) -> dict[str, list[SourceDocument]]:
    grouped = {file_type.value: [] for file_type in FileType}
    for source in sources:
        grouped.setdefault(source.file_type, []).append(source)
    return grouped
