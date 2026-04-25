from datetime import datetime, timezone

from app.generation import get_session_note_source, get_summary_sources, get_treatment_plan_sources
from app.models import DocumentType, FileType, OutputDocument, OutputStatus, Patient, SourceDocument


def test_summary_source_selection(db_session):
    patient = Patient(name="Jane Doe", drive_folder_id="folder")
    db_session.add(patient)
    db_session.flush()
    intake = SourceDocument(patient_id=patient.id, drive_file_id="i", name="intake.pdf", file_type=FileType.INTAKE.value)
    assessment = SourceDocument(patient_id=patient.id, drive_file_id="a", name="PHQ9.pdf", file_type=FileType.ASSESSMENT.value)
    zoom = SourceDocument(patient_id=patient.id, drive_file_id="z", name="042526-zoomnote.pdf", file_type=FileType.ZOOM_NOTE.value)
    db_session.add_all([intake, assessment, zoom])
    db_session.commit()
    assert [source.id for source in get_summary_sources(db_session, patient.id)] == [intake.id, assessment.id]


def test_session_note_single_zoom_note_rule(db_session):
    patient = Patient(name="Jane Doe", drive_folder_id="folder")
    db_session.add(patient)
    db_session.flush()
    zoom = SourceDocument(patient_id=patient.id, drive_file_id="z", name="042526-zoomnote.pdf", file_type=FileType.ZOOM_NOTE.value)
    intake = SourceDocument(patient_id=patient.id, drive_file_id="i", name="intake.pdf", file_type=FileType.INTAKE.value)
    db_session.add_all([zoom, intake])
    db_session.commit()
    assert get_session_note_source(db_session, patient.id, zoom.id).id == zoom.id
    assert get_session_note_source(db_session, patient.id, intake.id) is None


def test_treatment_plan_uses_latest_session_note(db_session):
    patient = Patient(name="Jane Doe", drive_folder_id="folder")
    db_session.add(patient)
    db_session.flush()
    summary = OutputDocument(patient_id=patient.id, doc_type=DocumentType.SUMMARY.value, status=OutputStatus.FINAL.value)
    old_session = OutputDocument(patient_id=patient.id, doc_type=DocumentType.SESSION_NOTE.value, status=OutputStatus.FINAL.value, created_at=datetime(2026, 4, 1, tzinfo=timezone.utc))
    new_session = OutputDocument(patient_id=patient.id, doc_type=DocumentType.SESSION_NOTE.value, status=OutputStatus.FINAL.value, created_at=datetime(2026, 4, 25, tzinfo=timezone.utc))
    db_session.add_all([summary, old_session, new_session])
    db_session.commit()
    selected = get_treatment_plan_sources(db_session, patient.id)
    assert selected["summary"].id == summary.id
    assert selected["session_note"].id == new_session.id
