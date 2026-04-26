import json
import logging
from abc import ABC, abstractmethod
from datetime import date
from typing import Any

import httpx

from .config import get_settings
from .models import DocumentType, Patient, SourceDocument

logger = logging.getLogger(__name__)

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
        settings = get_settings()
        if self.provider == "openai":
            key = settings.openai_api_key
            if not key:
                raise AIOutputError("OPENAI_API_KEY is not configured")
            response = httpx.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={"model": settings.openai_model or "gpt-4.1-mini", "messages": [{"role": "user", "content": prompt}], "response_format": {"type": "json_object"}},
                timeout=45,
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        if self.provider == "gemini":
            return self._request_gemini(prompt, settings)
        if self.provider == "perplexity":
            key = settings.perplexity_api_key
            if not key:
                return self._fallback_from_perplexity(prompt, settings, "PERPLEXITY_API_KEY is not configured")
            try:
                response = httpx.post(
                    "https://api.perplexity.ai/chat/completions",
                    headers={"Authorization": f"Bearer {key}"},
                    json={"model": settings.perplexity_model, "messages": [{"role": "user", "content": prompt}]},
                    timeout=45,
                )
                response.raise_for_status()
                return response.json()["choices"][0]["message"]["content"]
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code in {401, 402, 403, 429}:
                    return self._fallback_from_perplexity(prompt, settings, f"Perplexity unavailable: HTTP {exc.response.status_code}")
                raise
        raise AIOutputError(f"Unsupported AI provider: {self.provider}")

    def _request_gemini(self, prompt: str, settings=None) -> str:
        settings = settings or get_settings()
        key = settings.gemini_api_key
        if not key:
            raise AIOutputError("GEMINI_API_KEY is not configured")
        response = httpx.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_model}:generateContent?key={key}",
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=45,
        )
        response.raise_for_status()
        return response.json()["candidates"][0]["content"]["parts"][0]["text"]

    def _fallback_from_perplexity(self, prompt: str, settings, reason: str) -> str:
        logger.warning("AI fallback event: primary=perplexity reason=%s prompt_for_new_key=%s gemini_configured=%s", reason, settings.perplexity_fallback_prompt_for_new_key, bool(settings.gemini_api_key))
        if settings.perplexity_fallback_prompt_for_new_key and not settings.gemini_api_key:
            raise AIOutputError(f"{reason}. Please add a replacement PERPLEXITY_API_KEY; Gemini fallback is not configured.")
        if settings.gemini_api_key:
            return self._request_gemini(prompt, settings)
        raise AIOutputError(f"{reason}. Gemini fallback is not configured.")


def get_ai_provider() -> AIProvider:
    provider = get_settings().ai_provider.lower()
    if provider == "local":
        return LocalAIProvider()
    if provider in {"openai", "gemini", "perplexity"}:
        return JsonHttpAIProvider(provider)
    raise AIOutputError(f"Unsupported AI provider: {provider}")
