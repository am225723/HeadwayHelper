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
AI_SPAN_CAPTURE_RE = re.compile(r"(?is)<span([^>]*)class=[\"'][^\"']*ai-prompt[^\"']*[\"']([^>]*)>(.*?)</span>")
BRACKET_AI_RE = re.compile(r"\[AI:[^\]]+\]")
UNREPLACED_RE = re.compile(r"(\$\$[A-Z0-9_]+\$\$|{{\s*[a-zA-Z0-9_]+\s*}})")
TAG_RE = re.compile(r"(?is)<[^>]+>")


@dataclass(frozen=True)
class TemplatePlaceholder:
    placeholder_type: str
    machine_key: str
    prompt_text: str
    raw_token: str
    section_name: str | None
    repeat_count: int
    is_required: bool
    default_missing_behavior: str


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
    placeholder_inventory: list[TemplatePlaceholder]
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
    return sorted({item.machine_key for item in extract_placeholder_inventory(template)})


def placeholder_counts(template: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in extract_placeholder_inventory(template, preserve_repeats=True):
        counts[item.machine_key] = counts.get(item.machine_key, 0) + 1
    return dict(sorted(counts.items()))


def extract_placeholder_inventory(template: str, preserve_repeats: bool = False) -> list[TemplatePlaceholder]:
    """Extract both render tokens and embedded clinical prompt spans.

    The treatment-plan source keeps many prompts as visible ``span.ai-prompt`` nodes.
    Those are first-class placeholders because the AI must answer them even though
    they are not mustache variables.
    """
    raw_items: list[dict[str, str | None]] = []
    for match in DOLLAR_RE.finditer(template):
        token = match.group(1)
        raw_items.append(
            {
                "placeholder_type": "mustache",
                "machine_key": token.lower(),
                "prompt_text": token.replace("_", " ").strip(),
                "raw_token": match.group(0),
                "section_name": _section_for_offset(template, match.start()),
            }
        )
    for match in MUSTACHE_RE.finditer(template):
        token = match.group(1)
        raw_items.append(
            {
                "placeholder_type": "mustache",
                "machine_key": token.lower(),
                "prompt_text": token.replace("_", " ").strip(),
                "raw_token": match.group(0),
                "section_name": _section_for_offset(template, match.start()),
            }
        )
    for match in AI_SPAN_CAPTURE_RE.finditer(template):
        prompt = _strip_tags(match.group(3)).strip()
        raw_items.append(
            {
                "placeholder_type": "ai_prompt",
                "machine_key": _machine_key(prompt),
                "prompt_text": prompt,
                "raw_token": match.group(0),
                "section_name": _section_for_offset(template, match.start()),
            }
        )

    repeat_counts: dict[tuple[str, str], int] = {}
    for item in raw_items:
        key = (str(item["placeholder_type"]), str(item["machine_key"]))
        repeat_counts[key] = repeat_counts.get(key, 0) + 1

    output: list[TemplatePlaceholder] = []
    seen: set[tuple[str, str]] = set()
    for item in raw_items:
        key = (str(item["placeholder_type"]), str(item["machine_key"]))
        if not preserve_repeats and key in seen:
            continue
        seen.add(key)
        output.append(
            TemplatePlaceholder(
                placeholder_type=str(item["placeholder_type"]),
                machine_key=str(item["machine_key"]),
                prompt_text=str(item["prompt_text"]),
                raw_token=str(item["raw_token"]),
                section_name=item["section_name"],
                repeat_count=repeat_counts[key],
                is_required=_is_required_prompt(str(item["prompt_text"]), str(item["machine_key"])),
                default_missing_behavior="remove_block_if_not_documented",
            )
        )
    return output


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
        placeholder_inventory=result.placeholder_inventory,
        missing_placeholders=result.missing_placeholders,
        unreplaced_placeholders=result.unreplaced_placeholders,
        cleanup_warnings=result.cleanup_warnings,
        template_id=template.template_id,
        template_version=template.version,
    )


def render_template_source_with_diagnostics(template: str, values: dict, cleanup_rules: dict[str, Any] | None = None) -> RenderDiagnostics:
    cleanup_rules = cleanup_rules or {}
    inventory = extract_placeholder_inventory(template)
    placeholders = sorted({item.machine_key for item in inventory})
    missing = [item.machine_key for item in inventory if item.is_required and _is_missing(values.get(item.machine_key))]
    if cleanup_rules.get("strip_instruction_blocks", True):
        template = strip_instruction_blocks(template)
    raw_html = replace_placeholders(template, values)
    cleaned, warnings = cleanup_rendered_html(raw_html, cleanup_rules)
    unreplaced = sorted(set(match.group(1) for match in UNREPLACED_RE.finditer(cleaned)))
    return RenderDiagnostics(
        raw_html=raw_html,
        html=cleaned,
        placeholders=placeholders,
        placeholder_inventory=inventory,
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

    rendered = MUSTACHE_RE.sub(mustache, DOLLAR_RE.sub(dollar, template))

    def ai_prompt(match: re.Match) -> str:
        prompt = _strip_tags(match.group(3)).strip()
        value = _format_value(normalized.get(_machine_key(prompt)))
        if value.strip().lower().rstrip(".") == "not documented":
            value = "__REMOVE_BLOCK__"
        attrs = f"{match.group(1)}{match.group(2)}"
        return f"<span{attrs}>{escape(value)}</span>"

    return AI_SPAN_CAPTURE_RE.sub(ai_prompt, rendered)


def strip_instruction_blocks(template: str) -> str:
    template = AI_BLOCK_RE.sub("", template)
    return BRACKET_AI_RE.sub("", template)


def cleanup_rendered_html(html: str, rules: dict[str, Any]) -> tuple[str, list[str]]:
    warnings: list[str] = []
    if rules.get("remove_not_documented_lines", False):
        html, marked_highlights = re.subn(r'(?is)<div class="highlight-item"[^>]*>(?:(?!</div>).)*?__REMOVE_BLOCK__.*?</div>', "", html)
        html, marked_paragraphs = re.subn(r"(?is)<p[^>]*>(?:(?!</p>).)*?__REMOVE_BLOCK__.*?</p>", "", html)
        html = html.replace("__REMOVE_BLOCK__", "&nbsp;&nbsp;&nbsp;")
        html, not_documented_count = re.subn(r"(?is)<(p|li|tr|div)([^>]*)>(?:(?!</\1>).)*?Not documented(?:(?!</\1>).)*?</\1>", "", html)
        removed = marked_highlights + marked_paragraphs + not_documented_count
        if removed:
            warnings.append(f"Removed {removed} not-documented block(s)")
    html, instruction_count = re.subn(r'(?is)<div class="system-instructions-box[^>]*>.*?</div>', "", html)
    if instruction_count:
        warnings.append(f"Removed {instruction_count} instruction block(s)")
    html, empty_highlights = re.subn(r'(?is)<div class="highlight-block"[^>]*>\s*</div>', "", html)
    if empty_highlights:
        warnings.append(f"Removed {empty_highlights} empty highlight block(s)")
    no_break_pattern = r'(?is)<div class="no-break"[^>]*>\s*<h2 class="subsection-title"[^>]*>(?:(?!</h2>).)*?</h2>\s*</div>'
    html, empty_sections = re.subn(no_break_pattern, "", html)
    html, empty_sections_2 = re.subn(no_break_pattern, "", html)
    empty_sections += empty_sections_2
    if empty_sections:
        warnings.append(f"Removed {empty_sections} empty section(s)")
    orphan_pattern = r'(?is)<h1 class="section-title"[^>]*>(?:(?!</h1>).)*?</h1>\s*(?=(<h1|<div class="signature-section"|<!-- SIGNATURE))'
    html, orphaned = re.subn(orphan_pattern, "", html)
    html, orphaned_2 = re.subn(orphan_pattern, "", html)
    orphaned += orphaned_2
    if orphaned:
        warnings.append(f"Removed {orphaned} orphaned section header(s)")
    html, empty_count = re.subn(r"(?is)<(p|li)([^>]*)>\s*(?:&nbsp;)?\s*</\1>", "", html)
    if empty_count:
        warnings.append(f"Removed {empty_count} empty paragraph/list item(s)")
    html = re.sub(r"(?is)<td([^>]*)>\s*</td>", r"<td\1>&nbsp;&nbsp;&nbsp;&nbsp;</td>", html)
    html = re.sub(r"(?is)<br\s*/?>\s*<br\s*/?>", "<br>", html)
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


def _machine_key(prompt: str) -> str:
    text = _strip_tags(prompt).strip().lower()
    text = re.sub(r"^(extract|insert|generate|provide|summarize|list)\s+", "", text)
    text = re.sub(r"\b(format|including|include|with)\b", " ", text)
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text[:120] or "ai_prompt"


def _strip_tags(text: str) -> str:
    return re.sub(r"\s+", " ", TAG_RE.sub("", text)).strip()


def _section_for_offset(template: str, offset: int) -> str | None:
    prefix = template[:offset]
    matches = list(re.finditer(r"(?is)<h[12][^>]*>(.*?)</h[12]>", prefix))
    if not matches:
        return None
    return _strip_tags(matches[-1].group(1)) or None


def _is_required_prompt(prompt_text: str, machine_key: str) -> bool:
    required_keys = {
        "patient_name",
        "date_of_service",
        "icd_10",
        "icd10_codes",
        "cpt_codes",
        "diagnosis",
        "risk_assessment",
    }
    lower = f"{prompt_text} {machine_key}".lower()
    return machine_key in required_keys or any(term in lower for term in ["patient name", "date of service", "icd", "cpt", "diagnosis"])
