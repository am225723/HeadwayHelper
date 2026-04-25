import re
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from .models import DocumentTemplate, DocumentType

TEMPLATE_FILES = {
    DocumentType.SUMMARY: "Clinical_Summary_Template.html",
    DocumentType.TREATMENT_PLAN: "Clinical_Treatment_Plan.html",
    DocumentType.SESSION_NOTE: "Session_Notes_Template.html",
}
DOLLAR_RE = re.compile(r"\$\$([A-Z0-9_]+)\$\$")
MUSTACHE_RE = re.compile(r"{{\s*([a-zA-Z0-9_]+)\s*}}")
AI_BLOCK_RE = re.compile(r"(?is)<(system|prompt|instructions)>.*?</\1>")
AI_SPAN_RE = re.compile(r"(?is)<span[^>]*class=[\"'][^\"']*ai-prompt[^\"']*[\"'][^>]*>.*?</span>")
BRACKET_AI_RE = re.compile(r"\[AI:[^\]]+\]")
UNREPLACED_RE = re.compile(r"(\$\$[A-Z0-9_]+\$\$|{{\s*[a-zA-Z0-9_]+\s*}})")


@dataclass(frozen=True)
class ActiveTemplate:
    source: str
    cleanup_rules: dict[str, Any]
    template_id: str | None = None
    version: int = 1


@dataclass(frozen=True)
class RenderDiagnostics:
    raw_html: str
    html: str
    placeholders: list[str]
    missing_placeholders: list[str]
    unreplaced_placeholders: list[str]
    cleanup_warnings: list[str]
    template_id: str | None = None
    template_version: int = 1


def active_template_record(db: Session | None, doc_type: DocumentType) -> ActiveTemplate:
    if db is not None:
        row = (
            db.query(DocumentTemplate)
            .filter(DocumentTemplate.document_type == doc_type.value, DocumentTemplate.is_active.is_(True))
            .order_by(DocumentTemplate.updated_at.desc())
            .first()
        )
        if row:
            return ActiveTemplate(row.template_source, row.cleanup_rules_json or {}, row.id, row.version or 1)
    return ActiveTemplate(load_template(doc_type), {"strip_instruction_blocks": True, "remove_not_documented_lines": doc_type != DocumentType.SUMMARY})


def active_template(db: Session | None, doc_type: DocumentType) -> tuple[str, dict[str, Any]]:
    record = active_template_record(db, doc_type)
    return record.source, record.cleanup_rules


def load_template(doc_type: DocumentType) -> str:
    path = Path(__file__).parent / "templates" / TEMPLATE_FILES[doc_type]
    return path.read_text(errors="ignore")


def extract_placeholders(template: str) -> list[str]:
    dollar = [token.lower() for token in DOLLAR_RE.findall(template)]
    mustache = [token.lower() for token in MUSTACHE_RE.findall(template)]
    return sorted(set(dollar + mustache))


def placeholder_counts(template: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for token in [*DOLLAR_RE.findall(template), *MUSTACHE_RE.findall(template)]:
        key = token.lower()
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def render_template(doc_type: DocumentType, values: dict, db: Session | None = None) -> str:
    return render_template_with_diagnostics(doc_type, values, db).html


def render_template_source(template: str, values: dict, cleanup_rules: dict[str, Any] | None = None) -> str:
    return render_template_source_with_diagnostics(template, values, cleanup_rules).html


def render_template_with_diagnostics(doc_type: DocumentType, values: dict, db: Session | None = None) -> RenderDiagnostics:
    template = active_template_record(db, doc_type)
    result = render_template_source_with_diagnostics(template.source, values, template.cleanup_rules)
    return RenderDiagnostics(
        raw_html=result.raw_html,
        html=result.html,
        placeholders=result.placeholders,
        missing_placeholders=result.missing_placeholders,
        unreplaced_placeholders=result.unreplaced_placeholders,
        cleanup_warnings=result.cleanup_warnings,
        template_id=template.template_id,
        template_version=template.version,
    )


def render_template_source_with_diagnostics(template: str, values: dict, cleanup_rules: dict[str, Any] | None = None) -> RenderDiagnostics:
    cleanup_rules = cleanup_rules or {}
    placeholders = extract_placeholders(template)
    missing = [key for key in placeholders if _is_missing(values.get(key))]
    if cleanup_rules.get("strip_instruction_blocks", True):
        template = strip_instruction_blocks(template)
    raw_html = replace_placeholders(template, values)
    cleaned, warnings = cleanup_rendered_html(raw_html, cleanup_rules)
    unreplaced = sorted(set(match.group(1) for match in UNREPLACED_RE.finditer(cleaned)))
    return RenderDiagnostics(
        raw_html=raw_html,
        html=cleaned,
        placeholders=placeholders,
        missing_placeholders=missing,
        unreplaced_placeholders=unreplaced,
        cleanup_warnings=warnings,
    )


def replace_placeholders(template: str, values: dict) -> str:
    normalized = {str(key).lower(): value for key, value in values.items()}

    def dollar(match: re.Match) -> str:
        return escape(_format_value(normalized.get(match.group(1).lower())))

    def mustache(match: re.Match) -> str:
        return escape(_format_value(normalized.get(match.group(1).lower())))

    return MUSTACHE_RE.sub(mustache, DOLLAR_RE.sub(dollar, template))


def strip_instruction_blocks(template: str) -> str:
    template = AI_BLOCK_RE.sub("", template)
    template = AI_SPAN_RE.sub("", template)
    return BRACKET_AI_RE.sub("", template)


def cleanup_rendered_html(html: str, rules: dict[str, Any]) -> str:
    warnings: list[str] = []
    if rules.get("remove_not_documented_lines", False):
        html, count = re.subn(r"(?is)<(p|li|tr|div)([^>]*)>[^<]*(Not documented|not documented)[\s\S]*?</\1>", "", html)
        if count:
            warnings.append(f"Removed {count} not-documented block(s)")
    html, empty_count = re.subn(r"(?is)<(p|li)([^>]*)>\s*(?:&nbsp;)?\s*</\1>", "", html)
    if empty_count:
        warnings.append(f"Removed {empty_count} empty paragraph/list item(s)")
    html = re.sub(r"(?m)^[ \t]*\n", "", html)
    return html, warnings


def _format_value(value: object) -> str:
    if value is None:
        return "Not documented"
    if isinstance(value, list):
        return "\n".join(str(item) for item in value) if value else "Not documented"
    if isinstance(value, dict):
        return "; ".join(f"{key}: {val}" for key, val in value.items()) or "Not documented"
    text = str(value).strip()
    return text or "Not documented"


def _is_missing(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip().lower().rstrip(".") in {"", "not documented"}
    if isinstance(value, (list, tuple, dict)):
        return len(value) == 0
    return False
