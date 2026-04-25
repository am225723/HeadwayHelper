import re
from html import escape
from pathlib import Path

from .models import DocumentType

TEMPLATE_FILES = {
    DocumentType.SUMMARY: "Clinical_Summary_Template.html",
    DocumentType.TREATMENT_PLAN: "Clinical_Treatment_Plan.html",
    DocumentType.SESSION_NOTE: "Session_Notes_Template.html",
}
PLACEHOLDER_RE = re.compile(r"{{\s*([a-zA-Z0-9_]+)\s*}}")
SYSTEM_BLOCK_RE = re.compile(r"(?is)<(system|prompt|instructions)>.*?</\1>")


def load_template(doc_type: DocumentType) -> str:
    path = Path(__file__).parent / "templates" / TEMPLATE_FILES[doc_type]
    return path.read_text()


def extract_placeholders(template: str) -> list[str]:
    return sorted(set(PLACEHOLDER_RE.findall(template)))


def render_template(doc_type: DocumentType, values: dict) -> str:
    template = SYSTEM_BLOCK_RE.sub("", load_template(doc_type))
    placeholders = extract_placeholders(template)
    rendered = template
    for key in placeholders:
        value = values.get(key)
        rendered = re.sub(r"{{\s*" + re.escape(key) + r"\s*}}", escape(_format_value(value)), rendered)
    return rendered


def _format_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return str(value)
