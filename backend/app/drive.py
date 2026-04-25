import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaInMemoryUpload
from sqlalchemy.orm import Session

from .config import get_settings
from .models import FileType, Patient, ProcessedFile, SourceDocument


ZOOM_NOTE_RE = re.compile(r"^\d{6}-zoomn?note\.pdf$", re.IGNORECASE)
FOLDER_MIME = "application/vnd.google-apps.folder"
PDF_MIME = "application/pdf"


class DriveClient(Protocol):
    def list_patient_folders(self) -> list[dict]:
        ...

    def list_files(self, folder_id: str) -> list[dict]:
        ...

    def ensure_output_folder(self, patient_folder_id: str) -> str:
        ...

    def upload_pdf(self, folder_id: str, filename: str, pdf_bytes: bytes) -> str:
        ...


def classify_file(filename: str) -> FileType:
    lower = filename.lower()
    if "headway intake" in lower or "intake" in lower:
        return FileType.INTAKE
    if any(token in lower for token in ("asrs", "phq9", "gad7", "phq-9")):
        return FileType.ASSESSMENT
    if ZOOM_NOTE_RE.match(filename):
        return FileType.ZOOM_NOTE
    return FileType.UNKNOWN


class GoogleDriveService:
    def __init__(self) -> None:
        settings = get_settings()
        if not settings.google_drive_root_folder_id:
            raise RuntimeError("GOOGLE_DRIVE_ROOT_FOLDER_ID is not configured")
        if not settings.google_service_account_json:
            raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON is not configured")
        self.root_folder_id = settings.google_drive_root_folder_id
        creds_info = _load_service_account_info(settings.google_service_account_json)
        credentials = service_account.Credentials.from_service_account_info(creds_info, scopes=["https://www.googleapis.com/auth/drive"])
        self.service = build("drive", "v3", credentials=credentials, cache_discovery=False)

    def list_patient_folders(self) -> list[dict]:
        query = f"'{self.root_folder_id}' in parents and mimeType='{FOLDER_MIME}' and trashed=false"
        return self._list(query)

    def list_files(self, folder_id: str) -> list[dict]:
        query = f"'{folder_id}' in parents and mimeType!='{FOLDER_MIME}' and trashed=false"
        return self._list(query)

    def ensure_output_folder(self, patient_folder_id: str) -> str:
        query = f"'{patient_folder_id}' in parents and mimeType='{FOLDER_MIME}' and name='output' and trashed=false"
        matches = self._list(query)
        if matches:
            return matches[0]["id"]
        metadata = {"name": "output", "mimeType": FOLDER_MIME, "parents": [patient_folder_id]}
        created = self.service.files().create(body=metadata, fields="id").execute()
        return created["id"]

    def upload_pdf(self, folder_id: str, filename: str, pdf_bytes: bytes) -> str:
        media = MediaInMemoryUpload(pdf_bytes, mimetype=PDF_MIME, resumable=False)
        metadata = {"name": filename, "mimeType": PDF_MIME, "parents": [folder_id]}
        created = self.service.files().create(body=metadata, media_body=media, fields="id").execute()
        return created["id"]

    def _list(self, query: str) -> list[dict]:
        results: list[dict] = []
        page_token = None
        while True:
            response = (
                self.service.files()
                .list(q=query, fields="nextPageToken, files(id, name, mimeType, modifiedTime)", pageToken=page_token, pageSize=1000)
                .execute()
            )
            results.extend(response.get("files", []))
            page_token = response.get("nextPageToken")
            if not page_token:
                return results


class NullDriveService:
    def list_patient_folders(self) -> list[dict]:
        return []

    def list_files(self, folder_id: str) -> list[dict]:
        return []

    def ensure_output_folder(self, patient_folder_id: str) -> str:
        return f"{patient_folder_id}-output"

    def upload_pdf(self, folder_id: str, filename: str, pdf_bytes: bytes) -> str:
        return f"local-{folder_id}-{filename}"


def get_drive_service() -> DriveClient:
    settings = get_settings()
    if settings.google_drive_root_folder_id and settings.google_service_account_json:
        return GoogleDriveService()
    return NullDriveService()


def sync_all_patient_folders(db: Session, drive: DriveClient | None = None) -> list[SourceDocument]:
    client = drive or get_drive_service()
    created: list[SourceDocument] = []
    for folder in client.list_patient_folders():
        patient = db.query(Patient).filter(Patient.drive_folder_id == folder["id"]).first()
        if not patient:
            patient = Patient(name=folder["name"], drive_folder_id=folder["id"])
            db.add(patient)
            db.flush()
        else:
            patient.name = folder["name"]
        created.extend(sync_patient_files(db, patient, client.list_files(folder["id"]), commit=False))
    db.commit()
    for source in created:
        db.refresh(source)
    return created


def sync_patient_files(db: Session, patient: Patient, files: list[dict], commit: bool = True) -> list[SourceDocument]:
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
            uploaded_at=_parse_drive_time(item.get("modifiedTime") or item.get("modified_time")),
            processed=False,
        )
        db.add(source)
        db.flush()
        created.append(source)
    if commit:
        db.commit()
        for source in created:
            db.refresh(source)
    return created


def mark_processed(db: Session, source: SourceDocument) -> None:
    if not source.processed:
        source.processed = True
        db.add(ProcessedFile(source_document_id=source.id))


def grouped_sources(sources: list[SourceDocument]) -> dict[str, list[SourceDocument]]:
    grouped = {file_type.value: [] for file_type in FileType}
    for source in sources:
        grouped.setdefault(source.file_type, []).append(source)
    return grouped


def _parse_drive_time(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return datetime.now(timezone.utc)


def _load_service_account_info(raw: str) -> dict:
    stripped = raw.strip()
    if stripped.startswith("{"):
        return json.loads(stripped)
    return json.loads(Path(stripped).read_text())
