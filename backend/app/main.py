"""FastAPI application entrypoint for the clinical AI backend.

This module configures the FastAPI server, including CORS, startup
events, dependency injection and API routes. It exposes endpoints for
synchronising Google Drive, retrieving patient information and
generating clinical documents.
"""

from __future__ import annotations

from fastapi import FastAPI, Depends, HTTPException, Body
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from .config import ALLOWED_ORIGINS
from .database import get_session, engine
from .models import Base, Patient, Output
from .drive_service import sync_all_patients
from .generator_service import generate_treatment_plan, generate_session_note
from .summary_service import generate_patient_summary

app = FastAPI(title="Clinical AI Generator v2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


@app.on_event("startup")
async def on_startup() -> None:
    """Initialize the database and run any startup tasks."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


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
            "id": rec.folder_id,
            "name": rec.name,
        }
        for rec in records
    ]


@app.get("/patients/{folder_id}")
async def api_get_patient_detail(folder_id: str, session: AsyncSession = Depends(get_session)) -> dict:
    """Return details for a single patient folder."""
    result = await session.execute(
        Patient.__table__.select().where(Patient.folder_id == folder_id)
    )
    patient = result.fetchone()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    pat_obj = await session.get(Patient, patient.id)

    docs = [
        {
            "id": doc.id,
            "drive_file_id": doc.drive_file_id,
            "file_name": doc.file_name,
            "mime_type": doc.mime_type,
            "modified_time": doc.modified_time,
        }
        for doc in pat_obj.documents
    ]

    outs = [
        {
            "id": out.id,
            "file_id": out.output_drive_file_id,
            "file_name": out.output_file_name,
            "output_type": out.output_type,
            "created_at": out.created_at,
            "content": getattr(out, "content", None),
            "is_draft": not bool(out.output_drive_file_id),
        }
        for out in pat_obj.outputs
    ]

    return {
        "folder": {
            "id": pat_obj.folder_id,
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


@app.post("/generate/patient-summary")
async def api_generate_patient_summary(
    payload: GenerateRequest = Body(...), session: AsyncSession = Depends(get_session)
) -> dict:
    """Generate a pre-intake summary for the specified patient."""
    result = await session.execute(
        Patient.__table__.select().where(Patient.folder_id == payload.folder_id)
    )
    patient = result.fetchone()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    pat_obj = await session.get(Patient, patient.id)
    output = await generate_patient_summary(session, pat_obj)

    return {
        "success": True,
        "output_id": output.id,
        "output_file_id": output.output_drive_file_id,
        "output_file_name": output.output_file_name,
    }


@app.post("/generate/treatment-plan")
async def api_generate_treatment_plan(
    payload: GenerateRequest = Body(...), session: AsyncSession = Depends(get_session)
) -> dict:
    """Generate a treatment plan for a patient."""
    result = await session.execute(
        Patient.__table__.select().where(Patient.folder_id == payload.folder_id)
    )
    patient = result.fetchone()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    pat_obj = await session.get(Patient, patient.id)
    output = await generate_treatment_plan(session, pat_obj)

    return {
        "success": True,
        "output_id": output.id,
        "output_file_id": output.output_drive_file_id,
        "output_file_name": output.output_file_name,
    }


@app.post("/generate/session-note")
async def api_generate_session_note(
    payload: GenerateRequest = Body(...), session: AsyncSession = Depends(get_session)
) -> dict:
    """Generate a session note for a patient."""
    result = await session.execute(
        Patient.__table__.select().where(Patient.folder_id == payload.folder_id)
    )
    patient = result.fetchone()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    pat_obj = await session.get(Patient, patient.id)

    try:
        output = await generate_session_note(session, pat_obj)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "success": True,
        "output_id": output.id,
        "output_file_id": output.output_drive_file_id,
        "output_file_name": output.output_file_name,
    }


@app.get("/outputs/{output_id}")
async def api_get_output_file(output_id: int, session: AsyncSession = Depends(get_session)):
    """Download a generated PDF by its Output ID."""
    out_obj = await session.get(Output, output_id)
    if not out_obj:
        raise HTTPException(status_code=404, detail="Output not found")

    if not out_obj.output_drive_file_id:
        raise HTTPException(
            status_code=409,
            detail="This output is a draft and does not have a PDF file yet. Use /outputs/{output_id}/preview to view it.",
        )

    from .drive_service import download_file

    file_bytes = download_file(out_obj.output_drive_file_id)

    return StreamingResponse(
        iter([file_bytes]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename={out_obj.output_file_name}"
        },
    )


@app.get("/outputs/{output_id}/preview")
async def api_preview_output(output_id: int, session: AsyncSession = Depends(get_session)) -> dict:
    """Return a generated output for in-app preview, including drafts."""
    out_obj = await session.get(Output, output_id)
    if not out_obj:
        raise HTTPException(status_code=404, detail="Output not found")

    content = getattr(out_obj, "content", None)
    if content is None:
        content = getattr(out_obj, "html_content", None)
    if content is None:
        content = getattr(out_obj, "text_content", None)

    return {
        "id": out_obj.id,
        "file_id": out_obj.output_drive_file_id,
        "file_name": out_obj.output_file_name,
        "output_type": out_obj.output_type,
        "created_at": out_obj.created_at,
        "is_draft": not bool(out_obj.output_drive_file_id),
        "content": content,
    }
