import re
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


def active_template(db: Session | None, doc_type: DocumentType) -> tuple[str, dict[str, Any]]:
    if db is not None:
        row = (
            db.query(DocumentTemplate)
            .filter(DocumentTemplate.document_type == doc_type.value, DocumentTemplate.is_active.is_(True))
            .order_by(DocumentTemplate.updated_at.desc())
            .first()
        )
        if row:
            return row.template_source, row.cleanup_rules_json or {}
    return load_template(doc_type), {"strip_instruction_blocks": True, "remove_not_documented_lines": doc_type != DocumentType.SUMMARY}


def load_template(doc_type: DocumentType) -> str:
    path = Path(__file__).parent / "templates" / TEMPLATE_FILES[doc_type]
    return path.read_text(errors="ignore")


def extract_placeholders(template: str) -> list[str]:
    dollar = [token.lower() for token in DOLLAR_RE.findall(template)]
    mustache = [token.lower() for token in MUSTACHE_RE.findall(template)]
    return sorted(set(dollar + mustache))


def render_template(doc_type: DocumentType, values: dict, db: Session | None = None) -> str:
    template, cleanup_rules = active_template(db, doc_type)
    return render_template_source(template, values, cleanup_rules)


def render_template_source(template: str, values: dict, cleanup_rules: dict[str, Any] | None = None) -> str:
    cleanup_rules = cleanup_rules or {}
    if cleanup_rules.get("strip_instruction_blocks", True):
        template = strip_instruction_blocks(template)
    rendered = replace_placeholders(template, values)
    return cleanup_rendered_html(rendered, cleanup_rules)


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
    if rules.get("remove_not_documented_lines", False):
        html = re.sub(r"(?is)<(p|li|tr|div)([^>]*)>[^<]*(Not documented|not documented)[\s\S]*?</\1>", "", html)
    html = re.sub(r"(?m)^[ \t]*\n", "", html)
    return html


def _format_value(value: object) -> str:
    if value is None:
        return "Not documented"
    if isinstance(value, list):
        return "\n".join(str(item) for item in value) if value else "Not documented"
    if isinstance(value, dict):
        return "; ".join(f"{key}: {val}" for key, val in value.items()) or "Not documented"
    text = str(value).strip()
    return text or "Not documented"
