import json
import os
from abc import ABC, abstractmethod
from datetime import date
from typing import Any

import httpx

from .config import get_settings
from .models import DocumentType, Patient, SourceDocument


class AIOutputError(ValueError):
    pass


class AIProvider(ABC):
    @abstractmethod
    def generate_structured(self, doc_type: DocumentType, patient: Patient, sources: list[SourceDocument], placeholders: list[str]) -> dict[str, Any]:
        raise NotImplementedError


class LocalAIProvider(AIProvider):
    def generate_structured(self, doc_type: DocumentType, patient: Patient, sources: list[SourceDocument], placeholders: list[str]) -> dict[str, Any]:
        base = {key: "" for key in placeholders}
        base.update({"patient_name": patient.name, "date_of_service": date.today().isoformat()})
        source_names = ", ".join(source.name for source in sources)
        if doc_type == DocumentType.SUMMARY:
            base.update(
                {
                    "presenting_concerns": f"Draft summary based on: {source_names}",
                    "assessment_results": "Pending clinician review.",
                    "diagnostic_impressions": "Pending clinician review.",
                    "recommendations": "Review source documents and finalize recommendations.",
                }
            )
        elif doc_type == DocumentType.SESSION_NOTE:
            base.update(
                {
                    "service_name": "",
                    "subjective": f"Draft note based only on: {source_names}",
                    "objective": "",
                    "assessment": "",
                    "plan": "",
                    "icd10_codes": [],
                    "psychotherapy_minutes": None,
                    "em_level": None,
                    "has_medical_decision_making": False,
                }
            )
        else:
            base.update(
                {
                    "problems": "Pending clinician review.",
                    "goals": "Pending clinician review.",
                    "interventions": "Pending clinician review.",
                    "progress_measures": "Pending clinician review.",
                }
            )
        return base


class JsonHttpAIProvider(AIProvider):
    def __init__(self, provider: str):
        self.provider = provider

    def generate_structured(self, doc_type: DocumentType, patient: Patient, sources: list[SourceDocument], placeholders: list[str]) -> dict[str, Any]:
        prompt = (
            "Return strict JSON only. Do not invent missing clinical or billing fields. "
            f"Document type: {doc_type.value}. Patient: {patient.name}. "
            f"Required keys: {', '.join(placeholders)}. "
            f"Source filenames: {', '.join(source.name for source in sources)}."
        )
        for _ in range(3):
            content = self._request(prompt)
            try:
                parsed = json.loads(content)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict) and all(key in parsed for key in placeholders):
                return parsed
        raise AIOutputError("AI provider did not return valid JSON matching the template schema")

    def _request(self, prompt: str) -> str:
        if self.provider == "openai":
            key = os.environ.get("OPENAI_API_KEY")
            if not key:
                raise AIOutputError("OPENAI_API_KEY is not configured")
            response = httpx.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={"model": os.environ.get("OPENAI_MODEL", "gpt-4.1-mini"), "messages": [{"role": "user", "content": prompt}], "response_format": {"type": "json_object"}},
                timeout=45,
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        if self.provider == "gemini":
            key = os.environ.get("GEMINI_API_KEY")
            if not key:
                raise AIOutputError("GEMINI_API_KEY is not configured")
            response = httpx.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={key}",
                json={"contents": [{"parts": [{"text": prompt}]}]},
                timeout=45,
            )
            response.raise_for_status()
            return response.json()["candidates"][0]["content"]["parts"][0]["text"]
        if self.provider == "perplexity":
            key = os.environ.get("PERPLEXITY_API_KEY")
            if not key:
                raise AIOutputError("PERPLEXITY_API_KEY is not configured")
            response = httpx.post(
                "https://api.perplexity.ai/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={"model": os.environ.get("PERPLEXITY_MODEL", "sonar"), "messages": [{"role": "user", "content": prompt}]},
                timeout=45,
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        raise AIOutputError(f"Unsupported AI provider: {self.provider}")


def get_ai_provider() -> AIProvider:
    provider = get_settings().ai_provider.lower()
    if provider == "local":
        return LocalAIProvider()
    if provider in {"openai", "gemini", "perplexity"}:
        return JsonHttpAIProvider(provider)
    raise AIOutputError(f"Unsupported AI provider: {provider}")
