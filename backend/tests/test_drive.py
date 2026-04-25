from app.drive import classify_file
from app.models import FileType


def test_classifies_intake_assessment_and_zoom_note():
    assert classify_file("Headway Intake - Jane.pdf") == FileType.INTAKE
    assert classify_file("PHQ-9 scores.pdf") == FileType.ASSESSMENT
    assert classify_file("042526-zoomnote.pdf") == FileType.ZOOM_NOTE
    assert classify_file("042526-zoomnnote.pdf") == FileType.ZOOM_NOTE
    assert classify_file("receipt.pdf") == FileType.UNKNOWN
