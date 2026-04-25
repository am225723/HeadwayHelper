from app.drive import classify_file
from app.models import FileType, Patient
from app.drive import sync_patient_files


def test_classifies_intake_assessment_and_zoom_note():
    assert classify_file("Headway Intake - Jane.pdf") == FileType.INTAKE
    assert classify_file("PHQ-9 scores.pdf") == FileType.ASSESSMENT
    assert classify_file("042526-zoomnote.pdf") == FileType.ZOOM_NOTE
    assert classify_file("042526-zoomnnote.pdf") == FileType.ZOOM_NOTE
    assert classify_file("receipt.pdf") == FileType.UNKNOWN


def test_duplicate_drive_sync_behavior(db_session):
    patient = Patient(name="Jane Doe", drive_folder_id="folder")
    db_session.add(patient)
    db_session.commit()
    files = [{"id": "file-1", "name": "Headway Intake.pdf"}]
    assert len(sync_patient_files(db_session, patient, files)) == 1
    assert len(sync_patient_files(db_session, patient, files)) == 0
