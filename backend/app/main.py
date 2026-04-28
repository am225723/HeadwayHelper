"""FastAPI application entrypoint for the clinical AI backend.

This module configures the FastAPI server, including CORS, startup
events, dependency injection and API routes. It exposes endpoints for
synchronising Google Drive, retrieving patient information and
generating clinical documents.
"""

from __future__ import annotations

from typing import List, Any

from fastapi import FastAPI, Depends, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from .config import ALLOWED_ORIGINS
from .database import get_session, engine
from .models import Base, Patient, OutputDocument
from .drive_service import sync_all_patients
from .generator_service import generate_treatment_plan, generate_session_note
from .summary_service import generate_patient_summary

app = FastAPI(title="Clinical AI Generator v2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup() -> None:
    """Initialize the database and run any startup tasks."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@app.get("/")
async def root() -> dict:
    """Basic health response for root requests."""
    return {"status": "ok", "app": "Clinical AI Generator v2"}


@app.get("/health")
@app.get("/api/health")
async def health() -> dict:
    """Health check endpoint."""
    return {"status": "ok"}


def _get_attr(obj: Any, *names: str, default: Any = None) -> Any:
    """Return the first existing attribute from an object."""
    for name in names:
        if hasattr(obj, name):
            return getattr(obj, name)
    return default


def _output_drive_file_id(output: OutputDocument) -> str | None:
    return _get_attr(output, "output_drive_file_id", "drive_file_id")


def _output_file_name(output: OutputDocument) -> str | None:
    return _get_attr(output, "output_file_name", "file_name")


def _output_type(output: OutputDocument) -> str | None:
    return _get_attr(output, "output_type", "doc_type")


def _output_content(output: OutputDocument) -> str | None:
    return _get_attr(output, "content", "html_content", "text_content")


def _output_to_dict(output: OutputDocument) -> dict:
    """Serialize an output document safely across model versions."""
    drive_file_id = _output_drive_file_id(output)

    return {
        "id": output.id,
        "file_id": drive_file_id,
        "file_name": _output_file_name(output),
        "output_type": _output_type(output),
        "created_at": _get_attr(output, "created_at"),
        "content": _output_content(output),
        "is_draft": not bool(drive_file_id),
    }


@app.get("/patients")
async def api_get_patients(session: AsyncSession = Depends(get_session)) -> List[dict]:
    """Return a list of all patient folders in Google Drive."""
    await sync_all_patients(session)

    patients = await session.execute(
        Patient.__table__.select().order_by(Patient.name)
    )
    records = patients.fetchall()

    return [
        {
            "id": _get_attr(rec, "folder_id", "drive_folder_id", "id"),
            "name": rec.name,
        }
        for rec in records
    ]


@app.get("/patients/{folder_id}")
async def api_get_patient_detail(
    folder_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Return details for a single patient folder."""
    folder_column = (
        Patient.__table__.c.folder_id
        if "folder_id" in Patient.__table__.c
        else Patient.__table__.c.drive_folder_id
    )

    result = await session.execute(
        Patient.__table__.select().where(folder_column == folder_id)
    )
    patient = result.fetchone()

    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    pat_obj = await session.get(Patient, patient.id)

    docs = [
        {
            "id": doc.id,
            "drive_file_id": _get_attr(doc, "drive_file_id"),
            "file_name": _get_attr(doc, "file_name", "name"),
            "mime_type": _get_attr(doc, "mime_type"),
            "modified_time": _get_attr(doc, "modified_time", "uploaded_at", "created_at"),
        }
        for doc in _get_attr(pat_obj, "documents", "source_documents", default=[])
    ]

    outs = [
        _output_to_dict(out)
        for out in _get_attr(pat_obj, "outputs", "output_documents", default=[])
    ]

    return {
        "folder": {
            "id": _get_attr(pat_obj, "folder_id", "drive_folder_id", "id"),
            "name": pat_obj.name,
        },
        "documents": docs,
        "outputs": outs,
    }


@app.post("/drive/sync")
async def api_drive_sync(session: AsyncSession = Depends(get_session)) -> dict:
    """Synchronize all patient folders and return the number of folders."""
    patients = await sync_all_patients(session)
    return {"count": len(patients)}


class GenerateRequest(BaseModel):
    folder_id: str


async def _get_patient_by_folder_id(
    session: AsyncSession,
    folder_id: str,
) -> Patient:
    """Fetch patient by folder id across model versions."""
    folder_column = (
        Patient.__table__.c.folder_id
        if "folder_id" in Patient.__table__.c
        else Patient.__table__.c.drive_folder_id
    )

    result = await session.execute(
        Patient.__table__.select().where(folder_column == folder_id)
    )
    patient = result.fetchone()

    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    pat_obj = await session.get(Patient, patient.id)
    if not pat_obj:
        raise HTTPException(status_code=404, detail="Patient not found")

    return pat_obj


@app.post("/generate/patient-summary")
async def api_generate_patient_summary(
    payload: GenerateRequest = Body(...),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Generate a pre-intake summary for the specified patient."""
    pat_obj = await _get_patient_by_folder_id(session, payload.folder_id)
    output = await generate_patient_summary(session, pat_obj)

    return {
        "success": True,
        "output_id": output.id,
        "output_file_id": _output_drive_file_id(output),
        "output_file_name": _output_file_name(output),
    }


@app.post("/generate/treatment-plan")
async def api_generate_treatment_plan(
    payload: GenerateRequest = Body(...),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Generate a treatment plan for a patient."""
    pat_obj = await _get_patient_by_folder_id(session, payload.folder_id)
    output = await generate_treatment_plan(session, pat_obj)

    return {
        "success": True,
        "output_id": output.id,
        "output_file_id": _output_drive_file_id(output),
        "output_file_name": _output_file_name(output),
    }


@app.post("/generate/session-note")
async def api_generate_session_note(
    payload: GenerateRequest = Body(...),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Generate a session note for a patient."""
    pat_obj = await _get_patient_by_folder_id(session, payload.folder_id)

    try:
        output = await generate_session_note(session, pat_obj)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "success": True,
        "output_id": output.id,
        "output_file_id": _output_drive_file_id(output),
        "output_file_name": _output_file_name(output),
    }


@app.get("/outputs/{output_id}")
async def api_get_output_file(
    output_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Download a generated PDF by its Output ID."""
    out_obj = await session.get(OutputDocument, output_id)

    if not out_obj:
        raise HTTPException(status_code=404, detail="Output not found")

    drive_file_id = _output_drive_file_id(out_obj)
    if not drive_file_id:
        raise HTTPException(
            status_code=409,
            detail=(
                "This output is a draft and does not have a PDF file yet. "
                "Use /outputs/{output_id}/preview to view it."
            ),
        )

    from .drive_service import download_file

    file_bytes = download_file(drive_file_id)
    file_name = _output_file_name(out_obj) or f"output-{out_obj.id}.pdf"

    return StreamingResponse(
        iter([file_bytes]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename={file_name}"
        },
    )


@app.get("/outputs/{output_id}/preview")
async def api_preview_output(
    output_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Return a generated output for in-app preview, including drafts."""
    out_obj = await session.get(OutputDocument, output_id)

    if not out_obj:
        raise HTTPException(status_code=404, detail="Output not found")

    return _output_to_dict(out_obj)
