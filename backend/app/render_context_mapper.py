from datetime import date
from typing import Any

from .models import DocumentType, Patient, SourceDocument


def map_ai_output_to_placeholders(
    doc_type: DocumentType,
    patient: Patient,
    sources: list[SourceDocument],
    ai_output: dict[str, Any],
    placeholders: list[str],
) -> dict[str, Any]:
    """Normalize structured AI output into the exact placeholders required by a template."""
    base = _base_context(patient, sources, ai_output)
    if doc_type == DocumentType.SUMMARY:
        base.update(summary_placeholder_mapper(ai_output))
    elif doc_type == DocumentType.SESSION_NOTE:
        base.update(session_note_placeholder_mapper(ai_output))
    elif doc_type == DocumentType.TREATMENT_PLAN:
        base.update(treatment_plan_placeholder_mapper(ai_output))

    normalized_ai = {str(key).lower(): value for key, value in ai_output.items()}
    context = {key: normalized_ai.get(key, base.get(key, "Not documented")) for key in placeholders}
    context.update({key: value for key, value in base.items() if key in placeholders})
    return context


def summary_placeholder_mapper(ai_output: dict[str, Any]) -> dict[str, Any]:
    return _aliases(
        ai_output,
        {
            "patient_name": ["client_name", "name"],
            "summary_date": ["date", "generated_date"],
            "clinical_summary": ["summary", "hpi_compiled_narrative"],
            "diagnostic_impression": ["diagnosis", "diagnostic_summary"],
            "safety_risk_summary": ["risk_summary", "risk_assessment"],
            "medication_considerations": ["pharmacology", "medication_summary"],
        },
    )


def session_note_placeholder_mapper(ai_output: dict[str, Any]) -> dict[str, Any]:
    return _aliases(
        ai_output,
        {
            "client_id": ["patient_id", "mrn"],
            "date_of_service": ["dos", "date"],
            "data": ["data_section", "subjective_data"],
            "assessment": ["assessment_section"],
            "response": ["response_section"],
            "plan": ["plan_section"],
            "icd10_codes": ["diagnosis_codes"],
            "cpt_codes": ["billing_codes"],
        },
    )


def treatment_plan_placeholder_mapper(ai_output: dict[str, Any]) -> dict[str, Any]:
    return _aliases(
        ai_output,
        {
            "patient_name": ["client_name", "name"],
            "plan_date": ["date", "generated_date"],
            "hpi": ["hpi_compiled_narrative", "history_present_illness"],
            "symptoms": ["current_symptoms"],
            "risk_assessment": ["safety_risk_summary", "risk_summary"],
            "diagnosis": ["diagnostic_impression", "diagnoses"],
            "goals": ["treatment_goals"],
            "treatment_strategy": ["plan", "strategy"],
        },
    )


def _base_context(patient: Patient, sources: list[SourceDocument], ai_output: dict[str, Any]) -> dict[str, Any]:
    today = date.today().isoformat()
    return {
        "patient_name": patient.name,
        "client_name": patient.name,
        "client_id": patient.id,
        "patient_id": patient.id,
        "mrn": f"MRN-{patient.id[:6].upper()}",
        "date": today,
        "generated_date": today,
        "date_of_service": ai_output.get("date_of_service") or today,
        "source_documents": [source.name for source in sources],
    }


def _aliases(ai_output: dict[str, Any], aliases: dict[str, list[str]]) -> dict[str, Any]:
    normalized = {str(key).lower(): value for key, value in ai_output.items()}
    mapped: dict[str, Any] = {}
    for canonical, keys in aliases.items():
        if canonical in normalized:
            mapped[canonical] = normalized[canonical]
            continue
        for key in keys:
            if key in normalized:
                mapped[canonical] = normalized[key]
                break
    return mapped
